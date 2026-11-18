"""Prepare an A2 or A3 shot from the Phase 1 blend.

blender -b production/escalator_phase1.blend --python-exit-code 1 \
    --python production/phase2/build_task_b.py -- a2_step_solo
"""
from argparse import ArgumentParser
from math import tau
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track import Track


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def camera(scene, name, target, offset, width):
    data = bpy.data.cameras.new(name)
    data.type = 'ORTHO'
    data.ortho_scale = width
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = Vector(target) + Vector(offset)
    aim(obj, target)
    scene.camera = obj


def softbox(scene, name, location, power, size, color):
    light = bpy.data.lights.new(name, 'AREA')
    light.shape = 'DISK'
    light.energy = power
    light.size = size
    light.color = color
    light.use_shadow = False
    obj = bpy.data.objects.new(name, light)
    scene.collection.objects.link(obj)
    obj.location = location
    aim(obj, (0, 0, 0))


def step_solo(scene):
    scene.frame_set(1)
    names = ('踏段 02 | tread and riser', '前輪 02', '後輪 02', '三角リンク 02',
             '踏段チェーン 006', '踏段チェーン 007', '踏段チェーン 008')
    parts = [bpy.data.objects[name] for name in names]
    for obj in tuple(scene.objects):
        if obj not in parts:
            bpy.data.objects.remove(obj, do_unlink=True)

    # Freeze the Phase 1 local assembly, then spin all its parts about its center.
    corners = [obj.matrix_world @ Vector(corner) for obj in parts for corner in obj.bound_box]
    center = Vector([(min(p[i] for p in corners) + max(p[i] for p in corners)) / 2
                     for i in range(3)])
    turntable = bpy.data.objects.new('A2 | turntable', None)
    scene.collection.objects.link(turntable)
    for obj in parts:
        pose = obj.matrix_world.copy()
        obj.animation_data_clear()
        obj.parent = turntable
        pose.translation -= center
        obj.matrix_basis = pose

    turntable.rotation_euler.z = 0
    turntable.keyframe_insert('rotation_euler', index=2, frame=1)
    turntable.rotation_euler.z = tau
    turntable.keyframe_insert('rotation_euler', index=2, frame=97)
    curve = turntable.animation_data.action.fcurves[0]
    for key in curve.keyframe_points:
        key.interpolation = 'LINEAR'
    cycles = curve.modifiers.new('CYCLES')
    cycles.mode_before = cycles.mode_after = 'REPEAT_OFFSET'
    scene.frame_end = 96

    camera(scene, 'A2 | step assembly', (0, 0, 0), (-3.8, -5, 3.6), 1.71)
    softbox(scene, 'A2 | key', (-2.1, -1.8, 3.1), 340, 3.4, (1, .93, .85))
    softbox(scene, 'A2 | fill', (2, -1.8, .6), 135, 2.6, (.78, .89, 1))
    softbox(scene, 'A2 | rim', (.6, 1.8, 2.2), 285, 2.2, (.77, .88, 1))
    softbox(scene, 'A2 | underside', (-.8, .9, -.7), 38, 1.4, (.85, .92, 1))


def fade_lower_belt(rise):
    mat = bpy.data.materials['Handrail belt | rubber']
    tree = mat.node_tree
    surface = tree.nodes.get('Material Output').inputs['Surface']
    rubber = surface.links[0].from_socket
    geometry = tree.nodes.new('ShaderNodeNewGeometry')
    xyz = tree.nodes.new('ShaderNodeSeparateXYZ')
    alpha = tree.nodes.new('ShaderNodeMapRange')
    alpha.inputs['From Min'].default_value = rise + .10
    alpha.inputs['From Max'].default_value = rise + .36
    alpha.inputs['To Min'].default_value = .18
    clear = tree.nodes.new('ShaderNodeBsdfTransparent')
    mix = tree.nodes.new('ShaderNodeMixShader')
    tree.links.new(geometry.outputs['Position'], xyz.inputs[0])
    tree.links.new(xyz.outputs['Z'], alpha.inputs['Value'])
    tree.links.new(alpha.outputs[0], mix.inputs[0])
    tree.links.new(clear.outputs[0], mix.inputs[1])
    tree.links.new(rubber, mix.inputs[2])
    tree.links.new(mix.outputs[0], surface)


def tracks(scene):
    upper_x, rise = Track().upper
    camera(scene, 'A3 | upper transition', (upper_x - 1.62, 0, rise + .10),
           (-.90, -8, 1.22), 3.86)
    # This Phase 1 mesh groups both glass panels with the skirt guards.
    shell = bpy.data.objects['欄干・スカートガード・インレット部']
    shell.hide_render = True
    shell.hide_set(True)
    fade_lower_belt(rise)

    # The chain runs outboard of the front guide rail, so its plates would
    # otherwise cover the guide at the landing in this side-on view.
    for name, opacity in (('Step chain | bronze steel', .27),
                          ('Handrail drive | orange', .42)):
        shader = bpy.data.materials[name].node_tree.nodes.get('Principled BSDF')
        shader.inputs['Alpha'].default_value = opacity

    for name, color in (('Front guide rail', (.012, .29, 1)),
                        ('Rear guide rail', (.035, .69, .11))):
        shader = bpy.data.materials[name].node_tree.nodes.get('Principled BSDF')
        shader.inputs['Emission Color'].default_value = (*color, 1)
        shader.inputs['Emission Strength'].default_value = .85
    for obj in scene.objects:
        if obj.type == 'LIGHT':
            obj.data.energy *= .46


def main():
    parser = ArgumentParser()
    parser.add_argument('shot', choices=('a2_step_solo', 'a3_tracks'))
    parser.add_argument('--preview', type=Path)
    parser.add_argument('--preview-frame', type=int, action='append')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    scene = bpy.context.scene
    scene.timeline_markers.clear()
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0, 0, 0, 1)
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.fps_base = 1
    scene.render.filepath = '//../renders/'
    if args.shot == 'a2_step_solo':
        step_solo(scene)
        preview_frames = (1, 25, 49, 73)
    else:
        tracks(scene)
        preview_frames = (1, 41, 81, 121)

    scene.frame_set(1)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'

    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
        scene.render.resolution_percentage = 50
        for frame in args.preview_frame or preview_frames:
            scene.frame_set(frame)
            scene.render.filepath = str(args.preview / f'{args.shot}_{frame:04d}.png')
            bpy.ops.render.render(write_still=True)
    else:
        bpy.data.orphans_purge(do_recursive=True)
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(
            filepath=str(Path(__file__).resolve().with_name(f'{args.shot}.blend')),
            compress=True,
        )


if __name__ == '__main__':
    main()
