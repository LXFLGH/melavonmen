// cad.mjs — 内置参数化 CAD 几何构建、度量、验证与交付
// 用法：
//   node cad.mjs --spec maker.spec.json [--out out/] [--part panel] [--formats glb,step] [--json out/cad.receipt.json]
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { findBlender, runBlender, arg, flag } from './harness.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CAD_WORKER = path.join(__dirname, 'cad_worker.py');

const SPEC_FILE = arg('spec');
const OUT_DIR = arg('out', 'out');
const PART_FILTER = arg('part');
const FORMATS = arg('formats', 'glb');
const ALLOW_DEGRADED = flag('allow-degraded');
const RECEIPT_OUT = arg('json');

if (!SPEC_FILE) {
  console.error('缺少 --spec 参数');
  console.error('用法: node cad.mjs --spec maker.spec.json [--out out/] [--part <name>]');
  process.exit(2);
}

if (!fs.existsSync(SPEC_FILE)) {
  console.error(`spec 文件不存在: ${SPEC_FILE}`);
  process.exit(2);
}

const blender = findBlender();
if (!blender) {
  console.error('\n[E_NO_BLENDER] 未找到 Blender 可执行程序！');
  console.error('CAD 实体生成器需要 Blender 无头模式进行 CSG 布尔运算与模型导出。');
  console.error('请安装 Blender 或设置 BLENDER_PATH 环境变量。');
  process.exit(1);
}

const rawSpec = JSON.parse(fs.readFileSync(SPEC_FILE, 'utf8'));
let cadParts = [];
let specHash = '';

const unit = rawSpec.unit_mm || 1;
specHash = 'sha256:' + crypto.createHash('sha256')
  .update(JSON.stringify({ parts: rawSpec.parts, unit, scene: rawSpec.scene })).digest('hex').slice(0, 16);

const parts = rawSpec.parts || [];
cadParts = parts.filter((p) => p.owner === 'cad');
if (PART_FILTER) {
  cadParts = cadParts.filter((p) => p.name === PART_FILTER);
}

if (cadParts.length === 0) {
  if (PART_FILTER) {
    console.error(`未在 spec 中找到名为 "${PART_FILTER}" 的 cad 零件`);
    process.exit(1);
  }
  console.log('spec 中无 owner="cad" 零件，无需运行 CAD 构建。');
  process.exit(0);
}

fs.mkdirSync(OUT_DIR, { recursive: true });

const tasks = cadParts.map((p) => ({
  name: p.name,
  cad: p.cad || {},
  bbox_mm: p.bbox_mm || null,
  formats: (p.cad && p.cad.formats) || FORMATS,
}));

const payloadPath = path.join(OUT_DIR, '__cad_payload.json');
fs.writeFileSync(payloadPath, JSON.stringify({ unit_mm: unit, tasks }, null, 2));

console.log(`\n=== MelavonmenTD · CAD (Built-in Geometry Engine) ===`);
console.log(`spec: ${path.basename(SPEC_FILE)}  hash: ${specHash}  parts: ${tasks.map((t) => t.name).join(', ')}`);
console.log(`worker: ${blender}`);

const workerArgs = ['--spec', path.resolve(payloadPath), '--out', path.resolve(OUT_DIR)];
if (ALLOW_DEGRADED) workerArgs.push('--allow-degraded');

const res = runBlender(CAD_WORKER, workerArgs);

// 清理临时 payload
try { fs.unlinkSync(payloadPath); } catch { /* ignore */ }

if (res.status !== 0) {
  console.error('CAD worker 执行失败 (exit ' + res.status + ')');
  if (res.stderr) console.error(res.stderr.trim());
  process.exit(1);
}

const stdout = res.stdout || '';
const match = stdout.match(/CAD_RESULT_JSON:(.+)/);
if (!match) {
  console.error('未收到 CAD worker 的有效输出：\n', stdout.slice(-1000));
  process.exit(1);
}

let pyData = null;
try {
  pyData = JSON.parse(match[1]);
} catch (e) {
  console.error('解析 CAD 输出 JSON 失败:', e.message);
  process.exit(1);
}

const allPass = pyData.ok;
const allFiles = [];
const checks = [];

for (const r of pyData.results) {
  const vTag = r.verdict === 'pass' ? 'PASS' : (r.verdict === 'degraded' ? 'DEGR' : 'FAIL');
  console.log(`\n[${vTag}] Part: ${r.name}  verdict: ${r.verdict}`);
  if (r.facts) {
    const b = r.facts.bbox_mm;
    const bStr = b ? `${b[0].toFixed(1)} × ${b[1].toFixed(1)} × ${b[2].toFixed(1)} mm` : 'N/A';
    console.log(`       bbox: ${bStr}  V=${r.facts.volume_mm3?.toFixed(1) || 0} mm³  closed=${r.facts.closed}  genus=${r.facts.genus}  tris=${r.facts.tris}`);
  }
  if (r.files && r.files.length) {
    console.log(`       产出文件:`);
    for (const f of r.files) {
      console.log(`         - [${f.format}] ${f.path} (${(f.bytes / 1024).toFixed(1)} KB)`);
      allFiles.push(f.path);
    }
  }
  if (r.issues && r.issues.length) {
    for (const iss of r.issues) {
      console.log(`       ⚠ ${iss.code}: ${iss.message}`);
    }
  }
  checks.push({
    id: `cad.${r.name}`,
    verdict: r.verdict,
    ok: r.verdict === 'pass' || (ALLOW_DEGRADED && r.verdict === 'degraded'),
    facts: r.facts,
    files: r.files,
  });
}

const receipt = {
  schema: 'maker.receipt/v1',
  gate: 'cad',
  verdict: allPass ? 'pass' : 'fail',
  spec_hash: specHash,
  backend: {
    name: 'builtin_blender_cad',
    blender: blender,
  },
  checks,
  files: allFiles,
  timestamp: new Date().toISOString(),
};

const receiptFile = RECEIPT_OUT || path.join(OUT_DIR, 'cad.receipt.json');
fs.writeFileSync(receiptFile, JSON.stringify(receipt, null, 2));
console.log(`\nCAD receipt → ${receiptFile}`);

process.exit(allPass ? 0 : 1);
