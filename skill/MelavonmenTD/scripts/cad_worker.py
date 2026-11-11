#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cad_worker.py — MelavonmenTD 内置无头 CAD 几何引擎（基于 Blender Python）

无需任何外部 CAD 库，使用 Blender 内核直接进行参数化 CSG 实体建模、
实体闭合度量（manifold / volume / bbox）并交付导出（GLB / STL / OBJ）。

用法（由 cad.mjs 内部通过 blender --background 调度）：
    blender --background --factory-startup --python cad_worker.py -- --spec <payload.json> --out <out_dir>
"""
import sys
import json
import os
import math
import hashlib
from pathlib import Path

# 解析传入的命令行参数（在 -- 之后）
def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    
    spec_path = None
    out_dir = "out"
    allow_degraded = False

    i = 0
    while i < len(argv):
        if argv[i] == "--spec" and i + 1 < len(argv):
            spec_path = argv[i + 1]
            i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            out_dir = argv[i + 1]
            i += 2
        elif argv[i] == "--allow-degraded":
            allow_degraded = True
            i += 1
        else:
            i += 1
    return spec_path, out_dir, allow_degraded


def create_flange(params):
    """参数化法兰实体生成 (全毫米尺寸换算为米)"""
    import bpy, bmesh
    
    outer_d = float(params.get("outer_d", 160.0)) / 1000.0
    bore_d = float(params.get("bore_d", 80.0)) / 1000.0
    bolt_circle_d = float(params.get("bolt_circle_d", 130.0)) / 1000.0
    bolt_holes = int(params.get("bolt_holes", 6))
    bolt_hole_d = float(params.get("bolt_hole_d", 18.0)) / 1000.0
    plate_t = float(params.get("plate_t", 16.0)) / 1000.0
    hub_d = float(params.get("hub_d", 100.0)) / 1000.0
    hub_h = float(params.get("hub_h", 24.0)) / 1000.0
    raised_h = float(params.get("raised_h", 2.0)) / 1000.0

    # 1. 基础法兰盘
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=outer_d / 2.0, depth=plate_t,
        location=(0, 0, plate_t / 2.0)
    )
    base_obj = bpy.context.active_object
    base_obj.name = "Flange_Base"

    # 2. 轴套 (Hub)
    if hub_d > 0 and hub_h > 0:
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=64, radius=hub_d / 2.0, depth=hub_h,
            location=(0, 0, plate_t + hub_h / 2.0)
        )
        hub_obj = bpy.context.active_object
        mod_union = base_obj.modifiers.new(name="Union_Hub", type="BOOLEAN")
        mod_union.operation = "UNION"
        mod_union.object = hub_obj
        bpy.context.view_layer.objects.active = base_obj
        bpy.ops.object.modifier_apply(modifier="Union_Hub")
        bpy.data.objects.remove(hub_obj, do_unlink=True)

    # 3. 中心通孔 (Bore Hole)
    total_h = plate_t + hub_h + 0.02
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=bore_d / 2.0, depth=total_h,
        location=(0, 0, total_h / 2.0 - 0.01)
    )
    bore_obj = bpy.context.active_object
    mod_bore = base_obj.modifiers.new(name="Cut_Bore", type="BOOLEAN")
    mod_bore.operation = "DIFFERENCE"
    mod_bore.object = bore_obj
    bpy.context.view_layer.objects.active = base_obj
    bpy.ops.object.modifier_apply(modifier="Cut_Bore")
    bpy.data.objects.remove(bore_obj, do_unlink=True)

    # 4. 环形螺栓孔阵列 (Bolt Holes)
    if bolt_holes > 0 and bolt_circle_d > 0:
        radius_bc = bolt_circle_d / 2.0
        for idx in range(bolt_holes):
            ang = (2.0 * math.pi * idx) / bolt_holes
            bx = radius_bc * math.cos(ang)
            by = radius_bc * math.sin(ang)
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=32, radius=bolt_hole_d / 2.0, depth=plate_t * 2.0,
                location=(bx, by, plate_t / 2.0)
            )
            bolt_cutter = bpy.context.active_object
            mod_bolt = base_obj.modifiers.new(name=f"Cut_Bolt_{idx}", type="BOOLEAN")
            mod_bolt.operation = "DIFFERENCE"
            mod_bolt.object = bolt_cutter
            bpy.context.view_layer.objects.active = base_obj
            bpy.ops.object.modifier_apply(modifier=f"Cut_Bolt_{idx}")
            bpy.data.objects.remove(bolt_cutter, do_unlink=True)

    return base_obj


def create_box(params):
    import bpy
    size = params.get("size", [100.0, 100.0, 100.0])
    sx, sy, sz = [float(v) / 1000.0 for v in size]
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, sz / 2.0))
    obj = bpy.context.active_object
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def create_cylinder(params):
    import bpy
    r = float(params.get("radius", 50.0)) / 1000.0
    h = float(params.get("height", 100.0)) / 1000.0
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=r, depth=h, location=(0, 0, h / 2.0))
    return bpy.context.active_object


def build_cad_object(part_def):
    """根据定义构建零件几何体"""
    import bpy
    cad = part_def.get("cad") or {}
    recipe = cad.get("recipe") or cad.get("id") or cad.get("primitive") or ""
    params = cad.get("params") or {}

    if "flange" in recipe.lower():
        obj = create_flange(params)
    elif "box" in recipe.lower() or "cube" in recipe.lower():
        obj = create_box(params)
    elif "cylinder" in recipe.lower():
        obj = create_cylinder(params)
    else:
        # 默认回退：按 bbox 构建长方体
        bbox = part_def.get("bbox_mm") or {}
        sx = (bbox.get("x", [0, 100])[1] - bbox.get("x", [0, 100])[0]) if isinstance(bbox.get("x"), list) else 100
        sy = (bbox.get("y", [0, 100])[1] - bbox.get("y", [0, 100])[0]) if isinstance(bbox.get("y"), list) else 100
        sz = (bbox.get("z", [0, 40])[1] - bbox.get("z", [0, 40])[0]) if isinstance(bbox.get("z"), list) else 40
        obj = create_box({"size": [sx, sy, sz]})

    obj.name = part_def.get("name", "cad_part")
    return obj


def measure_and_verify(obj):
    """度量物理指标并进行三态验收闸门校验"""
    import bpy, bmesh

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])

    # 1. 闭合实体检验 (Manifold)
    is_closed = all(e.is_manifold for e in bm.edges) and (len(bm.faces) > 0)

    # 2. 体积计算 (m³ -> mm³)
    vol_m3 = 0.0
    try:
        vol_m3 = abs(bm.calc_volume())
    except Exception:
        pass
    vol_mm3 = vol_m3 * 1e9

    # 3. 包围盒计算 (m -> mm)
    bounds = obj.bound_box
    min_co = [min(pt[i] for pt in bounds) for i in range(3)]
    max_co = [max(pt[i] for pt in bounds) for i in range(3)]
    size_mm = [(max_co[i] - min_co[i]) * 1000.0 for i in range(3)]

    # 4. 拓扑与孔径亏格 (Genus)
    v_cnt = len(bm.verts)
    e_cnt = len(bm.edges)
    f_cnt = len(bm.faces)
    euler = v_cnt - e_cnt + f_cnt
    genus = max(0, int(round((2 - euler) / 2.0)))

    bm.free()

    issues = []
    if not is_closed:
        issues.append({"code": "E_GEOM_NOT_CLOSED", "message": "网格非闭合实体，存在边界或非流形边"})
    if vol_mm3 <= 0:
        issues.append({"code": "E_GEOM_EMPTY", "message": "体积为0或负值"})

    verdict = "pass" if not issues else "fail"

    facts = {
        "bbox_mm": [round(s, 2) for s in size_mm],
        "volume_mm3": round(vol_mm3, 2),
        "closed": is_closed,
        "genus": genus,
        "tris": f_cnt,
        "verts": v_cnt,
    }
    return verdict, facts, issues


def export_formats(obj, out_dir, part_name, formats):
    import bpy
    os.makedirs(out_dir, exist_ok=True)
    exported = []

    # 选中当前物体
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    for fmt in [f.strip().lower() for f in formats.split(",") if f.strip()]:
        if fmt == "glb" or fmt == "gltf":
            glb_path = os.path.join(out_dir, f"{part_name}.glb")
            bpy.ops.export_scene.gltf(
                filepath=glb_path,
                export_format="GLB",
                use_selection=True,
                export_apply=True,
                export_yup=True
            )
            if os.path.exists(glb_path):
                exported.append({
                    "format": "glb",
                    "path": os.path.abspath(glb_path),
                    "bytes": os.path.getsize(glb_path),
                    "sha256": hashlib.sha256(open(glb_path, "rb").read()).hexdigest()
                })
        elif fmt == "stl":
            stl_path = os.path.join(out_dir, f"{part_name}.stl")
            try:
                bpy.ops.wm.stl_export(filepath=stl_path, export_selected_objects=True)
            except AttributeError:
                bpy.ops.export_mesh.stl(filepath=stl_path, use_selection=True)
            if os.path.exists(stl_path):
                exported.append({
                    "format": "stl",
                    "path": os.path.abspath(stl_path),
                    "bytes": os.path.getsize(stl_path),
                    "sha256": hashlib.sha256(open(stl_path, "rb").read()).hexdigest()
                })
        elif fmt == "obj":
            obj_path = os.path.join(out_dir, f"{part_name}.obj")
            try:
                bpy.ops.wm.obj_export(filepath=obj_path, export_selected_objects=True)
            except AttributeError:
                bpy.ops.export_scene.obj(filepath=obj_path, use_selection=True)
            if os.path.exists(obj_path):
                exported.append({
                    "format": "obj",
                    "path": os.path.abspath(obj_path),
                    "bytes": os.path.getsize(obj_path),
                    "sha256": hashlib.sha256(open(obj_path, "rb").read()).hexdigest()
                })

    return exported


def main():
    import bpy
    spec_path, out_dir, allow_degraded = parse_args()
    if not spec_path or not os.path.exists(spec_path):
        print(json.dumps({"ok": False, "error": f"spec 文件不存在: {spec_path}"}))
        sys.exit(1)

    with open(spec_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    tasks = payload.get("tasks", [])
    results = []
    overall_ok = True

    for t in tasks:
        # 重置 Blender 出厂场景
        bpy.ops.wm.read_factory_settings(use_empty=True)

        name = t["name"]
        formats = t.get("formats", "glb")
        
        try:
            obj = build_cad_object(t)
            verdict, facts, issues = measure_and_verify(obj)
            
            is_pass = (verdict == "pass") or (allow_degraded and verdict == "degraded")
            if not is_pass:
                overall_ok = False

            files = []
            if is_pass:
                files = export_formats(obj, out_dir, name, formats)

            results.append({
                "name": name,
                "verdict": verdict,
                "facts": facts,
                "issues": issues,
                "files": files
            })
        except Exception as e:
            overall_ok = False
            results.append({
                "name": name,
                "verdict": "fail",
                "issues": [{"code": "E_CAD_BUILD_ERROR", "message": str(e)}]
            })

    output = {
        "ok": overall_ok,
        "results": results
    }
    # 打印特殊标记行，以便 Node 脚本精准解析
    print("CAD_RESULT_JSON:" + json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
