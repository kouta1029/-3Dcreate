"""Render Task A from the Phase 1 blend, one scene per Blender invocation.

From the repository root:
    blender -b production/escalator_phase1.blend --python-exit-code 1 \
        --python production/phase2/render_a.py -- a1 /tmp/phase2-a1
Use --preview for a 960x540 still or --benchmark for three full-size frames.
"""
from argparse import ArgumentParser
import csv
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter

import bpy


SCENES = {"a1": "a1_hero", "a8": "a8_xray"}
PHASE2 = Path(__file__).resolve().parent


def set_opacity(material, opacity):
    material.surface_render_method = 'BLENDED'
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    surface = nodes.get('Material Output').inputs['Surface']
    transparent = nodes.get('Transparent BSDF') or nodes.new('ShaderNodeBsdfTransparent')
    if opacity == 0:
        links.new(transparent.outputs[0], surface)
    else:
        mix = nodes.get('Mix Shader') or nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = opacity
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(nodes.get('Principled BSDF').outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], surface)


def configure(scene_id, width, height):
    scene = bpy.context.scene
    scene.name = SCENES[scene_id]
    scene.camera = bpy.data.objects['QC | whole loop']
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0, 0, 0, 1)
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    scene.frame_start = 1
    scene.frame_end = 120

    materials = bpy.data.materials
    set_opacity(materials['Balustrade | near glass'], 0)
    if scene_id == 'a8':
        for name, opacity in (
            ('Balustrade | far glass', .05),
            ('Skirt guard | blue steel', .10),
            ('Floor slab', .12),
            ('Landing | brushed metal', .15),
            ('Comb teeth', .28),
        ):
            set_opacity(materials[name], opacity)

        truss_nodes = materials['Truss | painted steel'].node_tree
        truss_nodes.animation_data.drivers[0].driver.expression = '0.96*transparency'

        for name, color, strength in (
            ('Sprocket | machined steel', (.90, .18, .025, 1), .55),
            ('Handrail drive | orange', (.85, .25, .052, 1), .24),
            ('Step chain | bronze steel', (.49, .26, .095, 1), .28),
        ):
            shader = materials[name].node_tree.nodes.get('Principled BSDF')
            shader.inputs['Emission Color'].default_value = color
            shader.inputs['Emission Strength'].default_value = strength
    return scene


def render_frames(scene, scratch, first, last, step=1):
    scene.frame_start = first
    scene.frame_end = last
    scene.frame_step = step
    scene.render.filepath = str(scratch / 'frame_')
    start = perf_counter()
    with (scratch / 'frame_times.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(('frame', 'seconds'))
        frame_start = start
        written = []

        def record_frame(render_scene):
            nonlocal frame_start
            now = perf_counter()
            writer.writerow((render_scene.frame_current, f'{now - frame_start:.6f}'))
            handle.flush()
            written.append(render_scene.frame_current)
            frame_start = now

        bpy.app.handlers.render_write.append(record_frame)
        try:
            bpy.ops.render.render(animation=True)
        finally:
            bpy.app.handlers.render_write.remove(record_frame)
        if written != list(range(first, last + 1, step)):
            raise RuntimeError(f'Incomplete render. Frames written: {written}')
    print(f'RENDER_SECONDS={perf_counter() - start:.3f}', flush=True)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('scene', choices=SCENES)
    parser.add_argument('scratch', type=Path)
    parser.add_argument('--height', type=int, choices=(720, 1080), default=1080)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preview', action='store_true')
    mode.add_argument('--benchmark', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])

    scratch = args.scratch.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    height = 540 if args.preview else args.height
    scene = configure(args.scene, height * 16 // 9, height)
    stem = f'{SCENES[args.scene]}_1080'
    if args.preview:
        render_frames(scene, scratch, 61, 61)
        return
    if args.benchmark:
        render_frames(scene, scratch, 1, 121, 60)
        return

    scene.frame_set(61)
    scene.render.filepath = '//../renders/'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(PHASE2 / f'escalator_{args.scene}.blend'),
                               compress=True)
    render_frames(scene, scratch, scene.frame_start, scene.frame_end)

    renders = PHASE2.parent / 'renders'
    renders.mkdir(exist_ok=True)
    start = perf_counter()
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-framerate', '24', '-start_number', '1', '-i', str(scratch / 'frame_%04d.png'),
        '-frames:v', '120', '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', str(renders / f'{stem}.mp4'),
    ], check=True)
    print(f'ENCODE_SECONDS={perf_counter() - start:.3f}', flush=True)
    shutil.copyfile(scratch / 'frame_0061.png', renders / f'{stem}.png')


if __name__ == '__main__':
    main()
