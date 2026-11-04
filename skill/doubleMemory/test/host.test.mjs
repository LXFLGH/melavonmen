import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdtemp, readFile, rm, writeFile, mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { Config, apply } from '../index.js'

const root = await mkdtemp(path.join(tmpdir(), 'dsh-memory-test-'))
const externalImage = path.join(root, 'source.png')
await writeFile(externalImage, Buffer.from('89504e470d0a1a0a', 'hex'))

const config = new Config({ root, autoCapture: true, captureAssistant: true, copyImages: true, injectContext: true })
const tools = new Map()
const listeners = new Map()
let promptSection

const attachments = {
  imageHostPath(ref) {
    return externalImage
  },
  async readImage(ref) {
    return { ref, data: await readFile(externalImage) }
  },
}

const ctx = {
  tools: {
    register(definition) {
      tools.set(definition.name, definition)
      return () => tools.delete(definition.name)
    },
  },
  on(name, listener) {
    if (!listeners.has(name)) listeners.set(name, [])
    listeners.get(name).push(listener)
    return () => {}
  },
  effect(callback) {
    const cleanup = callback()
    return typeof cleanup === 'function' ? cleanup : () => {}
  },
  inject(names, callback) {
    if (names.includes('systemPrompt')) callback(ctx)
  },
  get(name) {
    return name === 'attachments' ? attachments : undefined
  },
  systemPrompt: {
    section(section) {
      promptSection = section
      return () => {}
    },
  },
}

apply(ctx, config)
await new Promise((resolve) => setTimeout(resolve, 80))

const memory = tools.get('memory')
assert.ok(memory, 'memory tool registered')

async function run(args) {
  return memory.execute(args, { agent: undefined, signal: new AbortController().signal })
}

const init = await run({ action: 'init' })
assert.equal(init.ok, true)
assert.equal(init.root, path.resolve(root))
for (const file of ['soul.md', 'IDENTITY.md', 'MEMORY.md', 'date', 'session', 'pic/photo', 'pic/meme', 'pic/image']) {
  await readFile(path.join(root, file)).catch(() => {})
}

const readSoul = await run({ action: 'read', target: 'soul' })
assert.equal(readSoul.exists, true)
assert.match(readSoul.content, /Soul/)

const written = await run({ action: 'write', target: 'date', date: '2026-11-04', content: '# 2026-11-04\n\n- first note\n' })
assert.equal(written.path, 'date/2026-11-04.md')
assert.equal(await readFile(path.join(root, 'date/2026-11-04.md'), 'utf8'), '# 2026-11-04\n\n- first note\n')

const appended = await run({ action: 'append', target: 'date', date: '2026-11-04', content: '- second note' })
assert.match(await readFile(path.join(root, 'date/2026-11-04.md'), 'utf8'), /second note/)

const edited = await run({ action: 'edit', target: 'date', date: '2026-11-04', old_text: 'first note', new_text: 'renamed note' })
assert.match(edited.summary, /1 replacement/)
assert.match(await readFile(path.join(root, 'date/2026-11-04.md'), 'utf8'), /renamed note/)

const listed = await run({ action: 'list' })
assert.ok(listed.files.some((file) => file.path === 'soul.md'))
assert.ok(listed.files.some((file) => file.path === 'date/2026-11-04.md'))

const found = await run({ action: 'search', query: 'renamed' })
assert.equal(found.matches.length, 1)
assert.equal(found.matches[0].path, 'date/2026-11-04.md')

const image = await run({ action: 'add_image', target: 'meme', source_path: externalImage, name: 'smile.png' })
assert.equal(image.path, 'pic/meme/smile.png')
assert.match(image.html, /<img src="pic\/meme\/smile.png">/)
assert.equal(await readFile(path.join(root, 'pic/meme/smile.png')).then((value) => value.length), 8)

const captured = await run({ action: 'capture', speaker: 'user', text: '手动记录', images: [image.path], session_id: 'manual' })
assert.equal(captured.path, 'session/2026-11-04.json')
const manual = JSON.parse(await readFile(path.join(root, 'session/2026-11-04.json'), 'utf8'))
const manualEntry = manual.entries.find((entry) => entry.sessionId === 'manual')
assert.ok(manualEntry)
assert.match(manualEntry.html, /用户：手动记录<img src="pic\/meme\/smile.png">/)

for (const listener of listeners.get('session/event') || []) {
  listener(
    { id: 'session-test', header: { origin: 'root' } },
    {
      type: 'user/message',
      seq: 1,
      time: Date.now(),
      data: { role: 'user', source: { kind: 'user' }, content: [{ type: 'text', text: 'hello <world>' }] },
    },
  )
  listener(
    { id: 'session-test', header: { origin: 'root' } },
    {
      type: 'assistant/message',
      seq: 2,
      time: Date.now(),
      data: {
        message: {
          role: 'assistant',
          source: { kind: 'model', provider: 'test', model: 'test' },
          content: [
            { type: 'text', text: 'hi there' },
            { type: 'image', attachment: { attachmentId: 'image-1', mediaType: 'image/png', bytes: 8, width: 1, height: 1 } },
          ],
        },
      },
    },
  )
}
await new Promise((resolve) => setTimeout(resolve, 150))

const archive = JSON.parse(await readFile(path.join(root, 'session', `${new Date().toISOString().slice(0, 10)}.json`), 'utf8').catch(async () => {
  const { readdir } = await import('node:fs/promises')
  const files = (await readdir(path.join(root, 'session'))).filter((name) => name.endsWith('.json'))
  return readFile(path.join(root, 'session', files[0]), 'utf8')
}))
assert.ok(Array.isArray(archive.entries))
const userEntry = archive.entries.find((entry) => entry.sessionId === 'session-test' && entry.seq === 1)
const assistantEntry = archive.entries.find((entry) => entry.sessionId === 'session-test' && entry.seq === 2)
assert.ok(userEntry)
assert.ok(assistantEntry)
assert.match(userEntry.html, /用户：hello &lt;world&gt;/)
assert.match(assistantEntry.html, /助手：hi there<img src="pic\/image\//)
assert.equal(assistantEntry.images.length, 1)
assert.ok(await readFile(path.join(root, assistantEntry.images[0])).then((value) => value.length === 8))

const promptText = promptSection.text({ agent: { id: 'session-test' } })
assert.match(promptText, /<memory>/)
assert.match(promptText, /soul\.md/)
assert.match(promptText, /Memory root:/)

const removed = await run({ action: 'delete', target: 'date', date: '2026-11-04' })
assert.equal(removed.deleted, true)
await assert.rejects(readFile(path.join(root, 'date/2026-11-04.md')))
await assert.rejects(run({ action: 'delete', target: 'soul' }), /confirm=true/)

console.log('host functional test passed')

// --- Workspace root mode isolation test ---
const wsBase = await mkdtemp(path.join(tmpdir(), 'dsh-memory-ws-'))
const wsCwd = path.join(wsBase, 'qqbot-data')
await mkdir(wsCwd, { recursive: true })
const wsMemoryRoot = path.join(wsCwd, '.dsh-memory')

const wsConfig = new Config({ rootMode: 'workspace', autoCapture: true, captureAssistant: true, copyImages: false, injectContext: true })
const wsTools = new Map()
const wsListeners = new Map()
let wsPromptSection

const wsCtx = {
  tools: { register(def) { wsTools.set(def.name, def); return () => wsTools.delete(def.name) } },
  on(name, fn) { if (!wsListeners.has(name)) wsListeners.set(name, []); wsListeners.get(name).push(fn); return () => {} },
  effect(cb) { const d = cb(); return typeof d === 'function' ? d : () => {} },
  inject(names, cb) { if (names.includes('systemPrompt')) cb(wsCtx) },
  get() { return undefined },
  systemPrompt: { section(s) { wsPromptSection = s; return () => {} } },
}

apply(wsCtx, wsConfig)
await new Promise((r) => setTimeout(r, 80))

const wsMemory = wsTools.get('memory')
assert.ok(wsMemory, 'workspace memory tool registered')

// Simulate QQ bot session with cwd
for (const listener of wsListeners.get('session/event') || []) {
  listener(
    { id: 'qqbot-session-1', header: { origin: 'root', cwd: wsCwd } },
    { type: 'user/message', seq: 1, time: Date.now(), data: { role: 'user', source: { kind: 'user' }, content: [{ type: 'text', text: 'qqbot hello' }] } },
  )
}
await new Promise((r) => setTimeout(r, 150))

// Verify independent memory tree at <cwd>/.dsh-memory/
for (const file of ['soul.md', 'IDENTITY.md', 'MEMORY.md']) {
  assert.ok(await readFile(path.join(wsMemoryRoot, file)).then(() => true).catch(() => false), `workspace memory has ${file}`)
}
const wsArchive = await readFile(path.join(wsMemoryRoot, 'session', `${new Date().toISOString().slice(0, 10)}.json`), 'utf8').catch(() => null)
assert.ok(wsArchive, 'workspace session archive created')
assert.match(wsArchive, /qqbot hello/)
assert.ok(!wsArchive.includes('soul.md'), 'workspace archive independent from global')

// Verify prompt section uses workspace root
const wsPrompt = wsPromptSection.text({ agent: { id: 'qqbot-session-1', session: { header: { cwd: wsCwd } } } })
assert.match(wsPrompt, new RegExp(wsMemoryRoot.replace(/\\/g, '\\\\')), 'prompt references workspace root')
assert.match(wsPrompt, /<memory>/)

// Verify workspace memory is independent from global
assert.ok(await readFile(path.join(root, 'session', `${new Date().toISOString().slice(0, 10)}.json`), 'utf8').then((c) => c.includes('手动记录')).catch(() => false), 'global archive still has global entries')

console.log('workspace isolation test passed')
await rm(wsBase, { recursive: true, force: true })
await rm(root, { recursive: true, force: true })
