// frame.mjs — 帧级度量：覆盖率 / texel 密度 / 预算，产出 receipt
// 用法：
//   node frame.mjs --url file:///…/index.html --root window.CRT.aio.group \
//     --ready 'window.__crtReady===true' --texel 'screen=window.CRT.aio.screen:1.2' \
//     --budget calls=250,tris=150000,mats=200 --json out/frame.json
import fs from 'node:fs';
import path from 'node:path';
import { open, arg, flag } from './harness.mjs';

const URL_ = arg('url');
const ROOT = arg('root', 'window.CRT.aio.group');
const READY = arg('ready', 'window.__crtReady === true');
const W = +arg('width', 1600);
const H = +arg('height', 1000);
const DPR = +arg('dpr', 1);
const TEXEL = arg('texel', '');
const BUDGET = arg('budget', '');
const JSON_OUT = arg('json', '');
const VERBOSE = flag('verbose');

if (!URL_) {
  console.error('缺少 --url');
  process.exit(2);
}

const texelTargets = TEXEL
  ? TEXEL.split(',').map((s) => {
      const m = s.match(/^([^=]+)=(.+):([\d.]+)$/);
      if (!m) throw new Error('--texel 格式：name=expr:min');
      return { name: m[1], expr: m[2], min: +m[3] };
    })
  : [];

const budget = {};
for (const kv of BUDGET.split(',').filter(Boolean)) {
  const [k, v] = kv.split('=');
  budget[k] = +v;
}

const h = await open({ url: URL_, width: W, height: H, dpr: DPR, ready: READY, freeze: true });

const data = await h.page.evaluate(({ rootExpr, texelTargets, vw, vh }) => {
  const ev = (src) => new Function('return (' + src + ')')();
  const root = ev(rootExpr);
  if (!root) throw new Error('root 表达式取到空值：' + rootExpr);

  const V = root.position.constructor;
  const cam = (window.CRT && window.CRT.camera) || (window.__scene && window.__scene.camera);
  if (!cam) throw new Error('找不到 camera（window.CRT.camera）');
  cam.updateMatrixWorld();

  // ---- 世界 bbox（不依赖 Box3 导出） ----
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  let meshes = 0;
  root.updateWorldMatrix(true, true);
  root.traverse((m) => {
    if (!m.isMesh || !m.geometry) return;
    meshes++;
    const g = m.geometry;
    if (!g.boundingBox) g.computeBoundingBox();
    const b = g.boundingBox;
    for (let i = 0; i < 8; i++) {
      const p = new V(
        i & 1 ? b.max.x : b.min.x,
        i & 2 ? b.max.y : b.min.y,
        i & 4 ? b.max.z : b.min.z
      ).applyMatrix4(m.matrixWorld);
      min[0] = Math.min(min[0], p.x); max[0] = Math.max(max[0], p.x);
      min[1] = Math.min(min[1], p.y); max[1] = Math.max(max[1], p.y);
      min[2] = Math.min(min[2], p.z); max[2] = Math.max(max[2], p.z);
    }
  });

  // ---- 投影 ----
  const rect = (objMin, objMax) => {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, any = false;
    for (let i = 0; i < 8; i++) {
      const w = new V(i & 1 ? objMax[0] : objMin[0], i & 2 ? objMax[1] : objMin[1], i & 4 ? objMax[2] : objMin[2]);
      const p = w.clone().project(cam);
      if (p.z < -1 || p.z > 1) continue;
      any = true;
      x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x);
      y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y);
    }
    if (!any) return null;
    return {
      x: (x0 * 0.5 + 0.5) * vw, y: (-y1 * 0.5 + 0.5) * vh,
      width: (x1 - x0) * 0.5 * vw, height: (y1 - y0) * 0.5 * vh,
    };
  };
  const r = rect(min, max);
  const coverage = r ? (r.width * r.height) / (vw * vh) : 0;

  // ---- 预算 ----
  const ren = (window.CRT && window.CRT.renderer) || (window.__scene && window.__scene.renderer);
  const rendererRef = ren;
  const info = ren ? { calls: ren.info.render.calls, tris: ren.info.render.triangles } : null;
  const texOf = (mat) => {
    if (!mat) return null;
    if (mat.map && mat.map.image && mat.map.image.width) return mat.map;
    if (mat.uniforms) {
      for (const k in mat.uniforms) {
        const v = mat.uniforms[k] && mat.uniforms[k].value;
        if (v && v.image && v.image.width) return v;
      }
    }
    return null;
  };
  let objs = 0, geos = new Set(), mats = new Set(), texs = new Set(), texBytes = 0;
  const geoCount = new Map();
  const sceneRoot = (window.CRT && window.CRT.scene) || (rendererRef && rendererRef.__scene) || cam.parent || null;
  const scanRoot = sceneRoot || root;
  scanRoot.traverse((m) => {
    if (!m.isMesh) return;
    objs++;
    geos.add(m.geometry.uuid);
    geoCount.set(m.geometry.uuid, (geoCount.get(m.geometry.uuid) || 0) + 1);
    const ms = Array.isArray(m.material) ? m.material : [m.material];
    for (const mat of ms) {
      if (!mat) continue;
      mats.add(mat.uuid);
      for (const k of ['map', 'normalMap', 'roughnessMap', 'bumpMap', 'emissiveMap']) {
        const t = mat[k];
        if (t && t.image && t.image.width && !texs.has(t.uuid)) {
          texs.add(t.uuid);
          texBytes += t.image.width * t.image.height * 4;
        }
      }
      const u = texOf(mat);
      if (u && !texs.has(u.uuid)) { texs.add(u.uuid); texBytes += u.image.width * u.image.height * 4; }
    }
  });
  const reuseTop = [...geoCount.values()].sort((a, b) => b - a).slice(0, 5);

  // ---- texel ----
  const texels = texelTargets.map((t) => {
    let mesh;
    try { mesh = ev(t.expr); } catch (e) { return { name: t.name, error: String(e.message || e), min: t.min }; }
    if (!mesh) return { name: t.name, error: 'expr 取到空值', min: t.min };
    if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
    const b = mesh.geometry.boundingBox;
    mesh.updateWorldMatrix(true, false);
    let mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < 8; i++) {
      const p = new V(i & 1 ? b.max.x : b.min.x, i & 2 ? b.max.y : b.min.y, i & 4 ? b.max.z : b.min.z)
        .applyMatrix4(mesh.matrixWorld);
      mn = [Math.min(mn[0], p.x), Math.min(mn[1], p.y), Math.min(mn[2], p.z)];
      mx = [Math.max(mx[0], p.x), Math.max(mx[1], p.y), Math.max(mx[2], p.z)];
    }
    const rr = rect(mn, mx);
    const texW = (texOf(mesh.material) || { image: {} }).image.width || 0;
    return {
      name: t.name, min: t.min, texW,
      screenW: rr ? rr.width : 0,
      ratio: rr && rr.width > 0 && texW > 0 ? texW / rr.width : 0,
    };
  });

  return { rect: r, coverage, bbox: { min, max }, meshes, info, objs, geos: geos.size, mats: mats.size, texs: texs.size, texMB: texBytes / 1048576, reuseTop, texels };
}, { rootExpr: ROOT, texelTargets, vw: W, vh: H });

await h.close();

// ---------------- receipt ----------------
const checks = [];
const push = (id, value, expected, ok, severity = 'error') => checks.push({ id, value, expected, ok, severity });

const covRange = arg('coverage', '');
if (covRange) {
  const [lo, hi] = covRange.split('..').map(Number);
  push('frame.coverage', +data.coverage.toFixed(3), `${lo}..${hi}`,
    data.coverage >= lo && data.coverage <= hi);
} else {
  push('frame.coverage', +data.coverage.toFixed(3), 'report-only', true, 'info');
}

for (const t of data.texels) {
  if (t.error) { push('texel.' + t.name, 0, `>=${t.min}`, false); continue; }
  push('texel.' + t.name, +t.ratio.toFixed(2), `>=${t.min}`, t.ratio >= t.min);
}

if (data.info) {
  if (budget.calls) push('budget.calls', data.info.calls, `<=${budget.calls}`, data.info.calls <= budget.calls);
  if (budget.tris) push('budget.tris', data.info.tris, `<=${budget.tris}`, data.info.tris <= budget.tris);
  push('budget.reuse', data.reuseTop[0] || 0, '>=3', (data.reuseTop[0] || 0) >= 3, 'warn');
  // 逐键字符贴图这类场景天然一物一材质，硬编码 40 会误报 degraded；允许 --budget mats=N 覆盖。
  const matsLimit = budget.mats || 40;
  push('budget.materials', data.mats, `<=${matsLimit}`, data.mats <= matsLimit, 'warn');
}

const failed = checks.filter((c) => !c.ok && c.severity === 'error');
const degraded = checks.filter((c) => !c.ok && c.severity === 'warn');
const verdict = failed.length ? 'fail' : degraded.length ? 'degraded' : 'pass';

const receipt = {
  schema: 'maker.receipt/v1',
  gate: 'frame',
  level: arg('level', 'standard'),
  verdict,
  build: { url: URL_, viewport: [W, H], dpr: DPR, freeze: true, root: ROOT },
  checks,
  metrics: data,
  skipped: [],
};

console.log(`\n=== frame · ${verdict.toUpperCase()} ===`);
console.log(`bbox  ${data.bbox.min.map((n) => n.toFixed(2)).join(' / ')}  →  ${data.bbox.max.map((n) => n.toFixed(2)).join(' / ')}`);
console.log(`coverage ${(data.coverage * 100).toFixed(1)}%   rect ${data.rect ? Math.round(data.rect.width) + 'x' + Math.round(data.rect.height) + 'px' : 'n/a'}`);
if (data.info) console.log(`calls ${data.info.calls}   tris ${data.info.tris}   geos ${data.geos}   mats ${data.mats}   tex ${data.texs} (${data.texMB.toFixed(1)} MB)`);
for (const t of data.texels) {
  if (t.error) console.log(`texel ${t.name}: ERROR ${t.error}`);
  else console.log(`texel ${t.name}: ${t.ratio.toFixed(2)}  (tex ${t.texW}px / screen ${Math.round(t.screenW)}px)`);
}
console.log('');
for (const c of checks) console.log(`${c.ok ? 'PASS' : c.severity === 'warn' ? 'WARN' : 'FAIL'}  ${c.id.padEnd(22)} ${c.value}  期望 ${c.expected}`);
if (VERBOSE) console.log('\n几何复用前五：', data.reuseTop.join(', '));

if (JSON_OUT) {
  fs.mkdirSync(path.dirname(path.resolve(JSON_OUT)), { recursive: true });
  fs.writeFileSync(JSON_OUT, JSON.stringify(receipt, null, 2));
  console.log('\nreceipt →', JSON_OUT);
}
process.exit(failed.length ? 1 : 0);
