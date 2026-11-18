"""Build the two Task D shots from the committed Phase 1 assembly.

Run once per shot from the repository root:
    blender -b production/escalator_phase1.blend --python-exit-code 1 \
        --python production/phase2/build_d.py -- a4
    blender -b production/escalator_phase1.blend --python-exit-code 1 \
        --python production/phase2/build_d.py -- a7
"""
from argparse import ArgumentParser
from math import cos, degrees, sin
from pathlib import Path
import sys

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from track import AXLE_OFFSET, PITCH, REAR_AXLE, SLOPE, STEP_COUNT, Track, progression

FPS = 24
ADVANCE = 6 * PITCH / 120
A4_DISPLACEMENT = .050
A4_FIRST_SHIFT = 61
A4_FULL_SHIFT = 80
A7_CONTACT = 56
A7_WEDGED = 62
A7_LIFT = .116


def lit_material(source, name, color, strength):
    material = bpy.data.materials[source].copy()
    material.name = name
    material.diffuse_color = (*color, 1)
    surface = material.node_tree.nodes['Principled BSDF']
    surface.inputs['Base Color'].default_value = (*color, 1)
    surface.inputs['Emission Color'].default_value = (*color, 1)
    surface.inputs['Emission Strength'].default_value = strength
    return material


def point_camera(scene, name, target, offset, width, perspective=False):
    data = bpy.data.cameras.new(name)
    if perspective:
        data.lens = data.sensor_width * Vector(offset).length / width
    else:
        data.type = 'ORTHO'
        data.ortho_scale = width
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = Vector(target) + Vector(offset)
    obj.rotation_euler = (-Vector(offset)).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = obj


def softbox(scene, target, offset, power, size):
    light = bpy.data.lights.new('A7 | 櫛板照明', 'AREA')
    light.energy = power
    light.size = size
    light.use_shadow = False
    obj = bpy.data.objects.new(light.name, light)
    scene.collection.objects.link(obj)
    obj.location = Vector(target) + Vector(offset)
    obj.rotation_euler = (-Vector(offset)).to_track_quat('-Z', 'Y').to_euler()


def make_transparent(material):
    tree = material.node_tree
    transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
    tree.links.new(transparent.outputs[0], tree.nodes['Material Output'].inputs['Surface'])
    material.surface_render_method = 'BLENDED'


def make_near_faces_transparent(obj, slot_name, cutoff):
    slot = obj.data.materials.find(slot_name)
    clear = obj.data.materials[slot].copy()
    clear.name = f'A4 cutaway | {slot_name}'
    make_transparent(clear)
    obj.data.materials.append(clear)
    for face in obj.data.polygons:
        if face.material_index == slot and face.center.y < cutoff:
            face.material_index = len(obj.data.materials) - 1


def setup(scene, frames):
    make_transparent(bpy.data.materials['Balustrade | near glass'])
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0, 0, 0, 1)
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.eevee.taa_render_samples = 16
    # Phase 1's softboxes have shadows off. Skip the unused shadow atlas.
    scene.eevee.use_shadows = False
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.render.fps_base = 1
    scene.frame_start = 1
    scene.frame_end = frames
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.timeline_markers.clear()


def animate_linear(obj, property_name, axis, values):
    for frame, value in values:
        prop = getattr(obj, property_name)
        prop[axis] = value
        obj.keyframe_insert(property_name, index=axis, frame=frame)
    for curve in obj.animation_data.action.fcurves:
        if curve.data_path == property_name and curve.array_index == axis:
            for key in curve.keyframe_points:
                key.interpolation = 'LINEAR'


def build_a4(scene, track):
    setup(scene, 120)
    make_transparent(bpy.data.materials['Balustrade | far glass'])
    enclosure = bpy.data.objects['欄干・スカートガード・インレット部']
    make_near_faces_transparent(enclosure, 'Skirt guard | blue steel', 0)
    truss = bpy.data.objects['トラス | toggle Transparency in Custom Properties']
    make_near_faces_transparent(truss, 'Truss | painted steel', -.69)
    scene.view_settings.exposure = -.5
    mid = 400  # Midpoint of the outbound deck samples in Track.
    _, _, (rail_x, rail_z), _ = track.state(track.distances[mid])

    def rear_locus(x):
        return rail_z + SLOPE * (x - rail_x)

    def displacement(x):
        # Fade the rail back into the existing track outside the shot.
        t = min(1, max(0, (abs(x - rail_x) - 1.10) / .52))
        return A4_DISPLACEMENT * (1 - progression(t))

    def lift(frame):
        t = (frame - A4_FIRST_SHIFT + 1) / (A4_FULL_SHIFT - A4_FIRST_SHIFT + 1)
        return progression(min(1, max(0, t)))

    rail = bpy.data.objects['前輪案内レール・後輪案内レール | running faces']
    glow = lit_material('Rear guide rail', 'A4 | 後輪案内レール発光', (.041, .77, .39), .95)
    rear_slot = rail.data.materials.find('Rear guide rail')
    rail.data.materials.append(glow)
    glow_slot = len(rail.data.materials) - 1
    moved_vertices = set()
    for face in rail.data.polygons:
        if face.material_index == rear_slot and abs(face.center.z - rear_locus(face.center.x)) < .085:
            moved_vertices.update(face.vertices)
            if displacement(face.center.x) > 0:
                face.material_index = glow_slot
    rail.shape_key_add(name='Phase 1')
    shifted = rail.shape_key_add(name='A4 | 後輪案内レールを50 mm上昇')
    for index in moved_vertices:
        vertex = shifted.data[index]
        vertex.co.z += displacement(vertex.co.x)
    for frame in range(A4_FIRST_SHIFT - 1, A4_FULL_SHIFT + 1):
        shifted.value = lift(frame)
        shifted.keyframe_insert('value', frame=frame)
    for curve in rail.data.shape_keys.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'

    def rear_axle(front, angle):
        x, z = front
        dx, dz = REAR_AXLE
        return x + dx * cos(angle) + dz * sin(angle), z - dx * sin(angle) + dz * cos(angle)

    maximum_angle = 0
    maximum_contact_error = 0
    for index in range(STEP_COUNT):
        step = bpy.data.objects[f'踏段 {index + 1:02d} | tread and riser']
        wheel = bpy.data.objects[f'後輪 {index + 1:02d}']
        angles, xs, zs = [], [], []
        for frame in range(A4_FIRST_SHIFT, scene.frame_end + 1):
            _, front, rear, normal_angle = track.state(index * PITCH + ADVANCE * (frame - 1))
            if normal_angle or abs(rear[1] - rear_locus(rear[0])) > 1e-6 or not displacement(rear[0]):
                continue
            # Keep the front axle on the chain and rear axle at its original
            # distance from it. Solve for rear wheel alignment to the shifted rail.
            lo, hi = 0, .25
            for _ in range(26):
                angle = (lo + hi) / 2
                x, z = rear_axle(front, angle)
                if z < rear_locus(x) + lift(frame) * displacement(x):
                    lo = angle
                else:
                    hi = angle
            angle = (lo + hi) / 2
            x, z = rear_axle(front, angle)
            angles.append((frame, angle))
            xs.append((frame, x))
            zs.append((frame, z))
            maximum_angle = max(maximum_angle, angle)
            maximum_contact_error = max(maximum_contact_error,
                                        abs(z - rear_locus(x) - lift(frame) * displacement(x)))
        if angles:
            animate_linear(step, 'rotation_euler', 1, angles)
            animate_linear(wheel, 'location', 0, xs)
            animate_linear(wheel, 'location', 2, zs)
    print(f'A4 最大傾斜: {degrees(maximum_angle):.3f}°, 後輪中心残差: {maximum_contact_error:.2e} m')
    x, z = track.samples[mid][:2]
    point_camera(scene, 'A4 | 傾斜部の側面', (x, -.13, z + .20), (-.36, -7, 3.85), 2.63)
    scene.timeline_markers.new('Normal', frame=1)
    scene.timeline_markers.new('Rear rail begins to rise', frame=A4_FIRST_SHIFT)
    scene.timeline_markers.new('Full displacement', frame=A4_FULL_SHIFT)


def mesh_object(name, vertices, faces, materials, material_indices, collection):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    for material in materials:
        data.materials.append(material)
    data.polygons.foreach_set('material_index', material_indices)
    data.update()
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    return obj


def landing_part(source, name, faces, map_point, materials):
    """Extract selected faces, preserving the Phase 1 mesh winding and slots."""
    indices = sorted({index for face in faces for index in face.vertices})
    local = {index: i for i, index in enumerate(indices)}
    return mesh_object(name, [map_point(source.data.vertices[i].co) for i in indices],
                       [[local[index] for index in face.vertices] for face in faces],
                       materials, [face.material_index for face in faces],
                       source.users_collection[0])


def conceal_treads_under_landing(landing_edge):
    # Tread crowns and landing top are coplanar in Phase 1. Conceal the
    # crown surface once it passes the solid plate, leaving the grooves
    # and the tread segments between the visible teeth intact.
    for name in ('Tread | cast aluminum', 'Yellow demarcation'):
        material = bpy.data.materials[name]
        tree = material.node_tree
        position = tree.nodes.new('ShaderNodeNewGeometry')
        separate = tree.nodes.new('ShaderNodeSeparateXYZ')
        compare = tree.nodes.new('ShaderNodeMath')
        compare.operation = 'GREATER_THAN'
        compare.inputs[1].default_value = landing_edge
        mix = tree.nodes.new('ShaderNodeMixShader')
        transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
        output = tree.nodes['Material Output'].inputs['Surface']
        tree.links.new(position.outputs['Position'], separate.inputs['Vector'])
        tree.links.new(separate.outputs['X'], compare.inputs[0])
        tree.links.new(compare.outputs[0], mix.inputs[0])
        tree.links.new(output.links[0].from_socket, mix.inputs[1])
        tree.links.new(transparent.outputs[0], mix.inputs[2])
        tree.links.new(mix.outputs[0], output)
        material.surface_render_method = 'BLENDED'


def build_a7(scene, track):
    setup(scene, 96)
    upper_x, rise = track.upper
    edge = upper_x - .40
    tip = edge - .105
    hinge = edge + .140
    deck = rise + AXLE_OFFSET + .118
    source = bpy.data.objects['上下階 櫛板・乗降板 | interleaved comb teeth']
    slots = list(source.data.materials)
    tooth_slot = source.data.materials.find('Comb teeth')
    upper_teeth, upper_plate, lower = [], [], []
    for face in source.data.polygons:
        if face.center.x < edge - .2:
            lower.append(face)
        elif face.material_index == tooth_slot:
            upper_teeth.append(face)
        else:
            upper_plate.append(face)

    # Split the Phase 1 landing block across a transverse hinge. The two
    # pieces fill the original outline when shut and the original teeth move with it.
    landing_part(source, 'A7 | 下階と上階固定側の乗降板', lower + upper_plate,
                 lambda p: (hinge if edge - .001 < p.x < edge + .001 else p.x, p.y, p.z),
                 slots)
    glowing_slots = slots.copy()
    glowing_slots[tooth_slot] = lit_material('Comb teeth', 'A7 | 櫛歯発光', (.84, .49, .115), .30)
    moving = landing_part(source, 'A7 | 可動櫛板', upper_plate + upper_teeth,
                          lambda p: (min(p.x, hinge) - hinge, p.y, p.z - deck), glowing_slots)
    moving.location = (hinge, 0, deck)
    bpy.data.objects.remove(source, do_unlink=True)

    # The foreign object sits across two tread ribs, with its tapered nose
    # entering a groove and catching a comb tooth. It stays where it wedges.
    debris_material = lit_material('Tread | cast aluminum', 'A7 | 異物', (.42, .042, .025), .06)
    surface = debris_material.node_tree.nodes['Principled BSDF']
    surface.inputs['Metallic'].default_value = .12
    surface.inputs['Roughness'].default_value = .52
    profile = [(-.074, 0), (-.010, 0), (0, .004), (-.019, .012), (-.061, .016), (-.074, .009)]
    count = len(profile)
    debris = mesh_object('A7 | 異物', [(x, y, z) for y in (-.017, .017) for x, z in profile],
                         [list(range(count)), list(reversed(range(count, 2 * count)))] +
                         [(i, i + count, (i + 1) % count + count, (i + 1) % count)
                          for i in range(count)], [debris_material], [0] * (count + 2),
                         moving.users_collection[0])
    debris.location.y = -.132
    def front_axle(index, frame):
        return track.state(index * PITCH + ADVANCE * (frame - 1))[1]

    outbound = [index for index in range(STEP_COUNT)
                if track.state(index * PITCH + ADVANCE * (A7_CONTACT - 1))[3] == 0]
    carrier = min(outbound, key=lambda i: abs(front_axle(i, A7_CONTACT)[0] - tip - .17))
    nose_offset = tip - front_axle(carrier, A7_CONTACT)[0]
    approach = [(frame, front_axle(carrier, frame)) for frame in range(1, A7_CONTACT + 1)]
    animate_linear(debris, 'location', 0, [(frame, x + nose_offset) for frame, (x, _) in approach]
                   + [(A7_WEDGED, tip + .030)])
    animate_linear(debris, 'location', 2, [(frame, z + .119) for frame, (_, z) in approach])
    animate_linear(moving, 'rotation_euler', 1, [(1, 0), (A7_CONTACT, 0),
                                               (A7_CONTACT + 1, .046),
                                               (A7_WEDGED, A7_LIFT),
                                               (A7_WEDGED + 3, A7_LIFT - .010),
                                               (A7_WEDGED + 7, A7_LIFT - .004)])
    conceal_treads_under_landing(edge)
    scene.view_settings.exposure = -.90
    target = (edge - .20, -.055, deck + .025)
    point_camera(scene, 'A7 | 上階の櫛板', target, (-.54, -.31, 1.25), 1.46, perspective=True)
    softbox(scene, target, (-.8, -1.2, 1.35), 70, 1.35)
    scene.timeline_markers.new('Treads pass under the comb', frame=1)
    scene.timeline_markers.new('Foreign object reaches the teeth', frame=A7_CONTACT)
    scene.timeline_markers.new('Comb plate lifted', frame=A7_WEDGED)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('shot', choices=('a4', 'a7'))
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if Path(bpy.data.filepath).resolve() != HERE.parent / 'escalator_phase1.blend':
        parser.error('Open production/escalator_phase1.blend as the base file.')
    scene = bpy.context.scene
    track = Track()
    if args.shot == 'a4':
        build_a4(scene, track)
    else:
        build_a7(scene, track)
    scene.render.filepath = '//../renders/'
    scene.frame_set(scene.frame_start)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f'escalator_{args.shot}.blend'), compress=True)


if __name__ == '__main__':
    main()
