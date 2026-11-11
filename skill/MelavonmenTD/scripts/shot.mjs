// shot.mjs — 按 views 文件批量出图（支持 auto 取景 / 裁剪到某个物体）
// views.json: [{"name":"hero","cam":"auto","dir":[0.4,0.3,1],"margin":0.12,"clip":"window.CRT.aio.screen"}]
//            [{"name":"front","cam":[0,0.4,6],"target":[0,-0.8,0]}]
import fs from 'node:fs';
import path from 'node:path';
import { open, shot, arg, flag } from './harness.mjs';

const URL_ = arg('url');
const VIEWS = arg('views');
const OUT = arg('out', 'shots');
const W = +arg('width', 1600);
const H = +arg('height', 1000);
const READY = arg('ready', 'window.__crtReady === true');
const ROOT = arg('root', 'window.CRT.aio.group');

if (!URL_ || !VIEWS) {
  console.error('需要 --url 与 --views');
  process.exit(2);
}
const views = JSON.parse(fs.readFileSync(VIEWS, 'utf8'));
const h = await open({ url: URL_, width: W, height: H, ready: READY, freeze: true });
await h.page.evaluate(() => {
  const el = document.getElementById('hint');
  if (el) el.style.display = 'none';
});

const results = [];
for (const v of views) {
  const info = await h.page.evaluate(({ rootExpr, view }) => {
    const ev = (s) => new Function('return (' + s + ')')();
    const root = ev(rootExpr);
    const cam = (window.CRT && window.CRT.camera) || (window.__scene && window.__scene.camera) || window.camera;
    if (!cam) throw new Error('找不到 camera（window.CRT.camera / window.__scene.camera / window.camera）');
    const ctl = (window.CRT && window.CRT.controls) || (window.__scene && window.__scene.controls) || window.controls;

    // 世界 bbox
    const V = root.position.constructor;
    let mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
    root.updateWorldMatrix(true, true);
    root.traverse((m) => {
      if (!m.isMesh || !m.geometry) return;
      const g = m.geometry;
      if (!g.boundingBox) g.computeBoundingBox();
      const b = g.boundingBox;
      for (let i = 0; i < 8; i++) {
        const p = new V(i & 1 ? b.max.x : b.min.x, i & 2 ? b.max.y : b.min.y, i & 4 ? b.max.z : b.min.z)
          .applyMatrix4(m.matrixWorld);
        mn = [Math.min(mn[0], p.x), Math.min(mn[1], p.y), Math.min(mn[2], p.z)];
        mx = [Math.max(mx[0], p.x), Math.max(mx[1], p.y), Math.max(mx[2], p.z)];
      }
    });
    const center = new V((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2);
    const radius = 0.5 * Math.hypot(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]);

    let target = center.clone();
    if (view.target) target = new V(...view.target);

    if (view.cam === 'auto' || !view.cam) {
      const dir = new V(...(view.dir || [0.4, 0.28, 1])).normalize();
      const vfov = (cam.fov * Math.PI) / 180;
      const hfov = 2 * Math.atan(Math.tan(vfov / 2) * cam.aspect);
      const d = radius / Math.sin(Math.min(vfov, hfov) / 2) * (1 + (view.margin ?? 0.12));
      cam.position.copy(target).addScaledVector(dir, d);
    } else {
      cam.position.set(...view.cam);
    }
    if (ctl) { ctl.enableDamping = false; ctl.minDistance = 0; ctl.maxDistance = 1e6; ctl.target.copy(target); ctl.update(); } else cam.lookAt(target);
    cam.updateMatrixWorld();

    // 可选：裁剪到某个物体的投影矩形
    let clip = null;
    if (view.clip) {
      const obj = ev(view.clip);
      obj.updateWorldMatrix(true, true);
      let cmn = [Infinity, Infinity, Infinity], cmx = [-Infinity, -Infinity, -Infinity];
      obj.traverse((m) => {
        if (!m.isMesh || !m.geometry) return;
        const g = m.geometry;
        if (!g.boundingBox) g.computeBoundingBox();
        for (let i = 0; i < 8; i++) {
          const p = new V(i & 1 ? g.boundingBox.max.x : g.boundingBox.min.x,
            i & 2 ? g.boundingBox.max.y : g.boundingBox.min.y,
            i & 4 ? g.boundingBox.max.z : g.boundingBox.min.z).applyMatrix4(m.matrixWorld);
          cmn = [Math.min(cmn[0], p.x), Math.min(cmn[1], p.y), Math.min(cmn[2], p.z)];
          cmx = [Math.max(cmx[0], p.x), Math.max(cmx[1], p.y), Math.max(cmx[2], p.z)];
        }
      });
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (let i = 0; i < 8; i++) {
        const p = new V(i & 1 ? cmx[0] : cmn[0], i & 2 ? cmx[1] : cmn[1], i & 4 ? cmx[2] : cmn[2]).project(cam);
        x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x);
        y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y);
      }
      clip = {
        x: (x0 * 0.5 + 0.5) * innerWidth, y: (-y1 * 0.5 + 0.5) * innerHeight,
        width: (x1 - x0) * 0.5 * innerWidth, height: (y1 - y0) * 0.5 * innerHeight,
      };
    }
    return { clip, cam: cam.position.toArray().map((n) => +n.toFixed(3)), target: target.toArray().map((n) => +n.toFixed(3)), radius: +radius.toFixed(3) };
  }, { rootExpr: ROOT, view: v });

  await new Promise((r) => setTimeout(r, 350));
  const file = path.join(OUT, v.name + '.png');
  await shot(h.page, file, info.clip);
  results.push({ name: v.name, file, ...info });
  console.log('shot', v.name, '→', file, info.clip ? `clip ${Math.round(info.clip.width)}x${Math.round(info.clip.height)}` : '', `cam ${info.cam.join(',')} target ${info.target.join(',')}`);
}

if (flag('json')) {
  const j = arg('json', path.join(OUT, 'shots.json'));
  fs.writeFileSync(j, JSON.stringify(results, null, 2));
  console.log('manifest →', j);
}
await h.close();
