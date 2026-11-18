"""Render a prepared Task B blend to PNGs and encode its MP4.

blender -b -t 2 production/phase2/a2_step_solo.blend --python-exit-code 1 \
    --python production/phase2/render_task_b.py -- work/task-b/a2
"""
from argparse import ArgumentParser
import csv
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter

import bpy


def main():
    parser = ArgumentParser()
    parser.add_argument('scratch', type=Path)
    parser.add_argument('--height', type=int, choices=(720, 1080), default=1080)
    parser.add_argument('--still', type=int, default=1)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    scratch = args.scratch.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    blend = Path(bpy.data.filepath)
    renders = blend.parent.parent / 'renders'
    scene = bpy.context.scene
    scene.render.resolution_y = args.height
    scene.render.resolution_x = args.height * 16 // 9
    if not scene.frame_start <= args.still <= scene.frame_end:
        parser.error('--still must be within the rendered frame range')

    start = perf_counter()
    with (scratch / 'frame_times.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(('frame', 'seconds'))
        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            scene.render.filepath = str(scratch / f'frame_{frame:04d}.png')
            frame_start = perf_counter()
            bpy.ops.render.render(write_still=True)
            writer.writerow((frame, f'{perf_counter() - frame_start:.6f}'))
            handle.flush()
    print(f'RENDER_SECONDS={perf_counter() - start:.3f}', flush=True)

    start = perf_counter()
    video = scratch / f'{blend.stem}.mp4'
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-framerate', str(scene.render.fps), '-start_number', str(scene.frame_start),
        '-i', str(scratch / 'frame_%04d.png'),
        '-frames:v', str(scene.frame_end - scene.frame_start + 1),
        '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        str(video),
    ], check=True)
    print(f'ENCODE_SECONDS={perf_counter() - start:.3f}', flush=True)
    renders.mkdir(exist_ok=True)
    shutil.copyfile(video, renders / video.name)
    shutil.copyfile(scratch / f'frame_{args.still:04d}.png', renders / f'{blend.stem}.png')


if __name__ == '__main__':
    main()
