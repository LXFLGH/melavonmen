// doctor.mjs — 环境体检：node / puppeteer / chrome / blender / cad
import fs from 'node:fs';
import path from 'node:path';
import { findChrome, loadPuppeteer, findBlender, runBlender, flag, arg } from './harness.mjs';

const rows = [];
const add = (name, ok, detail, extra = {}) => rows.push({ name, ok, detail, ...extra });

add('node', true, process.version);

let puppeteerOk = false;
try {
  loadPuppeteer();
  puppeteerOk = true;
  add('puppeteer-core', true, '已加载 (用于 S4 帧级度量)');
} catch (e) {
  add('puppeteer-core', false, '可选：仅帧级度量需要（npm i -D puppeteer-core）');
}

let chromeOk = false;
try {
  const cr = findChrome();
  chromeOk = true;
  add('chrome', true, cr);
} catch (e) {
  add('chrome', false, '可选：设置 CHROME_PATH 环境变量');
}

const bl = findBlender();
add('blender', !!bl, bl || '可选：没有就仅跑 js 件');

// ---- 内置 CAD 引擎体检 ----
let cadOk = false;
let cadDetail = '未就绪 (需要 Blender 支撑 CSG 实体生成)';
if (bl) {
  try {
    const testPy = "import bpy, bmesh; print('CAD_ENGINE_OK:' + bpy.app.version_string)";
    const res = runBlender("-c", [], {
      timeout: 10000,
    });
    // 测试简单的 python-expr
    const p = (await import('node:child_process')).spawnSync(bl, ['--background', '--python-expr', testPy], {
      encoding: 'utf-8',
      timeout: 10000,
    });
    if (p.status === 0 && p.stdout && p.stdout.includes('CAD_ENGINE_OK')) {
      cadOk = true;
      cadDetail = `内置 CSG 引擎就绪 (Blender ${p.stdout.match(/CAD_ENGINE_OK:(.+)/)?.[1]?.trim() || 'OK'})`;
    } else {
      cadDetail = 'Blender 可用，但 Python 执行异常';
    }
  } catch (e) {
    cadDetail = `CAD 检测失败: ${e.message}`;
  }
}
add('cad', cadOk, cadDetail);

const pad = Math.max(...rows.map((r) => r.name.length));
console.log('\n=== MelavonmenTD · doctor ===');
for (const r of rows) {
  const tag = r.ok ? 'OK  ' : (r.name === 'node' ? 'FAIL' : 'WARN');
  console.log(`${tag}  ${r.name.padEnd(pad)}  ${r.detail}`);
}

const hard = rows.filter((r) => !r.ok && ['node'].includes(r.name));
const readyCount = rows.filter((r) => r.ok).length;
console.log(`\n${readyCount}/${rows.length} 可用` + (hard.length ? `，缺关键依赖: ${hard.map((r) => r.name).join('/')}` : '，流水线就绪'));

if (flag('json')) {
  const out = arg('json', 'out/doctor.json');
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  fs.writeFileSync(
    out,
    JSON.stringify(
      {
        schema: 'maker.receipt/v1',
        gate: 'doctor',
        verdict: hard.length ? 'fail' : 'pass',
        summary: `${readyCount}/${rows.length} components available`,
        rows,
        environment: {
          platform: process.platform,
          node: process.version,
          blender_path: bl,
        },
      },
      null,
      2
    )
  );
  console.log('receipt →', out);
}

process.exit(hard.length ? 1 : 0);
