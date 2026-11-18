"""Build either Task C scene from the checked-in Phase 1 blend.

blender -b production/escalator_phase1.blend --python-exit-code 1 \
    --python production/phase2/build_task_c.py -- a5
"""
from argparse import ArgumentParser
from bisect import bisect_right
from itertools import groupby
from math import atan2, cos, pi, sin, tau
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

PRODUCTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCTION))
from track import PITCH, Track, lengths

PERIOD = 120
TRAVEL = 6 * PITCH
RAIL_RATIO = 1.10


class Loop:
    """Read the exact centerline of a Phase 1 closed rectangular sweep."""

    def __init__(self, obj):
        _, faces = next(groupby(obj.data.polygons, key=lambda face: face.material_index))
        self.indices = sorted({index for face in faces for index in face.vertices})
        self.points = []
        for i in range(0, len(self.indices), 4):
            ring = self.indices[i:i + 4]
            center = sum((obj.data.vertices[j].co for j in ring), Vector()) / 4
            self.points.append((center.x, center.z))
        self.points.append(self.points[0])
        self.distances = lengths(self.points)
        self.length = self.distances[-1]

    def sample(self, distance):
        distance %= self.length
        i = bisect_right(self.distances, distance) - 1
        a = Vector(self.points[i])
        b = Vector(self.points[i + 1])
        fraction = (distance - self.distances[i]) / (self.distances[i + 1] - self.distances[i])
        return a.lerp(b, fraction), (b - a).normalized()

    def uphill_distance_at(self, x):
        for i, ((ax, _), (bx, _)) in enumerate(zip(self.points, self.points[1:])):
            if ax <= x < bx:
                fraction = (x - ax) / (bx - ax)
                return self.distances[i] + fraction * (self.distances[i + 1] - self.distances[i])
        raise ValueError(f'Position outside the uphill strand: {x}')


def principled(material):
    return material.node_tree.nodes.get('Principled BSDF')


def shaded(name, source, color, opacity=1):
    material = bpy.data.materials[source].copy()
    material.name = name
    material.diffuse_color = (*color, 1)
    shader = principled(material)
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Emission Color'].default_value = (*color, 1)
    if opacity < 1:
        material.surface_render_method = 'BLENDED'
        nodes = material.node_tree.nodes
        connections = material.node_tree.links
        mix = nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = opacity
        connections.new(nodes.new('ShaderNodeBsdfTransparent').outputs[0], mix.inputs[1])
        connections.new(shader.outputs[0], mix.inputs[2])
        connections.new(mix.outputs[0], nodes.get('Material Output').inputs['Surface'])
    return material


def highlight(material, peak, width, base=0.08, strength=2.6):
    emission = principled(material).inputs['Emission Strength']
    for frame in range(1, PERIOD + 2):
        delta = (frame - 1 - peak + PERIOD / 2) % PERIOD - PERIOD / 2
        weight = 0.5 + 0.5 * cos(pi * delta / width) if abs(delta) < width else 0
        emission.default_value = base + strength * weight
        emission.keyframe_insert('default_value', frame=frame)
    curve, = material.node_tree.animation_data.action.fcurves
    curve.modifiers.new('CYCLES')
    for key in curve.keyframe_points:
        key.interpolation = 'LINEAR'


def replace_material(obj, original, replacement):
    slot = obj.material_slots[original]
    slot.link = 'OBJECT'
    slot.material = replacement


def set_camera(obj, target, offset, width):
    offset = Vector(offset)
    obj.location = Vector(target) + offset
    obj.rotation_euler = (-offset).to_track_quat('-Z', 'Y').to_euler()
    obj.data.ortho_scale = width


def hide(obj):
    obj.hide_render = True
    obj.hide_viewport = True


def cutaway():
    panel = bpy.data.objects['欄干・スカートガード・インレット部']
    near = panel.data.materials.find('Balustrade | near glass')
    mesh = bmesh.new()
    mesh.from_mesh(panel.data)
    bmesh.ops.delete(mesh, geom=[face for face in mesh.faces if face.material_index == near],
                     context='FACES')
    mesh.to_mesh(panel.data)
    mesh.free()
    material = panel.material_slots['Balustrade | far glass'].material.copy()
    material.name = 'Task C | translucent far balustrade'
    mix = next(node for node in material.node_tree.nodes if node.type == 'MIX_SHADER')
    mix.inputs[0].default_value = .075
    replace_material(panel, 'Balustrade | far glass', material)


def cylinder(name, radius, depth, location, material, parent=None, axis='Z', vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj.parent = parent
    obj.location = location
    if axis == 'Y':
        obj.rotation_euler.x = pi / 2
    return obj


def rotor(name, center, y, radius, depth, steel, accent, turns):
    pivot = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(pivot)
    pivot.location = (center[0], y, center[1])
    cylinder(name + ' | core', radius, depth, (0, 0, 0), steel, pivot, 'Y')
    for index in range(5):
        angle = tau * index / 5
        # A single wider bar makes the direction of rotation visible.
        rib = radius * (0.20 if index == 0 else 0.10)
        cylinder(name + ' | rotor bar', rib, depth + .006,
                 (radius * .85 * cos(angle), 0, radius * .85 * sin(angle)),
                 accent, pivot, 'Y', vertices=12)
    pivot.rotation_euler.y = 0
    pivot.keyframe_insert('rotation_euler', index=1, frame=1)
    pivot.rotation_euler.y = tau * turns
    pivot.keyframe_insert('rotation_euler', index=1, frame=PERIOD + 1)
    curve, = pivot.animation_data.action.fcurves
    cycle = curve.modifiers.new('CYCLES')
    cycle.mode_after = cycle.mode_before = 'REPEAT_OFFSET'
    for key in curve.keyframe_points:
        key.interpolation = 'LINEAR'


def drive_links(loop, bronze, pins):
    # The existing 20- and 12-tooth gears advance 24 teeth per shot.
    count, advance = 42, 24
    pitch = loop.length / count
    source = bpy.data.objects['踏段チェーン 001'].data
    # Each Phase 1 link is made from two plates and a pin per side. Reuse the
    # near-side faces and normalize their origin to the drive chain plane.
    faces = [face for face in source.polygons if face.center.y < 0]
    source_indices = sorted({index for face in faces for index in face.vertices})
    remap = {index: local for local, index in enumerate(source_indices)}
    vertices = [(x * (pitch / (PITCH / 6)), (y + .637) * 1.22, z * .89)
                for x, y, z in (source.vertices[i].co for i in source_indices)]
    data = bpy.data.meshes.new('A5 | drive-chain plate and pin')
    data.from_pydata(vertices, [], [tuple(remap[i] for i in face.vertices) for face in faces])
    data.materials.append(bronze)
    data.materials.append(pins)
    for face, original in zip(data.polygons, faces):
        face.material_index = original.material_index
    data.update()

    for index in range(count):
        link = bpy.data.objects.new(f'A5 | drive chain {index + 1:02}', data)
        bpy.context.collection.objects.link(link)
        previous = None
        for frame in range(1, PERIOD + 2):
            # The swept centerline is counterclockwise in X/Z; the positive-Y
            # shaft rotations are clockwise. Align plates between their pins.
            distance = (index - advance * (frame - 1) / PERIOD) * pitch
            a, _ = loop.sample(distance - pitch / 2)
            b, _ = loop.sample(distance + pitch / 2)
            center = (a + b) / 2
            angle = -atan2(b.y - a.y, b.x - a.x)
            if previous is not None:
                angle += tau * round((previous - angle) / tau)
            previous = angle
            link.location = (center.x, -.711, center.y)
            link.rotation_euler.y = angle
            link.keyframe_insert('location', frame=frame)
            link.keyframe_insert('rotation_euler', index=1, frame=frame)
        for curve in link.animation_data.action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation = 'LINEAR'


def build_drive(scene, track):
    upper_x, rise = track.upper
    scene.camera = bpy.data.objects['QC | upper drive']
    set_camera(scene.camera, (upper_x + .29, -.12, rise - .32), (4.95, -7, 2.65), 3.05)
    hide(bpy.data.objects['上下階スラブ・支持アングル'])
    hide(bpy.data.objects['上下階 櫛板・乗降板 | interleaved comb teeth'])

    motor = bpy.data.objects['モーター・減速機・取付台']
    motor_shell = shaded('A5 | motor cutaway', 'Motor | blue', (.028, .18, .42), .34)
    reducer_shell = shaded('A5 | reducer cutaway', 'Reducer | cast steel', (.42, .20, .08), .27)
    replace_material(motor, 'Motor | blue', motor_shell)
    replace_material(motor, 'Reducer | cast steel', reducer_shell)
    steel = bpy.data.materials['Axle and roller pins']
    warm = (.95, .29, .043)
    motor_light = shaded('A5 | motor rotor', 'Handrail drive | orange', warm)
    reducer_light = shaded('A5 | reduction output', 'Handrail drive | orange', warm)
    chain_light = shaded('A5 | drive chain', 'Step chain | bronze steel', (.72, .24, .053))
    main_light = shaded('A5 | main drive sprocket', 'Handrail drive | orange', warm)
    step_light = shaded('A5 | step chain', 'Step chain | bronze steel', (.59, .285, .09))
    for mat, peak, width, strength in ((motor_light, 4, 19, 3.0),
                                       (reducer_light, 26, 23, 2.7),
                                       (chain_light, 48, 25, 1.8),
                                       (main_light, 69, 25, 1.9),
                                       (step_light, 92, 29, 1.8)):
        highlight(mat, peak, width, strength=strength)
    replace_material(bpy.data.objects['出力スプロケット'], 'Sprocket | machined steel', reducer_light)
    replace_material(bpy.data.objects['主駆動スプロケット'], 'Sprocket | machined steel', main_light)
    for obj in bpy.data.objects:
        if obj.name.startswith(('踏段チェーン ', '三角リンク ')):
            replace_material(obj, 'Step chain | bronze steel', step_light)

    center = (upper_x + .89, rise - .42)
    rotor('A5 | motor input rotor', center, .225, .092, .338, steel, motor_light, 13)
    rotor('A5 | reducer output shaft', center, -.169, .104, .294, steel, reducer_light, 2)
    static_chain = bpy.data.objects['駆動チェーン | reducer to main shaft']
    drive_links(Loop(static_chain), chain_light, steel)
    hide(static_chain)


def moving_belt_surface(obj, rail):
    """Move subtle transverse bands along the existing near rubber sweep."""
    original = bpy.data.materials['Handrail belt | rubber']
    obj.data.materials.append(original.copy())
    rubber = obj.data.materials[-1]
    rubber.name = 'A6 | moving near handrail rubber'
    attribute = obj.data.attributes.new('Belt distance', 'FLOAT', 'CORNER')
    distance_by_vertex = dict(zip(rail.indices, (s for s in rail.distances[:-1] for _ in range(4))))
    last_vertex = rail.indices[-1]
    for face in obj.data.polygons:
        if max(face.vertices) > last_vertex:
            break
        face.material_index = len(obj.data.materials) - 1
        closes_loop = min(face.vertices) < 4 and max(face.vertices) >= last_vertex - 3
        for loop_index, vertex in zip(face.loop_indices, face.vertices):
            distance = distance_by_vertex[vertex]
            attribute.data[loop_index].value = rail.length if closes_loop and vertex < 4 else distance

    nodes, links = rubber.node_tree.nodes, rubber.node_tree.links
    coord = nodes.new('ShaderNodeAttribute')
    coord.attribute_name = attribute.name
    travel = nodes.new('ShaderNodeMath')
    travel.operation = 'SUBTRACT'
    links.new(coord.outputs['Fac'], travel.inputs[0])
    for frame, distance in ((1, 0), (PERIOD + 1, TRAVEL * RAIL_RATIO)):
        travel.inputs[1].default_value = distance
        travel.inputs[1].keyframe_insert('default_value', frame=frame)
    for key in rubber.node_tree.animation_data.action.fcurves[0].keyframe_points:
        key.interpolation = 'LINEAR'
    frequency = nodes.new('ShaderNodeMath')
    frequency.operation = 'MULTIPLY'
    frequency.inputs[1].default_value = tau * round(rail.length / .12) / rail.length
    links.new(travel.outputs[0], frequency.inputs[0])
    wave = nodes.new('ShaderNodeMath')
    wave.operation = 'SINE'
    links.new(frequency.outputs[0], wave.inputs[0])
    ramp = nodes.new('ShaderNodeMapRange')
    ramp.inputs['From Min'].default_value = -1
    ramp.inputs['To Min'].default_value = .29
    ramp.inputs['To Max'].default_value = .46
    links.new(wave.outputs[0], ramp.inputs[0])
    links.new(ramp.outputs[0], principled(rubber).inputs['Roughness'])


def build_handrail(scene, track):
    upper_x, rise = track.upper
    scene.camera = bpy.data.objects['QC | upper landing']
    set_camera(scene.camera, (upper_x - 1.28, -.08, rise + .43), (0, -7, 3.9), 4.30)
    marker = shaded('A6 | comparison dots', 'Tread | cast aluminum', (.045, .86, .78))
    principled(marker).inputs['Emission Strength'].default_value = 1.35
    trim = shaded('A6 | comparison dot rims', 'Handrail belt | rubber', (.015, .027, .037))

    step = bpy.data.objects['踏段 16 | tread and riser']
    offset_x = -.134
    foot = cylinder('A6 | tread marker rim', .047, .007, (offset_x, .06, .121), trim, step)
    cylinder('A6 | tread marker dot', .031, .003, (0, 0, .0045), marker, foot)

    belt = bpy.data.objects['手摺りベルト・案内ローラ・連結ベルト']
    rail = Loop(belt)
    moving_belt_surface(belt, rail)
    initial_x = track.state(15 * PITCH)[1][0] + offset_x
    start = rail.uphill_distance_at(initial_x)
    _, tangent = rail.sample(start)
    # Align the dot tops in camera X, accounting for the offset from the belt centerline.
    start = rail.uphill_distance_at(initial_x + tangent.y * .031)
    rail_dot = cylinder('A6 | handrail marker rim', .047, .007, (0, 0, 0), trim)
    cylinder('A6 | handrail marker dot', .031, .003, (0, 0, .0045), marker, rail_dot)
    for frame in range(1, PERIOD + 2):
        point, tangent = rail.sample(start + (frame - 1) * TRAVEL * RAIL_RATIO / PERIOD)
        outward = Vector((-tangent.y, tangent.x))
        point += outward * .0265
        rail_dot.location = (point.x, -.689, point.y)
        rail_dot.rotation_euler.y = -atan2(tangent.y, tangent.x)
        rail_dot.keyframe_insert('location', frame=frame)
        rail_dot.keyframe_insert('rotation_euler', index=1, frame=frame)
    for curve in rail_dot.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('shot', choices=('a5', 'a6'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    scene = bpy.context.scene
    track = Track()
    cutaway()
    build = build_drive if args.shot == 'a5' else build_handrail
    build(scene, track)
    scene.name = 'A5 | Drive' if args.shot == 'a5' else 'A6 | Handrail sync'
    scene.timeline_markers.clear()
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = -.45
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.eevee.taa_render_samples = 16
    scene.render.fps = 24
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.image_settings.compression = 15
    scene.frame_start = 1
    scene.frame_end = PERIOD
    scene.frame_set(1)
    bpy.context.preferences.filepaths.save_version = 0
    filename = args.output or PRODUCTION / f'escalator_{args.shot}.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(filename.resolve()), compress=True)


if __name__ == '__main__':
    main()
