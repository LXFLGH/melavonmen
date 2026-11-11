// compare.mjs — 两张图比剪影 IoU / 像素差（只在 freeze 相机位下有意义）
// 用法：node compare.mjs --a shots/hero-mask.png --b ref/ref-mask.png [--threshold 0.5]
// 说明：--b 必须是剪影图（白底黑主体或黑底白主体都可以，脚本按亮度二值化后取反比）
import fs from 'node:fs';
import path from 'node:path';
import { loadPuppeteer, findChrome, arg, flag } from './harness.mjs';

const A = arg('a');
const B = arg('b');
const T = +arg('threshold', 0.5);
if (!A || !B) { console.error('需要 --a 与 --b'); process.exit(2); }

const toDataUrl = (p) => {
  const ext = path.extname(p).toLowerCase();
  const mime = ext === '.jpg' || ext === '.jpeg' ? 'image/jpeg' : 'image/png';
  return `data:${mime};base64,` + fs.readFileSync(p).toString('base64');
};

const puppeteer = loadPuppeteer();
const browser = await puppeteer.launch({
  executablePath: findChrome(), headless: true,
  args: ['--no-sandbox', '--hide-scrollbars'],
});
const page = await browser.newPage();

const res = await page.evaluate(async ({ a, b, t }) => {
  const load = (src) => new Promise((ok, no) => {
    const img = new Image();
    img.onload = () => ok(img);
    img.onerror = no;
    img.src = src;
  });
  const [ia, ib] = await Promise.all([load(a), load(b)]);
  const W = Math.min(ia.width, ib.width), H = Math.min(ia.height, ib.height);
  const read = (img) => {
    const c = document.createElement('canvas');
    c.width = W; c.height = H;
    const x = c.getContext('2d');
    x.drawImage(img, 0, 0, W, H);
    return x.getImageData(0, 0, W, H).data;
  };
  const da = read(ia), db = read(ib);
  // 用四角平均色当背景，前景 = 与背景差异大于阈值
  const bg = (d) => {
    const pts = [0, (W - 1) * 4, (H - 1) * W * 4, ((H - 1) * W + W - 1) * 4];
    let r = 0, g = 0, bb = 0;
    for (const i of pts) { r += d[i]; g += d[i + 1]; bb += d[i + 2]; }
    return [r / 4, g / 4, bb / 4];
  };
  const mask = (d) => {
    const bgc = bg(d);
    const m = new Uint8Array(W * H);
    for (let i = 0, p = 0; i < W * H; i++, p += 4) {
      const diff = (Math.abs(d[p] - bgc[0]) + Math.abs(d[p + 1] - bgc[1]) + Math.abs(d[p + 2] - bgc[2])) / 765;
      m[i] = diff > t ? 1 : 0;
    }
    return m;
  };
  const ma = mask(da), mb = mask(db);
  let inter = 0, uni = 0, onlyA = 0, onlyB = 0;
  for (let i = 0; i < W * H; i++) {
    if (ma[i] && mb[i]) inter++;
    if (ma[i] || mb[i]) uni++;
    if (ma[i] && !mb[i]) onlyA++;
    if (!ma[i] && mb[i]) onlyB++;
  }
  const areaA = ma.reduce((s, v) => s + v, 0);
  const areaB = mb.reduce((s, v) => s + v, 0);
  return {
    size: [W, H], iou: uni ? inter / uni : 0,
    coverageA: areaA / (W * H), coverageB: areaB / (W * H),
    onlyA: onlyA / (W * H), onlyB: onlyB / (W * H),
  };
}, { a: toDataUrl(A), b: toDataUrl(B), t: T });
await browser.close();

const min = +arg('min', 0.9);
const ok = res.iou >= min;
console.log('\n=== compare ===');
console.log(`尺寸 ${res.size[0]}x${res.size[1]}  阈值 ${T}  前景占比 A=${(res.coverageA * 100).toFixed(1)}%  B=${(res.coverageB * 100).toFixed(1)}%`);
console.log(`IoU ${res.iou.toFixed(3)}  期望 >= ${min}  ${ok ? 'PASS' : 'FAIL'}`);
console.log(`A 多出 ${(res.onlyA * 100).toFixed(1)}%   B 多出 ${(res.onlyB * 100).toFixed(1)}%`);

if (flag('json')) {
  const out = arg('json', 'out/compare.json');
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  fs.writeFileSync(out, JSON.stringify({
    schema: 'maker.receipt/v1', gate: 'silhouette',
    verdict: ok ? 'pass' : 'fail',
    checks: [{ id: 'silhouette.iou', value: +res.iou.toFixed(3), expected: `>=${min}`, ok }],
    ...res,
  }, null, 2));
  console.log('receipt →', out);
}
process.exit(ok ? 0 : 1);
