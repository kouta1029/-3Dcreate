"""Render Task C to a PNG sequence, then encode H.264 and copy a QC still.

blender -b production/escalator_a5.blend -t 2 --python-exit-code 1 \
    --python production/phase2/render_task_c.py -- /tmp/task-c/a5
"""
from argparse import ArgumentParser
from pathlib import Path
import csv
import shutil
import subprocess
import sys
from time import perf_counter

import bpy
from mathutils import Vector

SHOTS = {'A5 | Drive': ('a5_drive', 54), 'A6 | Handrail sync': ('a6_handrail', 95)}


def cull_offscreen(scene, frames):
    """Skip meshes outside the fixed cutaway for every frame in this sequence."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    camera = scene.camera
    projection = camera.calc_matrix_camera(depsgraph, x=scene.render.resolution_x,
                                           y=scene.render.resolution_y)
    world_to_clip = projection @ camera.matrix_world.inverted()
    candidates = {obj: tuple(Vector((*corner, 1)) for corner in obj.bound_box)
                  for obj in scene.objects if obj.type == 'MESH' and not obj.hide_render}
    for frame in frames:
        scene.frame_set(frame)
        for obj, bounds in tuple(candidates.items()):
            transform = world_to_clip @ obj.matrix_world
            corners = [transform @ corner for corner in bounds]
            if all(min(c[axis] for c in corners) < 1.03 and
                   max(c[axis] for c in corners) > -1.03 for axis in (0, 1)):
                del candidates[obj]
    for obj in candidates:
        obj.hide_render = True
    print(f'OFFSCREEN_MESHES={len(candidates)}', flush=True)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('scratch', type=Path)
    parser.add_argument('--height', type=int, choices=(270, 540, 720, 1080), default=1080)
    parser.add_argument('--preview', type=int, nargs='+', metavar='FRAME')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    scratch = args.scratch.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    basename, representative = SHOTS[scene.name]
    scene.render.resolution_x = args.height * 16 // 9
    scene.render.resolution_y = args.height
    frames = args.preview or range(scene.frame_start, scene.frame_end + 1)
    cull_offscreen(scene, frames)
    start = perf_counter()
    with (scratch / 'frame_times.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(('frame', 'seconds'))
        for frame in frames:
            scene.frame_set(frame)
            filename = scratch / f'frame_{frame:04d}.png'
            scene.render.filepath = str(filename)
            frame_start = perf_counter()
            bpy.ops.render.render(write_still=True)
            writer.writerow((frame, f'{perf_counter() - frame_start:.6f}'))
            handle.flush()
    print(f'RENDER_SECONDS={perf_counter() - start:.3f}', flush=True)
    if args.preview:
        return

    renders = Path(bpy.data.filepath).parent / 'renders'
    renders.mkdir(exist_ok=True)
    start = perf_counter()
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-threads', '2', '-framerate', str(scene.render.fps),
        '-i', str(scratch / 'frame_%04d.png'), '-frames:v', str(len(frames)),
        '-c:v', 'libx264', '-threads', '2', '-crf', '17', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', str(renders / f'{basename}.mp4'),
    ], check=True)
    print(f'ENCODE_SECONDS={perf_counter() - start:.3f}', flush=True)
    shutil.copyfile(scratch / f'frame_{representative:04d}.png', renders / f'{basename}.png')


if __name__ == '__main__':
    main()
