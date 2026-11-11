# 60 · Blender 常驻 worker

## 两条路，别混

| 用途 | 方式 | 特点 |
| --- | --- | --- |
| 批量渲染、导出、烘焙（无人值守） | `blender --background --python worker.py` 常驻子进程 | 不碰用户 GUI，一次启动多次调用，崩了自动重启 |
| 用户在看、要即时反馈 | GUI + addon（MCP） | 共享用户当前会话，可能撞上未保存场景 |

**红线**：用户开着 Blender 时，绝不 `taskkill`。要换 addon 就热重载（见 `blender-toolkit` 技能）。

## 线协议

一行一条，带前缀，避免和 Blender 自己的 stdout 混在一起：

```
host → worker   {"id":7,"op":"render","dir":"out/","views":["hero"]}\n
worker → host   MAKER_JSON:{"id":7,"ok":true,"files":["out/hero.png"]}\n
```

启动握手：worker 打印 `MAKER_READY`，host 收到才发第一条请求。

```python
# worker 骨架
import bpy, sys, json

def send(obj):
    sys.stdout.write("MAKER_JSON:" + json.dumps(obj) + "\n")
    sys.stdout.flush()

sys.stdout.write("MAKER_READY\n"); sys.stdout.flush()
for line in sys.stdin:
    req = json.loads(line)
    try:
        if req["op"] == "ping":
            send({"id": req["id"], "ok": True})
        elif req["op"] == "render":
            send({"id": req["id"], "ok": True, "files": do_render(req)})
    except Exception as e:
        send({"id": req["id"], "ok": False, "error": str(e)})
```

## host 侧要点

- **单例 + 串行**：一个 Python 进程一个 worker，请求排队，不并发。
- **超时即杀**：`kill()` 后下一调用重新 spawn，不要试图救活。
- **日志落盘**：Blender 的 stdout 里混着大量 chatter，只保留以 `MAKER_JSON:` 开头的行，
  其余写到 `out/blender.log`（网络/驱动问题九成从那里看出来）。
- **路径全绝对**：Blender 的工作目录不等于你的 cwd。
- **临时场景**：worker 自己 `bpy.ops.wm.read_factory_settings()`，不读用户的 .blend。

## 导出契约

```python
bpy.ops.export_scene.gltf(
    filepath=path, export_format='GLB',
    export_yup=True, use_selection=True,
    export_apply=True,            # 应用修改器
    export_materials='EXPORT',
)
```

导出后立刻回读：bbox（米）× `1000/unit_mm` 应等于 spec 的 scene 尺寸。
`glbcheck.mjs` 就是干这个的，别用肉眼对比。

## 常见故障

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `Could not connect` | addon 没起 / 端口没监听 | 查 `netstat -ano \| findstr 9876`，别改配置 |
| 重载后第一次调用 `WinError 10053` | 连接还在 TIME_WAIT | 重试一次即可 |
| 渲染全黑 | 相机没设 / 灯光在世界外 | worker 里强制检查 `scene.camera` |
| 导出后尺寸差 8.4 倍 | 单位换算漏了 | `meters × 1000 / unit_mm` |
| EEVEE 在无头下报 GPU 错 | 无显示设备 | 改 `CYCLES` + `samples=32`，或 `--factory-startup` |
