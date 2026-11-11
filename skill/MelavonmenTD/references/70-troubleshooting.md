# 70 · 按错误码排查

所有命令都在项目根跑，脚本在技能的 `scripts/` 目录。

## E_REF_MISSING
```
ls ref/            # 空 → 先找参考图/手册
```
参考图必须能回答：比例、面板分区、按键/接口朝向。查不到就把它标成 `assumed` 并写理由，
**不要**把“我记得”写进 spec 当成 ref。

## E_UNIT_AMBIGUOUS
```
node scripts/compile.mjs --spec maker.spec.json --check
```
两个数字互相矛盾时，以实机公开尺寸为准（如 5120：20.5 × 24.5 × 8 in）。
`unit_mm` 只允许一个值；多单位先在 spec 外换算好。

## E_GEOM_BURIED
```js
// 1. 染色定位
scene.traverse(o => { if (o.isMesh) o.material = new THREE.MeshBasicMaterial({ color: 0xff0000 }); });
// 2. 打射线
const ray = new THREE.Raycaster();
ray.setFromCamera(new THREE.Vector2(0, 0), camera);
ray.intersectObjects(scene.children, true).slice(0, 3).map(h => [h.object.name, h.distance]);
```
第一个命中不是目标 → 目标在前面被挡；一个都没有 → 目标在视锥外或没加进场景。

## E_GEOM_FACE_Z
挤出件的正面在 `depth + bevelThickness`。改 `translate`，别改零件坐标。

## E_FRAME_COVERAGE
先打印 bbox 投影，再动相机：
```
node scripts/frame.mjs --url … --root … --verbose
```
覆盖率小 → 拉近；边缘被裁 → 抬 `margin`。

## E_TEXEL_LOW
```
node scripts/frame.mjs --texel 'screen=window.__scene.screen:1.2'
```
比值 < 1.2 → 要么抬贴图分辨率，要么把机位拉近。**先确认不是辉光把字糊了**：
临时 `uGlow = 0` 再拍一张。

## E_PERIOD_MOIRE
把固定周期改成 `fwidth` 淡出；不要调幅度、不要加模糊。

## E_BUDGET_CALLS
```
node scripts/frame.mjs --budget calls=250 --verbose
```
按 “几何体 uuid → 实例数” 分组，≥5 且同材质的组用 `InstancedMesh`；
只有 1–2 个实例的组考虑合并 BufferGeometry。

## E_NOT_VERIFIED
缺 receipt。补跑：
```
node scripts/frame.mjs … --json out/frame.json
```
并在 spec 里记下 `build.spec_hash`，交付时两份 receipt 的 hash 必须一致。
