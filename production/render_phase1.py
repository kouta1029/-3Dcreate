"""Render the Phase 1 QC stills and 120-frame A1 loop from the generated blend.

Example:
    blender -b production/escalator_phase1.blend --python-exit-code 1 \
        --python production/render_phase1.py -- /tmp/escalator-frames
"""
from argparse import ArgumentParser
from pathlib import Path
import csv
import subprocess
import sys
from time import perf_counter

import bpy

parser = ArgumentParser()
parser.add_argument('scratch', type=Path)
modes = parser.add_mutually_exclusive_group()
modes.add_argument('--stills-only', action='store_true')
modes.add_argument('--drive-only', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
scratch = args.scratch.resolve()
scratch.mkdir(parents=True, exist_ok=True)
renders = Path(bpy.data.filepath).parent / 'renders'
renders.mkdir(exist_ok=True)
scene = bpy.context.scene
whole = bpy.data.objects['QC | whole loop']


def render(camera, frame, output):
    scene.camera = camera
    scene.frame_set(frame)
    scene.render.filepath = str(output)
    start = perf_counter()
    bpy.ops.render.render(write_still=True)
    return perf_counter()-start


def render_drive():
    camera = bpy.data.objects['QC | upper drive']
    cover = bpy.data.collections['M5  櫛板・乗降板']
    slabs = bpy.data.objects['上下階スラブ・支持アングル']
    cover_hidden = cover.hide_render
    slabs_hidden = slabs.hide_render
    cover.hide_render = True
    slabs.hide_render = True
    try:
        render(camera,73,renders/'drive_unit.png')
    finally:
        cover.hide_render = cover_hidden
        slabs.hide_render = slabs_hidden


if args.drive_only:
    render_drive()
elif args.stills_only:
    render(whole, 1, renders/'whole_loop.png')
    render(bpy.data.objects['QC | upper landing'],37,renders/'upper_landing.png')
    render_drive()
else:
    start = perf_counter()
    with (scratch/'frame_times.csv').open('w',newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(('frame','seconds'))
        for frame in range(scene.frame_start,scene.frame_end+1):
            path = scratch/f'frame_{frame:04d}.png'
            duration = render(whole,frame,path)
            writer.writerow((frame,f'{duration:.6f}'))
            handle.flush()
    print(f'RENDER_SECONDS={perf_counter()-start:.3f}',flush=True)
    (renders/'whole_loop.png').write_bytes((scratch/'frame_0001.png').read_bytes())
    render(bpy.data.objects['QC | upper landing'],37,renders/'upper_landing.png')
    render_drive()
    start = perf_counter()
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
                    '-framerate',str(scene.render.fps),'-i',str(scratch/'frame_%04d.png'),
                    '-frames:v',str(scene.frame_end-scene.frame_start+1),
                    '-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',
                    str(renders/'test_loop_5s.mp4')],check=True)
    print(f'ENCODE_SECONDS={perf_counter()-start:.3f}',flush=True)
