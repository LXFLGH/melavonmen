import { createHash } from 'node:crypto'
import {
  copyFile,
  mkdir,
  readFile,
  readdir,
  rename,
  rm,
  stat,
  writeFile,
} from 'node:fs/promises'
import { homedir } from 'node:os'
import path from 'node:path'
import z from '@deepseek-ai/schemastery'

export const name = 'doublememory'
export const inject = ['tools']

const DEFAULT_MAX_CONTEXT_CHARS = 4000
const MAX_READ_CHARS = 20000
const MAX_SEARCH_FILES = 400
const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.webp', '.gif'])
const CORE_FILES = {
  soul: 'soul.md',
  identity: 'IDENTITY.md',
  memory: 'MEMORY.md',
}
const TARGETS = ['soul', 'identity', 'memory', 'date', 'session', 'photo', 'meme', 'image', 'file']
const ACTIONS = ['read', 'list', 'search', 'write', 'append', 'edit', 'delete', 'capture', 'add_image', 'init']

const SessionConfig = z.object({
  enabled: z.boolean().default(true).description('Enable memory for this session.'),
  autoCapture: z.boolean().default(true).description('Archive this session automatically.'),
  captureAssistant: z.boolean().default(true).description('Archive assistant replies too.'),
  injectContext: z.boolean().default(true).description('Add memory to this session prompt.'),
  root: z.string().default('').description('Session-specific memory folder. Empty inherits the global folder.'),
  note: z.string().default('').description('Free-form note for this session override.'),
})

export const Config = z
  .object({
    root: z
      .string()
      .default('')
      .description('Memory folder. Empty means ~/.dsh/memory. Relative session folders resolve against it.')
      .volatile(),
    rootMode: z
      .string()
      .default('global')
      .description('Root mode: "global" uses the shared memory folder; "workspace" creates an independent .dsh-memory folder inside each session\'s working directory (ideal for QQ bot or other isolated agents).')
      .volatile(),
    autoCapture: z.boolean().default(true).description('Archive user and assistant messages to session/YYYY-MM-DD.json.').volatile(),
    captureAssistant: z.boolean().default(true).description('Archive assistant replies as well as user messages.').volatile(),
    captureSubagents: z.boolean().default(false).description('Archive subagent sessions too.').volatile(),
    copyImages: z.boolean().default(true).description('Copy conversation images into pic/image.').volatile(),
    injectContext: z.boolean().default(true).description('Add soul.md, IDENTITY.md, and MEMORY.md to the system prompt.').volatile(),
    maxContextChars: z
      .number()
      .min(500)
      .max(50000)
      .step(1)
      .default(DEFAULT_MAX_CONTEXT_CHARS)
      .description('Approximate character budget for memory in the system prompt.')
      .volatile(),
    sessions: z
      .dict(SessionConfig)
      .default({})
      .description('Per-session overrides. Global values remain the default for sessions not listed here.')
      .volatile(),
  })

const SOUL_TEMPLATE = `# Soul

> 这份文件定义助手的“灵魂”：长期价值观、语气、原则和行事方式。
> 它属于用户，可以由助手通过 \`memory\` 工具读取、写入、修改和删除。

## 核心原则

- 诚实：不确定时说明不确定，不编造事实。
- 克制：只做被请求的事，不擅自扩大范围。
- 可恢复：重要修改前保留上下文，删除前确认。
- 尊重用户：使用用户的语言和偏好，不替用户做价值判断。

## 语气

- 清楚、直接、温和。
- 先给结论，再给必要细节。
- 遇到失败时说明原因和下一步，而不是空泛道歉。

## 长期方向

- 帮助用户建立可持续的工作和记忆习惯。
- 把一次性的对话沉淀为可复用的长期记忆。
`

const IDENTITY_TEMPLATE = `# Identity

> 这份文件定义“我是谁”以及与用户的关系。请按实际情况修改。

- 名字：
- 角色：长期陪伴的助手
- 用户称呼：
- 主要语言：中文
- 工作方式：先理解目标，再拆解步骤；重要操作先确认。
- 边界：不伪造记忆；不把推测写成事实；不泄露用户隐私。
- 记忆原则：soul.md 记录原则，IDENTITY.md 记录身份，MEMORY.md 记录长期事实，date/ 记录每日细节。

## 与用户的关系

- 记住用户明确表达的长期偏好。
- 区分“用户说过”与“我推测”。
- 当记忆冲突时，以最近、最明确的用户表述为准，并说明冲突。
`

const MEMORY_TEMPLATE = `# Memory

> 长期记忆索引。每日细节写入 \`date/YYYY-MM-DD.md\`，会话原文写入
> \`session/YYYY-MM-DD.json\`，图片放在 \`pic/{photo,meme,image}/\`。

## 长期事实

- 

## 重要偏好

- 

## 进行中的项目

- 

## 日期索引

- 
`

const PROMPT_HEADER = `You have a persistent memory folder. Use the \`memory\` tool to read or update it.
Memory layout: soul.md, IDENTITY.md, MEMORY.md; date/YYYY-MM-DD.md for daily notes;
session/YYYY-MM-DD.json for archived conversation lines shaped like “speaker: text<img src="pic/image/...">”;
pic/photo, pic/meme, and pic/image for images. Paths are relative to the memory root.`

function readValue(value, fallback) {
  if (value && typeof value === 'object' && typeof value.get === 'function') {
    const current = value.get()
    return current === undefined ? fallback : current
  }
  return value === undefined ? fallback : value
}

function readBoolean(value, fallback) {
  const current = readValue(value, fallback)
  return typeof current === 'boolean' ? current : fallback
}

function clampInt(value, min, max, fallback) {
  const current = Number(value)
  if (!Number.isFinite(current)) return fallback
  return Math.max(min, Math.min(max, Math.trunc(current)))
}

function expandPath(raw, base) {
  let value = String(raw ?? '').trim()
  if (!value) return ''
  if (value === '~') return homedir()
  if (value.startsWith('~/') || value.startsWith('~\\')) value = path.join(homedir(), value.slice(2))
  value = value
    .replace(/\$\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (_, key) => process.env[key] ?? '')
    .replace(/%([^%]+)%/g, (_, key) => process.env[key] ?? '')
    .replace(/\$([A-Za-z_][A-Za-z0-9_]*)/g, (_, key) => process.env[key] ?? '')
  return base ? path.resolve(base, value) : path.resolve(value)
}

function defaultRoot() {
  return path.join(homedir(), '.dsh', 'memory')
}

function globalRoot(config) {
  const configured = readValue(config?.root, '')
  return expandPath(configured) || defaultRoot()
}

function effectiveConfig(config, sessionId, cwd) {
  const sessions = readValue(config?.sessions, {}) || {}
  const override = sessionId && sessions && typeof sessions === 'object' ? sessions[sessionId] : undefined
  const baseRoot = globalRoot(config)
  const overrideRoot = typeof override?.root === 'string' ? override.root.trim() : ''
  const rootModeRaw = readValue(config?.rootMode, 'global')
  const rootMode = rootModeRaw === 'workspace' ? 'workspace' : 'global'
  const pick = (key, fallback) => (override && typeof override[key] === 'boolean' ? override[key] : fallback)
  let root
  if (overrideRoot) {
    root = expandPath(overrideRoot, baseRoot)
  } else if (rootMode === 'workspace' && cwd) {
    root = path.resolve(cwd, '.dsh-memory')
  } else {
    root = baseRoot
  }
  return {
    enabled: override?.enabled !== false,
    autoCapture: pick('autoCapture', readBoolean(config?.autoCapture, true)),
    captureAssistant: pick('captureAssistant', readBoolean(config?.captureAssistant, true)),
    captureSubagents: readBoolean(config?.captureSubagents, false),
    copyImages: readBoolean(config?.copyImages, true),
    injectContext: pick('injectContext', readBoolean(config?.injectContext, true)),
    maxContextChars: clampInt(readValue(config?.maxContextChars, DEFAULT_MAX_CONTEXT_CHARS), 500, 50000, DEFAULT_MAX_CONTEXT_CHARS),
    root,
    baseRoot,
    rootMode,
    note: typeof override?.note === 'string' ? override.note : '',
  }
}

function localDate(ms = Date.now()) {
  const date = new Date(ms)
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function localIso(ms = Date.now()) {
  const date = new Date(ms)
  const pad = (value) => String(value).padStart(2, '0')
  const offset = -date.getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const hours = pad(Math.floor(Math.abs(offset) / 60))
  const minutes = pad(Math.abs(offset) % 60)
  return `${localDate(ms)}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}${sign}${hours}:${minutes}`
}

function assertDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error('date must use YYYY-MM-DD')
  }
  const [year, month, day] = value.split('-').map(Number)
  const candidate = new Date(year, month - 1, day)
  if (
    candidate.getFullYear() !== year ||
    candidate.getMonth() !== month - 1 ||
    candidate.getDate() !== day
  ) {
    throw new Error(`invalid calendar date: ${value}`)
  }
  return value
}

function resolveDate(value) {
  return assertDate(value || localDate())
}

function relativePosix(root, file) {
  return path.relative(root, file).split(path.sep).join('/')
}

function safePath(root, relative) {
  const normalized = String(relative ?? '').replace(/\\/g, '/').trim()
  if (!normalized) throw new Error('path is required')
  if (normalized.includes('\0')) throw new Error('path contains a NUL byte')
  if (normalized.startsWith('/') || /^[A-Za-z]:/.test(normalized)) {
    throw new Error('path must be relative to the memory root')
  }
  if (normalized.split('/').some((part) => part === '..')) {
    throw new Error('path may not leave the memory root')
  }
  const absolute = path.resolve(root, normalized)
  const check = path.relative(root, absolute)
  if (!check || check.startsWith('..') || path.isAbsolute(check)) {
    throw new Error('path must stay inside the memory root')
  }
  return { absolute, relative: normalized.replace(/^\.\//, '') }
}

function safeName(value) {
  const name = String(value ?? '').replace(/\\/g, '/').split('/').pop()?.trim()
  if (!name || name === '.' || name === '..') throw new Error('invalid file name')
  if (/[\u0000-\u001f]/.test(name)) throw new Error('file name contains control characters')
  return name
}

function dateFile(root, date) {
  return safePath(root, `date/${resolveDate(date)}.md`).absolute
}

function sessionFile(root, date) {
  return safePath(root, `session/${resolveDate(date)}.json`).absolute
}

function imageFile(root, target, name) {
  const kind = ['photo', 'meme', 'image'].includes(target) ? target : 'image'
  return safePath(root, `pic/${kind}/${safeName(name)}`).absolute
}

async function readTextFile(file) {
  try {
    return await readFile(file, 'utf8')
  } catch (error) {
    if (error?.code === 'ENOENT') return null
    throw error
  }
}

async function exists(file) {
  try {
    await stat(file)
    return true
  } catch (error) {
    if (error?.code === 'ENOENT') return false
    throw error
  }
}

async function writeAtomic(file, content) {
  await mkdir(path.dirname(file), { recursive: true })
  const temporary = `${file}.${process.pid}.${Date.now()}.${Math.random().toString(36).slice(2)}.tmp`
  await writeFile(temporary, content, 'utf8')
  try {
    await rename(temporary, file)
  } catch (error) {
    if (error?.code !== 'EEXIST' && error?.code !== 'EPERM' && error?.code !== 'EACCES' && error?.code !== 'EBUSY') {
      await rm(temporary, { force: true })
      throw error
    }
    await rm(file, { force: true })
    await rename(temporary, file)
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, '&#96;')
}

function clipText(text, limit) {
  const value = String(text ?? '')
  if (value.length <= limit) return { text: value, truncated: false }
  return { text: value.slice(0, limit), truncated: true }
}

function labelFor(speaker) {
  if (speaker === 'assistant') return '助手'
  if (speaker === 'system') return '系统'
  return '用户'
}

function renderLine(speaker, text, images) {
  const label = labelFor(speaker)
  const body = escapeHtml(String(text ?? '')).replace(/\n/g, '<br>')
  const imageHtml = (images || [])
    .map((src) => `<img src="${escapeAttr(src)}">`)
    .join('')
  return `${label}：${body}${imageHtml}`
}

function mediaExtension(mediaType) {
  switch (mediaType) {
    case 'image/png':
      return 'png'
    case 'image/webp':
      return 'webp'
    case 'image/gif':
      return 'gif'
    default:
      return 'jpg'
  }
}

function hash12(value) {
  return createHash('sha1').update(String(value)).digest('hex').slice(0, 12)
}

function sessionDocument(date) {
  return {
    schema: 1,
    date,
    updatedAt: localIso(),
    entries: [],
  }
}

function normalizeSessionDocument(value, date) {
  if (Array.isArray(value)) return { ...sessionDocument(date), entries: value.filter((entry) => entry && typeof entry === 'object') }
  if (!value || typeof value !== 'object') return sessionDocument(date)
  const entries = Array.isArray(value.entries) ? value.entries.filter((entry) => entry && typeof entry === 'object') : []
  return {
    schema: 1,
    date: value.date || date,
    updatedAt: value.updatedAt || localIso(),
    entries,
  }
}

async function ensureLayout(root) {
  await Promise.all(
    [root, path.join(root, 'date'), path.join(root, 'session'), path.join(root, 'pic'), path.join(root, 'pic', 'photo'), path.join(root, 'pic', 'meme'), path.join(root, 'pic', 'image')].map(
      (directory) => mkdir(directory, { recursive: true }),
    ),
  )
  const templates = {
    'soul.md': SOUL_TEMPLATE,
    'IDENTITY.md': IDENTITY_TEMPLATE,
    'MEMORY.md': MEMORY_TEMPLATE,
  }
  for (const [file, template] of Object.entries(templates)) {
    try {
      await writeFile(path.join(root, file), template, { encoding: 'utf8', flag: 'wx' })
    } catch (error) {
      if (error?.code !== 'EEXIST') throw error
    }
  }
}

function createRuntime(ctx, config) {
  const layoutReady = new Set()
  const docs = new Map()
  const locks = new Map()
  const pending = new Set()
  let disposed = false

  function track(promise) {
    const guarded = Promise.resolve(promise)
      .catch((error) => {
        if (!disposed) console.warn('[memory] background task failed:', error)
      })
      .finally(() => pending.delete(guarded))
    pending.add(guarded)
    return guarded
  }

  async function ensure(root) {
    if (layoutReady.has(root)) return
    await ensureLayout(root)
    layoutReady.add(root)
  }

  async function refreshDocs(root) {
    await ensure(root)
    const entries = await Promise.all(
      Object.values(CORE_FILES).map(async (file) => [file, (await readTextFile(path.join(root, file))) ?? '']),
    )
    docs.set(root, Object.fromEntries(entries))
  }

  function promptFor(root, sessionId, cwd) {
    const current = effectiveConfig(config, sessionId, cwd)
    if (!current.enabled || !current.injectContext) return ''
    const cached = docs.get(root)
    const parts = [PROMPT_HEADER, `Memory root: ${root}`]
    if (cached) {
      for (const [file, text] of Object.entries(cached)) {
        if (text.trim()) parts.push(`## ${file}\n${text.trim()}`)
      }
    } else {
      parts.push('Use the memory tool to read soul.md, IDENTITY.md, and MEMORY.md before relying on memory.')
    }
    const clipped = clipText(`<memory>\n${parts.join('\n\n')}\n</memory>`, current.maxContextChars)
    return clipped.truncated ? `${clipped.text}\n[memory truncated]` : clipped.text
  }

  function withLock(file, operation) {
    const previous = locks.get(file) ?? Promise.resolve()
    const run = previous.then(operation, operation)
    locks.set(file, run)
    return run.finally(() => {
      if (locks.get(file) === run) locks.delete(file)
    })
  }

  async function loadSessionForAppend(file, date) {
    const text = await readTextFile(file)
    if (!text) return sessionDocument(date)
    try {
      return normalizeSessionDocument(JSON.parse(text), date)
    } catch (error) {
      const backup = `${file}.corrupt-${Date.now()}`
      await rename(file, backup).catch(() => {})
      console.warn(`[memory] moved malformed session file to ${backup}:`, error?.message ?? error)
      return sessionDocument(date)
    }
  }

  async function appendSessionEntry(file, date, entry) {
    return withLock(file, async () => {
      const document = await loadSessionForAppend(file, date)
      if (entry.id && document.entries.some((candidate) => candidate.id === entry.id)) return false
      document.entries.push(entry)
      document.date = date
      document.updatedAt = localIso()
      await writeAtomic(file, `${JSON.stringify(document, null, 2)}\n`)
      return true
    })
  }

  async function saveAttachmentImage(root, attachment, date, copyImages) {
    if (!copyImages || !attachment) return null
    const attachments = ctx.get?.('attachments')
    if (!attachments) return null
    const extension = mediaExtension(attachment.mediaType)
    const name = `${date}-${hash12(attachment.attachmentId)}.${extension}`
    const destination = path.join(root, 'pic', 'image', name)
    if (await exists(destination)) return `pic/image/${name}`
    await mkdir(path.dirname(destination), { recursive: true })
    const hostPath = attachments.imageHostPath?.(attachment)
    if (hostPath) {
      await copyFile(hostPath, destination)
    } else {
      const stored = await attachments.readImage(attachment)
      await writeFile(destination, stored.data)
    }
    return `pic/image/${name}`
  }

  async function copyIntoAlbum(root, target, sourcePath, preferredName) {
    const source = expandPath(sourcePath, process.cwd())
    if (!source) throw new Error('source_path is required')
    const info = await stat(source)
    if (!info.isFile()) throw new Error(`source_path is not a file: ${source}`)
    const extension = path.extname(source).toLowerCase()
    if (!IMAGE_EXTS.has(extension)) throw new Error('source_path must be a PNG, JPEG, WebP, or GIF image')
    const base = safeName(preferredName || path.basename(source))
    let destination = imageFile(root, target, base)
    if (path.resolve(source) !== path.resolve(destination) && (await exists(destination))) {
      const stem = path.basename(base, path.extname(base))
      const suffix = path.extname(base)
      destination = imageFile(root, target, `${stem}-${hash12(source)}${suffix}`)
    }
    if (path.resolve(source) !== path.resolve(destination)) {
      await mkdir(path.dirname(destination), { recursive: true })
      await copyFile(source, destination)
    }
    return relativePosix(root, destination)
  }

  async function ensureImageReference(root, value) {
    if (typeof value !== 'string' || !value.trim()) return null
    const normalized = value.replace(/\\/g, '/').trim()
    if (normalized.startsWith('pic/')) {
      const candidate = safePath(root, normalized)
      if (await exists(candidate.absolute)) return normalized
    }
    if (!normalized.startsWith('/') && !/^[A-Za-z]:/.test(normalized) && !normalized.startsWith('pic/')) {
      const candidate = safePath(root, normalized)
      if (await exists(candidate.absolute)) {
        return copyIntoAlbum(root, 'image', candidate.absolute, path.basename(candidate.absolute))
      }
    }
    return copyIntoAlbum(root, 'image', normalized, path.basename(normalized))
  }

  async function captureEntry(root, date, speaker, text, imageValues, sessionId, seq) {
    const images = []
    for (const value of imageValues || []) {
      try {
        const resolved = await ensureImageReference(root, value)
        if (resolved) images.push(resolved)
      } catch (error) {
        console.warn('[memory] could not archive image:', error?.message ?? error)
      }
    }
    const cleanText = String(text ?? '').trim()
    if (!cleanText && images.length === 0) return null
    const id = seq === undefined ? hash12(`${date}|${sessionId}|${speaker}|${cleanText}|${images.join(',')}`) : `${sessionId}:${seq}`
    const entry = {
      id,
      ...(seq === undefined ? {} : { seq }),
      sessionId,
      date,
      time: localIso(),
      speaker,
      label: labelFor(speaker),
      text: cleanText,
      images,
      html: renderLine(speaker, cleanText, images),
    }
    const wrote = await appendSessionEntry(sessionFile(root, date), date, entry)
    return wrote ? entry : null
  }

  function captureFromEvent(session, event) {
    const current = effectiveConfig(config, session?.id, session?.header?.cwd)
    if (!current.enabled || !current.autoCapture) return
    if (session?.header?.origin === 'subagent' && !current.captureSubagents) return
    if (event?.surfaceOp && event.surfaceOp !== 'append') return
    let message
    let speaker
    if (event?.type === 'user/message') {
      message = event.data
      speaker = 'user'
      if (message?.source && message.source.kind !== 'user') return
    } else if (event?.type === 'assistant/message') {
      if (!current.captureAssistant) return
      message = event.data?.message
      speaker = 'assistant'
    } else {
      return
    }
    const text = []
    const images = []
    for (const block of Array.isArray(message?.content) ? message.content : []) {
      if (block?.type === 'text' && typeof block.text === 'string') text.push(block.text)
      if (block?.type === 'image' && block.attachment) images.push(block.attachment)
    }
    const date = localDate(event.time || Date.now())
    track(
      (async () => {
        await ensure(current.root)
        const archived = []
        for (const attachment of images) {
          try {
            const src = await saveAttachmentImage(current.root, attachment, date, current.copyImages)
            if (src) archived.push(src)
          } catch (error) {
            console.warn('[memory] could not copy conversation image:', error?.message ?? error)
          }
        }
        const cleanText = text.join('\n').trim()
        if (!cleanText && archived.length === 0) return
        const sessionId = String(session?.id || 'unknown')
        const entry = {
          id: `${sessionId}:${event.seq}`,
          seq: Number(event.seq),
          sessionId,
          date,
          time: localIso(event.time || Date.now()),
          speaker,
          label: labelFor(speaker),
          text: cleanText,
          images: archived,
          html: renderLine(speaker, cleanText, archived),
        }
        await appendSessionEntry(sessionFile(current.root, date), date, entry)
      })(),
    )
  }

  async function listFiles(root) {
    const files = []
    for (const [target, file] of Object.entries(CORE_FILES)) {
      const info = await stat(path.join(root, file)).catch(() => null)
      files.push({ path: file, kind: target, ...(info?.isFile() ? { bytes: info.size } : {}) })
    }
    for (const [directory, kind] of [
      ['date', 'date'],
      ['session', 'session'],
      ['pic/photo', 'photo'],
      ['pic/meme', 'meme'],
      ['pic/image', 'image'],
    ]) {
      let entries = []
      try {
        entries = await readdir(path.join(root, directory), { withFileTypes: true })
      } catch {
        continue
      }
      for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name)).slice(0, 100)) {
        if (!entry.isFile()) continue
        const info = await stat(path.join(root, directory, entry.name)).catch(() => null)
        files.push({ path: `${directory}/${entry.name}`, kind, ...(info?.isFile() ? { bytes: info.size } : {}) })
      }
    }
    return files
  }

  async function searchFiles(root, query, limit) {
    const needle = query.toLowerCase()
    const matches = []
    let scanned = 0
    async function visit(directory) {
      if (scanned >= MAX_SEARCH_FILES) return
      let entries = []
      try {
        entries = await readdir(directory, { withFileTypes: true })
      } catch {
        return
      }
      for (const entry of entries) {
        if (matches.length >= limit || scanned >= MAX_SEARCH_FILES) return
        if (entry.name === 'pic' || entry.name.startsWith('.')) continue
        const full = path.join(directory, entry.name)
        if (entry.isDirectory()) {
          await visit(full)
          continue
        }
        if (!entry.isFile() || !/\.(md|json|txt)$/i.test(entry.name)) continue
        const info = await stat(full).catch(() => null)
        if (!info || info.size > 1024 * 1024) continue
        scanned += 1
        const text = await readTextFile(full).catch(() => null)
        if (!text) continue
        const lines = text.split(/\r?\n/)
        for (let index = 0; index < lines.length && matches.length < limit; index += 1) {
          if (lines[index].toLowerCase().includes(needle)) {
            matches.push({
              path: relativePosix(root, full),
              line: index + 1,
              text: lines[index].slice(0, 240),
            })
          }
        }
      }
    }
    await visit(root)
    return matches
  }

  function assertTextTarget(target, args) {
  if (target !== 'file') return
  const extension = path.extname(String(args.path || '')).toLowerCase()
  if (!['.md', '.json', '.txt'].includes(extension)) {
    throw new Error('target=file supports .md, .json, and .txt files; use add_image for pictures')
  }
}

async function resolveFileForTarget(root, args, allowFolder = false) {
    const target = String(args.target || '')
    if (CORE_FILES[target]) return path.join(root, CORE_FILES[target])
    if (target === 'date') return dateFile(root, args.date)
    if (target === 'session') return sessionFile(root, args.date)
    if (target === 'photo' || target === 'meme' || target === 'image') {
      if (!args.path && allowFolder) return path.join(root, 'pic', target)
      return imageFile(root, target, args.path)
    }
    if (target === 'file') {
      if (!args.path) throw new Error('path is required for target=file')
      return safePath(root, args.path).absolute
    }
    throw new Error(`target must be one of: ${TARGETS.join(', ')}`)
  }

  async function runAction(args, exec) {
    const action = String(args.action || '')
    if (!ACTIONS.includes(action)) throw new Error(`action must be one of: ${ACTIONS.join(', ')}`)
    const current = effectiveConfig(config, exec?.agent?.id, exec?.agent?.session?.header?.cwd || exec?.agent?.cwd)
    const root = current.root
    await ensure(root)
    if (action === 'init') {
      await refreshDocs(root)
      return {
        ok: true,
        action,
        root,
        summary: `Memory ready at ${root}`,
      }
    }
    if (action === 'list') {
      const files = await listFiles(root)
      return {
        ok: true,
        action,
        root,
        files,
        summary: `${files.length} memory file(s) under ${root}`,
      }
    }
    if (action === 'search') {
      const query = String(args.query || '').trim()
      if (!query) throw new Error('query is required for search')
      const limit = clampInt(args.limit, 1, 100, 20)
      const matches = await searchFiles(root, query, limit)
      return {
        ok: true,
        action,
        root,
        matches,
        truncated: matches.length >= limit,
        summary: `${matches.length} match(es) for ${JSON.stringify(query)}`,
      }
    }
    if (action === 'add_image') {
      const target = ['photo', 'meme', 'image'].includes(args.target) ? args.target : 'image'
      const source = String(args.source_path || '').trim()
      if (!source) throw new Error('source_path is required for add_image')
      const src = await copyIntoAlbum(root, target, source, args.name)
      return {
        ok: true,
        action,
        target,
        path: src,
        src,
        html: `<img src="${escapeAttr(src)}">`,
        summary: `Added ${src}`,
      }
    }
    if (action === 'capture') {
      if (!current.enabled) throw new Error('memory is disabled for this session')
      const speaker = ['user', 'assistant', 'system'].includes(args.speaker) ? args.speaker : 'user'
      const date = resolveDate(args.date)
      const sessionId = String(args.session_id || exec?.agent?.id || 'manual')
      const entry = await captureEntry(root, date, speaker, args.text, args.images, sessionId, undefined)
      if (!entry) throw new Error('capture needs text or at least one image')
      return {
        ok: true,
        action,
        path: `session/${date}.json`,
        html: entry.html,
        summary: `Captured one ${speaker} entry in session/${date}.json`,
      }
    }
    const target = String(args.target || '')
    if (!TARGETS.includes(target)) throw new Error(`target must be one of: ${TARGETS.join(', ')}`)
    assertTextTarget(target, args)
    const file = await resolveFileForTarget(root, args, action === 'read')
    const relative = relativePosix(root, file)
    if (action === 'read') {
      if (target === 'photo' || target === 'meme' || target === 'image') {
        const info = await stat(file).catch(() => null)
        if (!args.path) {
          const files = (await listFiles(root)).filter((entry) => entry.kind === target)
          return { ok: true, action, target, path: relative, root, files, summary: `${files.length} file(s) in ${relative}` }
        }
        if (!info?.isFile()) return { ok: true, action, target, path: relative, exists: false, summary: `${relative} does not exist` }
        return { ok: true, action, target, path: relative, exists: true, bytes: info.size, summary: `${relative} (${info.size} bytes)` }
      }
      const text = await readTextFile(file)
      if (text === null) {
        return { ok: true, action, target, path: relative, exists: false, content: '', summary: `${relative} does not exist` }
      }
      const maxChars = clampInt(args.max_chars, 100, 200000, MAX_READ_CHARS)
      const clipped = clipText(text, maxChars)
      return {
        ok: true,
        action,
        target,
        path: relative,
        exists: true,
        bytes: Buffer.byteLength(text, 'utf8'),
        content: clipped.text,
        truncated: clipped.truncated,
        summary: `Read ${relative} (${text.length} chars${clipped.truncated ? ', truncated' : ''})`,
      }
    }
    if (action === 'write') {
      if (target === 'photo' || target === 'meme' || target === 'image') throw new Error('use add_image to add a picture')
      if (typeof args.content !== 'string') throw new Error('content is required for write')
      if (target === 'session') {
        try {
          JSON.parse(args.content)
        } catch {
          throw new Error('session content must be valid JSON')
        }
      }
      await writeAtomic(file, args.content)
      if (CORE_FILES[target]) await refreshDocs(root)
      return { ok: true, action, target, path: relative, bytes: Buffer.byteLength(args.content, 'utf8'), summary: `Wrote ${relative}` }
    }
    if (action === 'append') {
      if (target === 'session') throw new Error('use capture to append to a session archive')
      if (target === 'photo' || target === 'meme' || target === 'image') throw new Error('use add_image to add a picture')
      if (typeof args.content !== 'string' || !args.content) throw new Error('content is required for append')
      const previous = (await readTextFile(file)) ?? ''
      const separator = previous && !previous.endsWith('\n') ? '\n' : ''
      await writeAtomic(file, `${previous}${separator}${args.content}${args.content.endsWith('\n') ? '' : '\n'}`)
      if (CORE_FILES[target]) await refreshDocs(root)
      return { ok: true, action, target, path: relative, bytes: Buffer.byteLength(args.content, 'utf8'), summary: `Appended to ${relative}` }
    }
    if (action === 'edit') {
      if (target === 'photo' || target === 'meme' || target === 'image') throw new Error('pictures are binary; use add_image or delete')
      const oldText = String(args.old_text ?? '')
      const newText = String(args.new_text ?? '')
      if (!oldText) throw new Error('old_text is required for edit')
      const previous = await readTextFile(file)
      if (previous === null) throw new Error(`${relative} does not exist`)
      const first = previous.indexOf(oldText)
      if (first === -1) throw new Error(`old_text was not found in ${relative}`)
      let replacements = 0
      let next
      if (args.replace_all === true) {
        next = previous.split(oldText).join(newText)
        replacements = previous.split(oldText).length - 1
      } else {
        const second = previous.indexOf(oldText, first + oldText.length)
        if (second !== -1) throw new Error(`old_text appears more than once in ${relative}; set replace_all to true or use a longer match`)
        next = `${previous.slice(0, first)}${newText}${previous.slice(first + oldText.length)}`
        replacements = 1
      }
      if (target === 'session') {
        try {
          JSON.parse(next)
        } catch {
          throw new Error('edit would make the session archive invalid JSON; no change was written')
        }
      }
      await writeAtomic(file, next)
      if (CORE_FILES[target]) await refreshDocs(root)
      return { ok: true, action, target, path: relative, bytes: Buffer.byteLength(next, 'utf8'), summary: `Edited ${relative} (${replacements} replacement${replacements === 1 ? '' : 's'})` }
    }
    if (action === 'delete') {
      if (CORE_FILES[target] && args.confirm !== true) throw new Error('deleting a core memory file requires confirm=true')
      const present = await exists(file)
      if (present) await rm(file, { force: true })
      if (CORE_FILES[target]) await refreshDocs(root)
      return { ok: true, action, target, path: relative, exists: present, deleted: present, summary: present ? `Deleted ${relative}` : `${relative} did not exist` }
    }
    throw new Error(`unsupported action: ${action}`)
  }

  const tool = {
    name: 'memory',
    description:
      'Read, write, edit, delete, search, or capture persistent memory. Layout: soul.md, IDENTITY.md, MEMORY.md; date/YYYY-MM-DD.md; session/YYYY-MM-DD.json with lines shaped like speaker: text<img src="pic/image/...">; pic/photo, pic/meme, pic/image. Paths are relative to the memory root. Capturing conversation messages also happens automatically when enabled in settings.',
    parameters: {
      type: 'object',
      additionalProperties: false,
      properties: {
        action: {
          type: 'string',
          enum: ACTIONS,
          description: 'Operation to perform.',
        },
        target: {
          type: 'string',
          enum: TARGETS,
          description: 'Memory area for read/write/append/edit/delete. list and init do not need it.',
        },
        date: {
          type: 'string',
          description: 'Date in YYYY-MM-DD for date/session targets. Defaults to today.',
        },
        path: {
          type: 'string',
          description: 'Path relative to the memory root. Required for target=file; for photo/meme/image it is the file inside that album.',
        },
        content: {
          type: 'string',
          description: 'Full text for write, or appended text for append.',
        },
        old_text: {
          type: 'string',
          description: 'Exact text to replace for edit.',
        },
        new_text: {
          type: 'string',
          description: 'Replacement text for edit. May be empty.',
        },
        replace_all: {
          type: 'boolean',
          description: 'Replace every occurrence for edit. Defaults to false.',
        },
        query: {
          type: 'string',
          description: 'Case-insensitive text to find for search.',
        },
        limit: {
          type: 'integer',
          description: 'Maximum search results, 1-100. Defaults to 20.',
        },
        speaker: {
          type: 'string',
          enum: ['user', 'assistant', 'system'],
          description: 'Speaker for capture. Defaults to user.',
        },
        text: {
          type: 'string',
          description: 'Message text for capture.',
        },
        images: {
          type: 'array',
          items: { type: 'string' },
          description: 'Image paths for capture. Relative pic/... paths are reused; other files are copied into pic/image.',
        },
        session_id: {
          type: 'string',
          description: 'Session id for capture. Defaults to the calling session, or manual.',
        },
        source_path: {
          type: 'string',
          description: 'Existing image file to copy for add_image.',
        },
        name: {
          type: 'string',
          description: 'Optional destination file name for add_image.',
        },
        confirm: {
          type: 'boolean',
          description: 'Must be true to delete soul.md, IDENTITY.md, or MEMORY.md.',
        },
        max_chars: {
          type: 'integer',
          description: 'Maximum characters returned by read. Defaults to 20000.',
        },
      },
      required: ['action'],
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          ok: { type: 'boolean' },
          action: { type: 'string' },
          target: { type: 'string' },
          path: { type: 'string' },
          root: { type: 'string' },
          summary: { type: 'string' },
          content: { type: 'string' },
          exists: { type: 'boolean' },
          deleted: { type: 'boolean' },
          bytes: { type: 'integer' },
          truncated: { type: 'boolean' },
          src: { type: 'string' },
          html: { type: 'string' },
          files: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                path: { type: 'string' },
                kind: { type: 'string' },
                bytes: { type: 'integer' },
              },
              required: ['path', 'kind'],
            },
          },
          matches: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                path: { type: 'string' },
                line: { type: 'integer' },
                text: { type: 'string' },
              },
              required: ['path', 'line', 'text'],
            },
          },
        },
        required: ['ok', 'action', 'summary'],
      },
      render(_args, value) {
        const parts = [value?.summary ?? 'Memory operation complete.']
        if (typeof value?.content === 'string' && value.content) parts.push(value.content)
        if (Array.isArray(value?.files) && value.files.length > 0) {
          parts.push(
            value.files
              .map((file) => `- ${file.path}${typeof file.bytes === 'number' ? ` (${file.bytes} bytes)` : ''}`)
              .join('\n'),
          )
        }
        if (Array.isArray(value?.matches) && value.matches.length > 0) {
          parts.push(value.matches.map((match) => `${match.path}:${match.line}: ${match.text}`).join('\n'))
        }
        if (typeof value?.html === 'string' && value.html) parts.push(value.html)
        const text = parts.filter(Boolean).join('\n\n')
        return [{ type: 'text', text: text.slice(0, 30000) }]
      },
    },
    async execute(args, exec) {
      if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error('memory arguments must be an object')
      return runAction(args, exec)
    },
  }

  return {
    tool,
    captureFromEvent,
    prepare(root) {
      return track((async () => {
        await ensure(root)
        await refreshDocs(root)
      })())
    },
    promptFor,
    drain() {
      disposed = true
      return Promise.allSettled([...pending])
    },
  }
}

export function apply(ctx, config) {
  const runtime = createRuntime(ctx, config ?? {})
  ctx.effect(() => ctx.tools.register(runtime.tool), 'memory: tool')
  ctx.inject(['settings'], (child) => {
    child.effect(() => child.settings.configure({ auto: false }, ctx.fiber), 'memory: settings page policy')
  })
  ctx.effect(() => ctx.on('session/event', (session, event) => runtime.captureFromEvent(session, event)), 'memory: session archive')
  ctx.effect(
    () =>
      ctx.on('agent/created', ({ agent }) => {
        const current = effectiveConfig(config ?? {}, agent?.id, agent?.session?.header?.cwd || agent?.cwd)
        runtime.prepare(current.root)
      }),
    'memory: session layout',
  )
  ctx.inject(['systemPrompt'], (child) => {
    child.effect(
      () =>
        child.systemPrompt.section({
          name: 'memory',
          order: 95,
          text: (assembly) => {
            const agent = assembly?.agent
            const sessionId = agent?.id
            const cwd = agent?.session?.header?.cwd || agent?.cwd
            const current = effectiveConfig(config ?? {}, sessionId, cwd)
            return runtime.promptFor(current.root, sessionId, cwd)
          },
        }),
      'memory: prompt section',
    )
  })
  ctx.effect(
    () => () => runtime.drain(),
    'memory: background drain',
  )
  const initial = effectiveConfig(config ?? {})
  runtime.prepare(initial.root)
}
