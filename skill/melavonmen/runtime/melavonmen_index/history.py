"""Project-authorized GitHub issue and pull request history via gh."""

from contextlib import closing
from datetime import date
import json
import re
import subprocess
from urllib.parse import urlencode

from .index import QUERY_WORD, STOP, check_cancel, iso_now
from .workspace import IndexErrorWithCode, config_file, operation_connection, read_config


SELECTOR = re.compile(r"(?:(?P<host>[A-Za-z0-9.-]+\.[A-Za-z0-9.-]+)/)?(?P<owner>[A-Za-z0-9-]+)/(?P<repo>[A-Za-z0-9_.-]+)\Z")


class GitHubFailure(IndexErrorWithCode):
    def __init__(self, status=None, rate_limited=False):
        super().__init__(f"GitHub history request failed{f' (HTTP {status})' if status else ''}. Check gh login and repository access.",
                         "GITHUB_ERROR")
        self.status = status
        self.rate_limited = rate_limited


def repository_id(value):
    match = SELECTOR.fullmatch(value)
    if not match or match["repo"] in {".", ".."}:
        raise IndexErrorWithCode("Expected [HOST/]OWNER/REPO")
    return "/".join((match["host"] or "github.com", match["owner"], match["repo"])).lower()


def gh_api(host, endpoint, paginated=False):
    command = ["gh", "api", "--hostname", host, endpoint]
    if paginated:
        command.extend(("--paginate", "--slurp"))
    try:
        result = subprocess.run(command, capture_output=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitHubFailure() from exc
    if result.returncode:
        match = re.search(rb"HTTP (\d{3})", result.stderr)
        raise GitHubFailure(int(match[1]) if match else None, b"rate limit" in result.stderr.lower())
    try:
        data = json.loads(result.stdout)
        return [item for page in data for item in page] if paginated else data
    except (ValueError, TypeError) as exc:
        raise GitHubFailure() from exc


def pull_request(workspace, number):
    key = repository_id(workspace.remote_repository())
    host, owner, repo = key.split("/")
    return gh_api(host, f"repos/{owner}/{repo}/pulls/{number}")


class History:
    def __init__(self, index):
        self.index = index
        self.workspace = index.workspace

    def configured(self):
        settings = read_config(config_file(self.workspace.root))
        sources = settings.get("repositoryHistory", {}).get("repositories", [])
        return {repository_id(item["repository"]): item for item in sources if item.get("enabled") is True}

    def choose(self, value, enabled=True):
        sources = self.configured()
        if value:
            key = repository_id(value)
        elif len(sources) == 1:
            key = next(iter(sources))
        else:
            raise IndexErrorWithCode("Specify the history repository")
        if enabled and key not in sources:
            raise IndexErrorWithCode("History must be enabled for this repository in project-local config", "HISTORY_DISABLED")
        return key, sources.get(key, {})

    def status(self, repository=None):
        key, source = self.choose(repository, enabled=False)
        stored, count = None, 0
        if conn := self.index.connect():
            with closing(conn):
                stored = conn.execute("SELECT * FROM history_sources WHERE repository=?", (key,)).fetchone()
                count = conn.execute("SELECT count(*) FROM history_entries WHERE repository=?", (key,)).fetchone()[0]
        return {"repository": key, "enabled": bool(source), "entries": count,
                "lastSyncedAt": stored["synced_at"] if stored else None,
                "since": stored["since_date"] if stored else None}

    def clear(self, repository=None):
        key, _ = self.choose(repository, enabled=False)
        with closing(self.index.connect(write=True)) as conn, operation_connection(conn):
            conn.execute("DELETE FROM history_entries WHERE repository=?", (key,))
            conn.execute("DELETE FROM history_sources WHERE repository=?", (key,))
            self.bump(conn, key)
        return {"repository": key, "cleared": True}

    @staticmethod
    def generation(conn, key):
        row = conn.execute("SELECT generation FROM history_generation WHERE repository=?", (key,)).fetchone()
        return row["generation"] if row else 0

    @staticmethod
    def bump(conn, key):
        conn.execute("""INSERT INTO history_generation VALUES (?,1)
            ON CONFLICT(repository) DO UPDATE SET generation=generation+1""", (key,))

    def sync(self, repository=None, since=None, cancel=None):
        key, source = self.choose(repository)
        host, owner, name = key.split("/")
        prefix = f"repos/{owner}/{name}"
        previous = self.status(key)
        since = since or previous["since"] or source.get("initialSince")
        if since:
            date.fromisoformat(since)
        if previous["lastSyncedAt"] and previous["since"] != since:
            raise IndexErrorWithCode("Clear the existing history cache before changing its initial date")
        with closing(self.index.connect(write=True)) as conn:
            initial = self.generation(conn, key)
        try:
            principal = self.identity(host, prefix)
            with closing(self.index.connect(write=True)) as conn:
                saved = conn.execute("SELECT principal FROM history_sources WHERE repository=?", (key,)).fetchone()
            if saved and saved["principal"] != principal:
                self.clear(key)
                initial += 1
            check_cancel(cancel)
            listing = gh_api(host, f"{prefix}/issues?state=all&per_page=100", paginated=True)
            entries = []
            for item in listing:
                check_cancel(cancel)
                if since and item.get("created_at", "")[:10] < since:
                    continue
                entries.append(self.entry(host, prefix, item, cancel))
            if principal != self.identity(host, prefix):
                self.clear(key)
                raise IndexErrorWithCode("GitHub repository identity or account changed during sync", "GITHUB_ERROR")
            check_cancel(cancel)
        except GitHubFailure as exc:
            if exc.status in {401, 403, 404} and not exc.rate_limited:
                self.clear(key)
            raise
        with closing(self.index.connect(write=True)) as conn, operation_connection(conn):
            if self.generation(conn, key) != initial:
                raise IndexErrorWithCode("Another operation changed history during synchronization", "HISTORY_CHANGED")
            check_cancel(cancel)
            if key not in self.configured():
                raise IndexErrorWithCode("History permission changed during synchronization", "HISTORY_DISABLED")
            conn.execute("DELETE FROM history_entries WHERE repository=?", (key,))
            conn.executemany("INSERT INTO history_entries VALUES (?,?,?,?,?,?,?,?,?,?)",
                             ((key, *entry) for entry in entries))
            conn.execute("INSERT OR REPLACE INTO history_sources VALUES (?,?,?,?)", (key, principal, since, iso_now()))
            self.bump(conn, key)
        return self.status(key)

    @staticmethod
    def identity(host, prefix):
        account = gh_api(host, "user")
        repo = gh_api(host, prefix)
        return f"{repo['id']}:{account['id']}"

    @staticmethod
    def entry(host, prefix, issue, cancel):
        number = issue["number"]
        is_pr = "pull_request" in issue
        kind = "pull_request" if is_pr else "issue"
        original = gh_api(host, f"{prefix}/pulls/{number}") if is_pr else issue
        state = "merged" if original.get("merged_at") else "draft" if original.get("draft") else original["state"]
        discussions = gh_api(host, f"{prefix}/issues/{number}/comments?per_page=100", paginated=True)
        files = []
        if is_pr:
            discussions.extend(gh_api(host, f"{prefix}/pulls/{number}/reviews?per_page=100", paginated=True))
            discussions.extend(gh_api(host, f"{prefix}/pulls/{number}/comments?per_page=100", paginated=True))
            try:
                files = [item["filename"] for item in gh_api(host, f"{prefix}/pulls/{number}/files?per_page=100", paginated=True)]
            except GitHubFailure as exc:
                if exc.status != 422:
                    raise
        check_cancel(cancel)
        passages = [{"text": item.get("body") or "", "url": item.get("html_url") or original["html_url"]}
                    for item in (original, *discussions) if item.get("body")]
        return (number, kind, state, (original.get("user") or {}).get("login", ""), original["title"],
                original["html_url"], original.get("updated_at"), json.dumps(passages), json.dumps(files))

    def search(self, query, options):
        key, _ = self.choose(options.get("repository"))
        conn = self.index.connect()
        if conn is None:
            return []
        selector = re.fullmatch(r"#?(\d+)", query.strip())
        words = {word.casefold() for word in QUERY_WORD.findall(query) if word.casefold() not in STOP}
        hits = []
        with closing(conn):
            for row in conn.execute("SELECT * FROM history_entries WHERE repository=?", (key,)):
                if any(options.get(name) and options[name].casefold() != row[name].casefold() for name in ("kind", "state", "author")):
                    continue
                direct = bool(selector and int(selector[1]) == row["number"] or query.strip() == row["url"])
                passages = [{"text": row["title"], "url": row["url"]}, *json.loads(row["passages"])]
                def relevance(passage):
                    available = {word.casefold() for word in QUERY_WORD.findall(passage["text"])}
                    return len(words & available)
                best = max(passages, key=relevance)
                score = (100 if direct else 0) + relevance(best) + relevance(passages[0])
                if not score:
                    continue
                excerpt = best["text"]
                if len(excerpt) > 550:
                    match = next((m for m in QUERY_WORD.finditer(excerpt) if m[0].casefold() in words), None)
                    start = max(0, match.start() - 120) if match else 0
                    excerpt = excerpt[start:start + 550]
                hits.append({**{name: row[name] for name in ("repository", "number", "kind", "state", "author", "title", "updated")},
                             "url": best["url"], "excerpt": excerpt, "score": score,
                             "files": json.loads(row["files"])})
        return sorted(hits, key=lambda item: (-item["score"], -item["number"]))[:options.get("limit", 10)]

    def overlapping_pulls(self, paths, except_number=None, cancel=None):
        host, owner, repo = repository_id(self.workspace.remote_repository()).split("/")
        prefix = f"repos/{owner}/{repo}/pulls"
        pulls = gh_api(host, prefix + "?" + urlencode({"state": "open", "per_page": 100}), paginated=True)
        overlaps = []
        for pull in pulls[:30]:
            check_cancel(cancel)
            number = pull["number"]
            if number == except_number:
                continue
            files = {item["filename"] for item in gh_api(host, f"{prefix}/{number}/files?per_page=100", paginated=True)}
            common = files & set(paths)
            if common:
                overlaps.append({"pr": number, "url": pull["html_url"], "paths": sorted(common)})
        return {"overlaps": overlaps, "truncated": len(pulls) > 30}
