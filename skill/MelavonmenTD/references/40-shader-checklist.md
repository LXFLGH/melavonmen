# 40 · 着色器清单

按顺序过。每条都能判“是/否”，不写“看起来还行”。

## 必查

1. **色彩空间**：颜色贴图 `texture.colorSpace = SRGBColorSpace`；数据贴图（法线、粗糙度、
   遮罩）保持 `NoColorSpace`。渲染器 `outputColorSpace = SRGBColorSpace`。
2. **tone mapping 只做一次**：用了 `ACESFilmic` 就不要在着色器里再 gamma 一次。
   症状：整体发灰、高光不饱和。
3. **固定周期图案必须有 LOD**：
   ```glsl
   float texelPx = 1.0 / max(uTexSize.x * fwidth(uv.x), 1e-6);
   float on = smoothstep(1.8, 3.2, texelPx);   // < 1.8px 淡出
   col *= 1.0 + 0.03 * pattern * on;
   ```
   不做的结果不是“看不清”，是整屏噪点（摩尔纹）。
4. **噪声按屏幕像素生成**，不按 UV：`vec2 gp = floor(gl_FragCoord.xy * 0.5);`
   按 UV 生成的东西一旦降采样，必然糊成一层雾。
5. **采样数写死上限**：移动端 ≤ 8 次额外采样；桌面 ≤ 24。循环次数必须是常量，
   否则编译期无法展开，某些驱动直接掉到 10 fps。
6. **辉光分辨率依赖**：辉光半径用 texel 单位时，改画布分辨率必须重调。
   经验值：`半径 ≈ 2–6 texel`，强度按 1/分辨率 线性缩放。
7. **避免在片元里做分支重活**：`if` 里套 texture 采样会让 GPU 走两条路径。

## 会咬人的细节

| 现象 | 真因 | 处置 |
| --- | --- | --- |
| 文字发虚、边缘发灰 | 贴图被压缩（texel/px < 1） | 抬画布 + 拉近机位，或删辉光 |
| 一片均匀的绿雾 | 辉光强度按低分辨率调的 | 按分辨率重算强度 |
| 扫描线变成虚线 | 扫描线周期接近像素周期 | 周期 ≥ 3px，或用解析式而非贴图 |
| 边缘出现彩边 | 会聚误差/RGB 偏移过大 | 0.3–0.5 texel 足够，别超过 1 |
| 屏幕像镜子 | 反射强度 > 0.5 | Fresnel 基项压到 0.035 左右 |
| 曲面高光是死的 | 用了环境贴图而不是解析法线 | 顶点位移后重算法线 |

## 确定性开关

着色器里带 `uTime` 的，必须支持冻结：

```js
const FREEZE = new URLSearchParams(location.search).has('freeze');
U.uTime.value = FREEZE ? 0 : time;
```

否则同一份代码两次截图必然不同，diff 全是噪声。
