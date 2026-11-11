// glbcheck.mjs — 校验导出的 GLB：单位换算后的 bbox 是否等于 spec 的 mm 尺寸
// 用法：node glbcheck.mjs --glb out/panel.glb --spec maker.spec.json --part panel
import fs from 'node:fs';
import { arg, flag } from './harness.mjs';

const GLB = arg('glb');
const SPEC = arg('spec');
const PART = arg('part');
if (!GLB) { console.error('需要 --glb'); process.exit(2); }

const buf = fs.readFileSync(GLB);
if (buf.readUInt32LE(0) !== 0x46546c67) { console.error('不是 GLB（magic 不符）'); process.exit(2); }
const version = buf.readUInt32LE(4);
let off = 12;
let json = null;
let binLen = 0;
while (off < buf.length) {
  const len = buf.readUInt32LE(off);
  const type = buf.readUInt32LE(off + 4);
  const data = buf.subarray(off + 8, off + 8 + len);
  if (type === 0x4e4f534a) json = JSON.parse(new TextDecoder().decode(data));
  if (type === 0x004e4942) binLen = len;
  off += 8 + len + ((4 - (len % 4)) % 4);
}
if (!json) { console.error('GLB 里没有 JSON chunk'); process.exit(2); }

// POSITION accessor 的 min/max 并集（导出时已 export_apply，忽略节点变换）
const mn = [Infinity, Infinity, Infinity];
const mx = [-Infinity, -Infinity, -Infinity];
let prims = 0, tris = 0;
for (const mesh of json.meshes || []) {
  for (const p of mesh.primitives || []) {
    const acc = json.accessors[p.attributes.POSITION];
    if (!acc || !acc.min || !acc.max) continue;
    prims++;
    for (let i = 0; i < 3; i++) { mn[i] = Math.min(mn[i], acc.min[i]); mx[i] = Math.max(mx[i], acc.max[i]); }
    if (p.indices != null) tris += json.accessors[p.indices].count / 3;
  }
}
const sizeM = [mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]];
const sizeMm = sizeM.map((n) => n * 1000);

let expected = null;
if (SPEC && fs.existsSync(SPEC)) {
  const spec = JSON.parse(fs.readFileSync(SPEC, 'utf8'));
  const part = (spec.parts || []).find((p) => p.name === PART) || (spec.parts || [])[0];
  expected = part && part.bbox_mm ? part.bbox_mm : null;
}

console.log(`\n=== glbcheck · ${PART || json.meshes?.[0]?.name || 'mesh'} ===`);
console.log(`glTF ${version}   prims ${prims}   tris ${Math.round(tris)}   bin ${(binLen / 1024).toFixed(0)} KB`);
console.log(`bbox(m)  ${sizeM.map((n) => n.toFixed(4)).join(' × ')}`);
console.log(`bbox(mm) ${sizeMm.map((n) => n.toFixed(1)).join(' × ')}`);

let fail = 0;
if (expected) {
  for (const [k, idx] of [['x', 0], ['y', 1], ['z', 2]]) {
    const v = expected[k];
    if (!Array.isArray(v)) continue;
    const ok = sizeMm[idx] >= v[0] && sizeMm[idx] <= v[1];
    if (!ok) fail++;
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${k}: ${sizeMm[idx].toFixed(1)} mm  期望 [${v[0]}, ${v[1]}]`);
  }
} else {
  console.log('WARN  没给 --spec/--part，只报告不判定');
}

if (flag('json')) {
  fs.writeFileSync(arg('json', 'out/glbcheck.json'), JSON.stringify({
    schema: 'maker.receipt/v1', gate: 'glbcheck', verdict: fail ? 'fail' : 'pass',
    glb: GLB, bbox_m: sizeM, bbox_mm: sizeMm, tris: Math.round(tris), expected,
  }, null, 2));
  console.log('receipt →', arg('json', 'out/glbcheck.json'));
}
process.exit(fail ? 1 : 0);
