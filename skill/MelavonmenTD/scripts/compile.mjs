// compile.mjs — spec → 三份产物：cad spec / scene 常量 / manifest
// 用法：node compile.mjs --spec maker.spec.json --out out/
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { arg, flag } from './harness.mjs';

const SPEC = arg('spec');
const OUT = arg('out', 'out');
const CHECK = flag('check');

if (!SPEC) { console.error('需要 --spec'); process.exit(2); }
const spec = JSON.parse(fs.readFileSync(SPEC, 'utf8'));

const issues = [];
const err = (code, msg, fix, p) => issues.push({ code, severity: 'error', message: msg, fix, path: p });
const warn = (code, msg, fix, p) => issues.push({ code, severity: 'warn', message: msg, fix, path: p });

// ---- 校验 ----
if (spec.schema !== 'maker.spec/v1') err('E_SCHEMA', 'schema 必须是 maker.spec/v1', '改 schema 字段');
if (!spec.unit_mm || spec.unit_mm <= 0) err('E_UNIT_AMBIGUOUS', 'unit_mm 缺失或非正', '钉死 1 单位 = 多少 mm', 'unit_mm');
if (!Array.isArray(spec.parts) || !spec.parts.length) err('E_PART_MISSING', 'parts 为空', '至少一个件', 'parts');

const OWNERS = new Set(['cad', 'blend', 'js']);
const names = new Set();
for (const [i, p] of (spec.parts || []).entries()) {
  const at = `parts[${i}]`;
  if (!p.name) err('E_PART_MISSING', '零件缺 name', '补 name', at);
  else if (names.has(p.name)) err('E_PART_MISSING', `重名：${p.name}`, '改名', at);
  else names.add(p.name);
  if (!OWNERS.has(p.owner)) err('E_OWNER_MISSING', `owner 非法：${p.owner}`, 'cad / blend / js 之一', at + '.owner');
  if (p.bbox_mm && !Array.isArray(p.bbox_mm) && typeof p.bbox_mm === 'object') {
    for (const [k, v] of Object.entries(p.bbox_mm)) {
      if (!Array.isArray(v) || v.length !== 2 || v[0] > v[1]) err('E_SPEC_RANGE', `bbox.${k} 不是 [min,max]`, '写成 [lo,hi]', at + '.bbox_mm.' + k);
    }
  }
}
for (const [i, s] of (spec.shots || []).entries()) {
  if (!s.name) err('E_SHOT', `shots[${i}] 缺 name`, '补 name', `shots[${i}]`);
  if (s.coverage && (!Array.isArray(s.coverage) || s.coverage.length !== 2)) warn('E_SHOT', 'coverage 应是 [lo,hi]', '补区间', `shots[${i}]`);
}

const unit = spec.unit_mm || 1;
const scale = 1000 / unit; // meters → scene units
const hash = 'sha256:' + crypto.createHash('sha256')
  .update(JSON.stringify({ parts: spec.parts, unit, scene: spec.scene })).digest('hex').slice(0, 16);

console.log(`\n=== compile · ${issues.some(i => i.severity === 'error') ? 'FAIL' : 'PASS'} ===`);
console.log(`spec ${spec.name || '(unnamed)'}  unit_mm=${unit}  scale=${scale.toFixed(4)}  hash=${hash}`);
for (const i of issues) {
  console.log(`${i.severity === 'error' ? 'FAIL' : 'WARN'}  ${i.code.padEnd(18)} ${i.message}  → ${i.fix}`);
}
if (CHECK) process.exit(issues.some((i) => i.severity === 'error') ? 1 : 0);
if (issues.some((i) => i.severity === 'error')) process.exit(1);

// ---- 产物 ----
fs.mkdirSync(OUT, { recursive: true });

const cadParts = (spec.parts || []).filter((p) => p.owner === 'cad');
const cadFiles = [];
if (cadParts.length) {
  for (const p of cadParts) {
    const partSpec = {
      schema: 'maker.cad/v1',
      name: p.name,
      cad: p.cad || {},
      bbox_mm: p.bbox_mm || null,
    };
    const partPath = path.join(OUT, `spec.cad.${p.name}.json`);
    fs.writeFileSync(partPath, JSON.stringify(partSpec, null, 2));
    cadFiles.push(partPath);
  }

  const compositeCad = {
    schema: 'maker.cad/v1',
    name: spec.name || 'maker',
    parts: cadParts.map((p) => ({
      name: p.name,
      file: `spec.cad.${p.name}.json`,
      cad: p.cad || null,
      bbox_mm: p.bbox_mm || null,
    })),
  };
  fs.writeFileSync(path.join(OUT, 'spec.cad.json'), JSON.stringify(compositeCad, null, 2));
}

const constants = `// 由 compile.mjs 生成，勿手改
export const UNIT_MM = ${unit};
export const METERS_TO_SCENE = ${scale.toFixed(8)};
export const SPEC_HASH = ${JSON.stringify(hash)};
export const PARTS = ${JSON.stringify((spec.parts || []).map((p) => ({ name: p.name, owner: p.owner })), null, 2)};
`;
fs.writeFileSync(path.join(OUT, 'scene.constants.js'), constants);

const manifest = {
  schema: 'maker.manifest/v1',
  name: spec.name,
  spec_hash: hash,
  unit_mm: unit,
  scale_meters_to_scene: scale,
  parts: (spec.parts || []).map((p) => ({
    name: p.name, owner: p.owner,
    cad: p.cad || null,
    src: p.src || null,
    recipe: p.recipe || null,
    bbox_mm: p.bbox_mm || null,
    bbox_scene: p.bbox_mm
      ? Object.fromEntries(Object.entries(p.bbox_mm).map(([k, v]) =>
          [k, Array.isArray(v) ? v.map((n) => +(n / unit).toFixed(4)) : +(v / unit).toFixed(4)]))
      : null,
    tris: p.tris || null,
  })),
  shots: spec.shots || [],
  budgets: spec.budgets || {},
  assumptions: (spec.parts || []).filter((p) => p.assumed).map((p) => ({ part: p.name, note: p.assumed })),
};
fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2));

console.log(`\n产物：\n  ${path.join(OUT, 'manifest.json')}${cadParts.length ? '\n  ' + path.join(OUT, 'spec.cad.json') + '\n  ' + cadFiles.join('\n  ') : ''}\n  ${path.join(OUT, 'scene.constants.js')}`);
