// harness.mjs — 共享的跨平台引导：找 Chrome、解析 puppeteer、定位 Blender、收报错
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SKILL_ROOT = path.resolve(__dirname, '..');

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  // Windows Google Chrome
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  path.join(process.env.LOCALAPPDATA || '', 'Google/Chrome/Application/chrome.exe'),
  // Windows Microsoft Edge
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  path.join(process.env.LOCALAPPDATA || '', 'Microsoft/Edge/Application/msedge.exe'),
  // Windows Brave / Chromium
  'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe',
  // Linux
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/snap/bin/chromium',
  // macOS
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
].filter(Boolean);

export function findChrome() {
  for (const p of CHROME_CANDIDATES) {
    if (p && fs.existsSync(p)) return p;
  }
  throw new Error('找不到 Chrome/Edge/Chromium，请设置 CHROME_PATH 环境变量');
}

/** 从 cwd 往上找 node_modules，或从 skill 目录寻找 puppeteer-core */
export function loadPuppeteer() {
  const dirs = [];
  let cur = process.cwd();
  for (let i = 0; i < 8; i++) {
    dirs.push(cur);
    const up = path.dirname(cur);
    if (up === cur) break;
    cur = up;
  }
  dirs.push(SKILL_ROOT);

  for (const d of dirs) {
    const pkg = path.join(d, 'node_modules', 'puppeteer-core', 'package.json');
    if (fs.existsSync(pkg)) {
      const req = createRequire(path.join(d, 'noop.js'));
      return req('puppeteer-core');
    }
  }

  try {
    const req = createRequire(path.join(process.cwd(), 'noop.js'));
    return req('puppeteer-core');
  } catch { /* ignore */ }

  throw new Error('找不到 puppeteer-core（请在被测项目中运行 npm i -D puppeteer-core）');
}

const BLENDER_CANDIDATES = [
  process.env.BLENDER_PATH,
  'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe',
  'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe',
  'C:/Program Files/Blender Foundation/Blender 5.0/blender.exe',
  'C:/Program Files/Blender Foundation/Blender 4.3/blender.exe',
  'C:/Program Files/Blender Foundation/Blender 4.2/blender.exe',
  'C:/Program Files/Blender Foundation/Blender 4.1/blender.exe',
  'C:/Program Files/Blender Foundation/Blender 4.0/blender.exe',
  'C:/Program Files/Blender Foundation/Blender 3.6/blender.exe',
  '/usr/bin/blender',
  '/snap/bin/blender',
  '/Applications/Blender.app/Contents/MacOS/Blender',
].filter(Boolean);

export function findBlender() {
  for (const p of BLENDER_CANDIDATES) {
    if (p && fs.existsSync(p)) return p;
  }
  return null;
}

/** 运行无头 Blender 脚本 */
export function runBlender(scriptPath, scriptArgs = [], opts = {}) {
  const blender = findBlender();
  if (!blender) {
    throw new Error('未检测到 Blender 可执行文件，请安装 Blender 或设置 BLENDER_PATH');
  }

  const args = [
    '--background',
    '--factory-startup',
    '--python',
    scriptPath,
    '--',
    ...scriptArgs,
  ];

  return spawnSync(blender, args, {
    cwd: opts.cwd || process.cwd(),
    encoding: 'utf-8',
    timeout: opts.timeout || 180000,
    maxBuffer: 10 * 1024 * 1024,
  });
}

export function fileUrl(p) {
  const abs = path.resolve(p).split(path.sep).join('/');
  return 'file:///' + (abs.startsWith('/') ? abs.slice(1) : abs);
}

/**
 * @param {{url:string,width?:number,height?:number,dpr?:number,ready?:string,timeout?:number,freeze?:boolean}} o
 */
export async function open(o) {
  const puppeteer = loadPuppeteer();
  const browser = await puppeteer.launch({
    executablePath: findChrome(),
    headless: true,
    args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--hide-scrollbars', '--force-device-scale-factor=1'],
    defaultViewport: { width: o.width || 1600, height: o.height || 1000, deviceScaleFactor: o.dpr || 1 },
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e.message || e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

  let url = o.url;
  if (o.freeze && !/freeze=1/.test(url)) url += (url.includes('?') ? '&' : '?') + 'freeze=1';
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });

  const ready = o.ready || 'window.__crtReady === true';
  try {
    await page.waitForFunction(ready, { timeout: o.timeout || 60000, polling: 120 });
  } catch (e) {
    const hint = errors.length ? '\n页面报错：\n  ' + errors.slice(0, 4).join('\n  ') : '';
    await browser.close();
    throw new Error(`等待 ready 超时：${ready}${hint}`);
  }
  // 让首帧动画/自检稳定
  await new Promise((r) => setTimeout(r, 900));
  return { browser, page, errors, close: () => browser.close() };
}

/** 在页面里求值一个表达式字符串（可访问 window） */
export async function evalExpr(page, expr) {
  return page.evaluate((src) => {
    // eslint-disable-next-line no-new-func
    return new Function('return (' + src + ')')();
  }, expr);
}

export async function shot(page, file, clip) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const opt = { path: file };
  if (clip) {
    opt.clip = {
      x: Math.round(clip.x), y: Math.round(clip.y),
      width: Math.max(1, Math.round(clip.width)), height: Math.max(1, Math.round(clip.height)),
    };
  }
  await page.screenshot(opt);
  return file;
}

export function arg(name, dflt) {
  const i = process.argv.indexOf('--' + name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : dflt;
}

export function flag(name) {
  return process.argv.includes('--' + name);
}

export { SKILL_ROOT };
