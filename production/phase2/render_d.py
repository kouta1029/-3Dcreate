"""Render Task D PNG frames and time each one.

Run from the repository root, with a fresh scratch directory for each shot:
    blender -b production/phase2/escalator_a4.blend --python-exit-code 1 \
        --python production/phase2/render_d.py -- /tmp/task-d/a4
Use --frames 1 60 90 --width 640 for a preview. Use --width 1280 for the
production fallback in COMMON.md. The default is 1920 pixels wide.
"""
from argparse import ArgumentParser
import csv
from pathlib import Path
import sys
from time import perf_counter

import bpy
from mathutils import Vector


def cull_offscreen(objects, camera_projection):
    # Test all eight corners against clip planes, including a margin for
    # subpixel jitter. Stage lighting has no shadows or screen-space rays.
    for obj, corners in objects:
        projection = camera_projection @ obj.matrix_world
        points = [projection @ corner for corner in corners]
        obj.hide_render = (all(p.x < -1.02 * p.w for p in points)
                           or all(p.x > 1.02 * p.w for p in points)
                           or all(p.y < -1.02 * p.w for p in points)
                           or all(p.y > 1.02 * p.w for p in points)
                           or all(p.z < -p.w for p in points))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--width', type=int, choices=(640, 1280, 1920), default=1920)
    parser.add_argument('--frames', type=int, nargs='+')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    scene = bpy.context.scene
    frames = range(scene.frame_start, scene.frame_end + 1)
    selected = args.frames or frames
    if any(frame not in frames for frame in selected):
        parser.error(f'Frames must be within {scene.frame_start}–{scene.frame_end}.')
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.width * 9 // 16
    depsgraph = bpy.context.evaluated_depsgraph_get()
    camera = scene.camera
    projection = camera.calc_matrix_camera(depsgraph, x=scene.render.resolution_x,
                                           y=scene.render.resolution_y)
    camera_projection = projection @ camera.matrix_world.inverted()
    mechanism = bpy.data.collections['M2  踏段・前輪・後輪・踏段チェーン']
    objects = [(obj, [Vector((*corner, 1)) for corner in obj.bound_box])
               for obj in mechanism.objects if not obj.hide_render]
    start = perf_counter()
    with (directory / 'frame_times.csv').open('w', newline='') as log:
        writer = csv.writer(log)
        writer.writerow(('frame', 'seconds'))
        for frame in selected:
            scene.frame_set(frame)
            cull_offscreen(objects, camera_projection)
            scene.render.filepath = str(directory / f'frame_{frame:04d}.png')
            frame_start = perf_counter()
            bpy.ops.render.render(write_still=True)
            writer.writerow((frame, f'{perf_counter() - frame_start:.6f}'))
            log.flush()
    print(f'RENDER_SECONDS={perf_counter() - start:.3f}', flush=True)


if __name__ == '__main__':
    main()
