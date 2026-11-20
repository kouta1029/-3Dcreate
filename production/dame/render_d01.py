"""Render the Phase A stills or the 48 test-loop frames from d01_models.blend."""

import argparse
from pathlib import Path
import sys
from time import perf_counter

import bpy

ROOT = Path(__file__).resolve().parent / "renders" / "d01"
STILLS = {
    "hero_interior": "01_hero_interior",
    "hero_interior_hot": "02_hero_interior_hot",
    "cutaway_side": "03_cutaway_side",
    "foil_macro": "04_foil_macro",
}


def render_still(name, scene_name, directory, percentage=100):
    scene = bpy.data.scenes[scene_name]
    bpy.context.window.scene = scene
    scene.frame_set(1)
    scene.render.resolution_percentage = percentage
    scene.render.filepath = str(directory / (name + ".png"))
    started = perf_counter()
    bpy.ops.render.render(write_still=True)
    print(f"D01_RENDER {name} {perf_counter()-started:.3f}s", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preview", "stills", "loop"))
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--shot", choices=STILLS)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "loop":
        scene = bpy.data.scenes[STILLS["hero_interior"]]
        bpy.context.window.scene = scene
        scene.render.resolution_percentage = 50
        scene.render.filepath = str(work_dir / "frame_")
        started = perf_counter()
        bpy.ops.render.render(animation=True)
        print(f"D01_RENDER test_loop_frames {perf_counter()-started:.3f}s", flush=True)
        return
    directory = work_dir if args.mode == "preview" else ROOT / "stills"
    directory.mkdir(parents=True, exist_ok=True)
    selected = [args.shot] if args.shot else STILLS
    for name in selected:
        render_still(name, STILLS[name], directory, 50 if args.mode == "preview" else 100)


if __name__ == "__main__":
    main()
