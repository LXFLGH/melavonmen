# 50 · 几何坑（每条都真踩过）

## 1. `ExtrudeGeometry` 的正面不在 `depth`

`new THREE.ExtrudeGeometry(shape, { depth: d, bevelEnabled: true, bevelThickness: b })`
的实际 z 范围是 `[-b, d + b]`，**平面在 `d + b`，不是 `d`**。

症状：所有“贴在正面”的零件（面板、按钮、驱动器面板、丝印）全被埋进挤出体里，
正面看只剩一块底板。

```js
// 想让真正的前平面落在 FACE：
geo.translate(0, 0, FACE - depth - bevelThickness);
```

判据：`bevelSize` 会把**孔**缩小 `2×b`，所以开孔前要先按 `HOLE + 2b` 放大，否则屏幕四周被裁。

## 2. 封闭壳体把内部零件挡在后面

用“侧面放样 + 顶/底封盖”搭的壳，前壁就在 `z = 0`。
玻璃放在 `z = -0.095` 时整个藏在壳里，只在开孔处透出一个圆顶 —— 看起来像“屏幕没渲染”。

排查顺序（别跳步）：

```js
scene.traverse(o => { if (o.isMesh) o.material = new THREE.MeshBasicMaterial({color:0xff0000}) })
// 还看不见 → 是遮挡/位置问题；能看见 → 是材质/光照问题
```

再用射线确认“从相机到目标点的第一个交点是谁”，一次定位。

## 3. 键帽/贴图 180° 或镜像

`CanvasTexture.flipY` 默认 `true`。顶面 UV 只反转 v，不要同时反转 u：

```js
uv.push(0.5 + px / (hw * 2), 0.5 - pz / (hh * 2));
```

多圈环（碟形顶面）必须**统一按最外圈尺寸归一化**，每圈各自归一化会把贴图压成一团。
侧壁 UV 钉在贴图下沿的纯底色上，避免蹭到相邻字符。

## 4. 布局坐标系与外壳坐标系不同源

按键按 `u` 从左侧一个固定起点排，外壳绕原点建 —— 少一排数字区，整块键区就偏 36 mm。
**凡是“布局按单位排、外壳按原点建”的，先算布局包围盒中心再摆。**

```js
const bb = new THREE.Box3().setFromObject(keysGroup);
mesh.position.x -= (bb.min.x + bb.max.x) / 2;
```

## 5. 脚的坐标跑出机身

`for (sx of [-1,1]) for (sz of [-1,1])` 里如果 z 写成 `-0.55 + sz*1.55`，会有一个脚落在
`z = +1.0`，而机身只到 `z = 0` —— 桌面上多出一个圆盘，还以为是谁的杯子。
**对称布置的坐标要断言在壳体内**：`Math.abs(z) < depth/2`。

## 6. 一体成型不是拼出来的

台面 + 机身用两个 box 拼，接缝处会有：

- 侧影线断开（一眼看出是两个件）
- 90° 硬接（比周围更亮的一条线）
- 光打上去法线不连续

处置：机身放样出完整前脸；台面用**带倒角的挤出**（bevelSize ≥ 3 mm），
或者让台面顶面沿 z 方向带一个曲率（小半径圆角过渡）。

## 7. 拼接感：先染色，再看谁盖住谁

两个件"是不是一体"，肉眼在渲染图里看不准。染色一次就清楚：

```js
deck.material = new THREE.MeshBasicMaterial({ color: 0xff3b30 });   // 台面
shell.material = new THREE.MeshBasicMaterial({ color: 0x2b6cff });  // 机壳
```

同角度出图：红色盖住蓝色 → 台面比壳宽；蓝色压住红色 → 台面缩进去了。
两个真因（都踩过）：

- `ExtrudeGeometry` 的 `bevelSize` 是**向外扩**：腰线 = 形状宽 + 2×bevel，两端盖仍是形状宽。
  想和相邻件共面，得按腰线算宽度，倒角只留 0.005–0.01。
- 相接件的后缘要埋得比对方的**圆角半径**更深。对方前角 R0.10，你只埋 0.06，两个角就会露竖边。

## 8. 判断“看不见”的三段式

1. `o.visible` / `material.opacity` / `material.transparent`
2. 世界 bbox 是否在相机视锥内（`Box3` + `Frustum.intersectsBox`）
3. 从相机打一条射线到预想位置，看首个命中是谁

三分钟能定位的问题，不要靠反复换材质猜一小时。
