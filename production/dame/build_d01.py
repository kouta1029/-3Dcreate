"""Build the reusable D01 asset and Phase A review scenes in Blender 4.3.2."""

from math import cos, exp, pi, sin, sqrt, tau
from pathlib import Path
import random

import bpy
from mathutils import Vector, noise

ROOT = Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)


def collection(name, parent=None):
    group = bpy.data.collections.new(name)
    if parent is not None:
        parent.children.link(group)
    return group


def add_object(name, data, group, location=(0, 0, 0)):
    obj = bpy.data.objects.new(name, data)
    group.objects.link(obj)
    obj.location = location
    return obj


def mesh_object(name, group, vertices, faces, material, smooth=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = add_object(name, mesh, group)
    if material:
        mesh.materials.append(material)
    if smooth:
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    return obj


def bevel(obj, width, segments=3):
    modifier = obj.modifiers.new("Manufactured edge radius", "BEVEL")
    modifier.width = width
    modifier.segments = segments
    modifier = obj.modifiers.new("Face-weighted normals", "WEIGHTED_NORMAL")
    modifier.keep_sharp = True


def box(name, group, center, size, material, rounding=0):
    x, y, z = (dim / 2 for dim in size)
    vertices = [
        (-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
        (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z),
    ]
    faces = [(3, 2, 1, 0), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
    obj = mesh_object(name, group, vertices, faces, material)
    obj.location = center
    if rounding:
        bevel(obj, rounding)
    return obj


def lathe(name, group, center, profile, material, count=96):
    vertices = [(r * cos(tau * i / count), r * sin(tau * i / count), z)
                for r, z in profile for i in range(count)]
    faces = []
    for ring in range(len(profile) - 1):
        for i in range(count):
            j = (i + 1) % count
            b, c = ring * count, (ring + 1) * count
            faces.append((b + i, b + j, c + j, c + i))
    return mesh_at(name, group, center, vertices, faces, material, smooth=True)


def mesh_at(name, group, center, vertices, faces, material, smooth=False):
    obj = mesh_object(name, group, vertices, faces, material, smooth)
    obj.location = center
    return obj


def cylinder(name, group, center, radius, depth, material, axis="Z", count=64):
    r = min(depth * .16, radius * .15, .0011)
    profile = [(0, -depth / 2), (radius - r, -depth / 2),
               (radius, -depth / 2 + r), (radius, depth / 2 - r),
               (radius - r, depth / 2), (0, depth / 2)]
    obj = lathe(name, group, center, profile, material, count)
    if axis == "X":
        obj.rotation_euler.y = pi / 2
    if axis == "Y":
        obj.rotation_euler.x = pi / 2
    return obj


def tube(name, group, points, radius, material, closed=False):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    curve.use_fill_caps = not closed
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, coordinates in zip(spline.points, points):
        point.co = (*coordinates, 1)
    spline.use_cyclic_u = closed
    curve.materials.append(material)
    return add_object(name, curve, group)


def solidify(obj, thickness):
    modifier = obj.modifiers.new("Sheet thickness", "SOLIDIFY")
    modifier.thickness = thickness
    modifier.offset = 0


def material(name, color, metallic=0, roughness=.4):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    return mat, shader


def grain(mat, shader, scale, distance, roughness=None):
    tree = mat.node_tree
    tex = tree.nodes.new("ShaderNodeTexNoise")
    coord = tree.nodes.new("ShaderNodeTexCoord")
    tree.links.new(coord.outputs["Object"], tex.inputs["Vector"])
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = 2.0
    if distance:
        bump = tree.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = .25
        bump.inputs["Distance"].default_value = distance
        tree.links.new(tex.outputs["Fac"], bump.inputs["Height"])
        tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    if roughness:
        ramp = tree.nodes.new("ShaderNodeMapRange")
        ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = roughness
        tree.links.new(tex.outputs["Fac"], ramp.inputs["Value"])
        tree.links.new(ramp.outputs["Result"], shader.inputs["Roughness"])
    return tex


def glass_material(name, color, opacity, edge_opacity):
    mat, shader = material(name, color, .05, .16)
    shader.inputs["Coat Weight"].default_value = .22
    tree = mat.node_tree
    fresnel = tree.nodes.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.47
    ramp = tree.nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = opacity
    ramp.inputs["To Max"].default_value = edge_opacity
    tree.links.new(fresnel.outputs["Fac"], ramp.inputs["Value"])
    tree.links.new(ramp.outputs["Result"], shader.inputs["Alpha"])
    mat.surface_render_method = "DITHERED"
    return mat


def microwave_materials():
    case, shader = material("Graphite powder-coated steel", (.068, .073, .079), .56, .32)
    grain(case, shader, 1400, .00012, (.28, .39))
    enamel, shader = material("Charcoal enamel cavity", (.078, .083, .089), .38, .41)
    grain(enamel, shader, 1900, .00014, (.32, .49))
    enamel_trim, _ = material("Formed enamel details", (.093, .101, .11), .43, .32)
    bezel, _ = material("Satin black polymer", (.025, .028, .032), .12, .29)
    seam, _ = material("Gaskets and recesses", (.009, .010, .012), 0, .62)
    brushed, shader = material("Satin aluminum", (.31, .34, .37), .75, .29)
    grain(brushed, shader, 2100, 0, (.23, .37))
    section, _ = material("Uncoated cut edges", (.48, .52, .56), .81, .29)
    mica, shader = material("Warm mica waveguide cover", (.40, .306, .213), .12, .61)
    tex = grain(mica, shader, 1050, .00023)
    tint = mica.node_tree.nodes.new("ShaderNodeValToRGB")
    tint.color_ramp.elements[0].color = (.22, .155, .11, 1)
    tint.color_ramp.elements[1].color = (.55, .435, .302, 1)
    mica.node_tree.links.new(tex.outputs["Fac"], tint.inputs["Fac"])
    mica.node_tree.links.new(tint.outputs["Color"], shader.inputs["Base Color"])
    rubber, _ = material("Roller polymer", (.22, .21, .185), 0, .48)
    bulb, shader = material("Warm opal lamp diffuser", (.65, .53, .38), 0, .33)
    shader.inputs["Emission Color"].default_value = (1, .64, .35, 1)
    shader.inputs["Emission Strength"].default_value = 2.1
    glass = glass_material("Clear pressed turntable glass", (.131, .171, .180), .19, .64)
    glass.surface_render_method = "BLENDED"
    glass.use_transparency_overlap = False
    glass_rim = glass_material("Turntable thick glass lip", (.22, .29, .31), .32, .94)
    door_glass = glass_material("Smoke-tinted door glass", (.042, .054, .065), .27, .86)
    return case, enamel, enamel_trim, bezel, seam, brushed, section, mica, rubber, bulb, glass, glass_rim, door_glass


def door_screen_material():
    mat, shader = material("Door screen | round perforations", (.028, .032, .037), .65, .39)
    tree = mat.node_tree
    coord = tree.nodes.new("ShaderNodeTexCoord")
    metric = tree.nodes.new("ShaderNodeVectorMath")
    metric.operation = "MULTIPLY"
    metric.inputs[1].default_value = (172, 0, 76)
    tree.links.new(coord.outputs["Generated"], metric.inputs[0])
    cell = tree.nodes.new("ShaderNodeTexVoronoi")
    cell.inputs["Scale"].default_value = 1
    cell.inputs["Randomness"].default_value = 0
    tree.links.new(metric.outputs["Vector"], cell.inputs["Vector"])
    threshold = tree.nodes.new("ShaderNodeMath")
    threshold.operation = "GREATER_THAN"
    threshold.inputs[1].default_value = .32
    tree.links.new(cell.outputs["Distance"], threshold.inputs[0])
    tree.links.new(threshold.outputs[0], shader.inputs["Alpha"])
    mat.surface_render_method = "DITHERED"
    return mat


def perforated_left_wall(group, enamel, seam):
    """Press a regular grid of round holes through the left lining."""
    x, y0, z0 = -.214, -.073, .139
    pitch = .0044
    cols, rows, sides = 13, 9, 12
    vertices, faces = [], []
    for col in range(cols):
        for row in range(rows):
            y = y0 + (col + .5) * pitch
            z = z0 + (row + .5) * pitch
            start = len(vertices)
            for i in range(sides):
                a = tau * (i + .5) / sides
                dy, dz = cos(a), sin(a)
                square_radius = pitch / 2 / max(abs(dy), abs(dz))
                vertices.extend([(x, y + .00127 * dy, z + .00127 * dz),
                                 (x, y + square_radius * dy, z + square_radius * dz)])
            for i in range(sides):
                a, b = start + 2 * i, start + 2 * ((i + 1) % sides)
                faces.append((a, a + 1, b + 1, b))
    panel = mesh_object("Left wall | circular perforations", group, vertices, faces, enamel)
    weld = panel.modifiers.new("Join vent panel cells", "WELD")
    weld.merge_threshold = .000001
    solidify(panel, .0013)
    outer_y, outer_z = y0 + cols * pitch, z0 + rows * pitch
    # The surrounding four pieces leave the perforated insert open.
    for label, y1, y2, z1, z2 in [
        ("front", -.161, y0, .040, .250),
        ("rear", outer_y, .169, .040, .250),
        ("lower", y0, outer_y, .040, z0),
        ("upper", y0, outer_y, outer_z, .250),
    ]:
        box(f"Left enamel lining | {label}", group, (-.215, (y1+y2)/2, (z1+z2)/2),
            (.002, y2-y1, z2-z1), enamel, .0005)
    box("Recess behind left perforations", group, (-.223, (y0 + outer_y) / 2, (z0+outer_z)/2),
        (.002, outer_y-y0+.009, outer_z-z0+.009), seam, .0006)


def microwave():
    model = collection("M1_microwave")
    fixed = collection("Cabinet and cavity", model)
    door = collection("Hinged door", model)
    rotor = collection("Turntable assembly", model)
    skin = collection("Side panels | intact", model)
    section_only = collection("Cut edges | cutaway", model)
    case, enamel, lining, bezel, seam, metal, section, mica, rubber, bulb, glass, glass_rim, door_glass = microwave_materials()
    cx = -.059
    box("Upper cabinet skin", fixed, (0, .015, .285), (.480, .330, .010), case, .0048)
    box("Lower chassis", fixed, (0, .015, .020), (.478, .329, .015), case, .003)
    box("Rear outer skin", fixed, (0, .176, .151), (.475, .008, .265), case, .002)
    box("Left outer skin", fixed, (-.235, .013, .151), (.010, .328, .263), case, .002)
    box("Right cabinet skin | removable", skin, (.235, .014, .151), (.010, .327, .263), case, .002)
    for x in (-.188, .190):
        for y in (-.116, .121):
            cylinder("Isolation foot", fixed, (x, y, .007), .017, .014, seam, count=32)

    # The opening is 310 × 210 mm; the cavity runs from y=-.161 to .169.
    box("Enamel cavity floor", fixed, (cx, .004, .037), (.314, .330, .006), enamel, .0026)
    box("Enamel cavity roof", fixed, (cx, .004, .253), (.314, .330, .006), enamel, .0026)
    box("Enamel cavity rear", fixed, (cx, .172, .145), (.313, .006, .213), enamel, .0026)
    perforated_left_wall(fixed, enamel, seam)
    for label, y1, y2, z1, z2, group in [
        ("side lining | removable", -.161, .079, .040, .250, skin),
        ("rear strip", .157, .169, .040, .250, fixed),
        ("upper strip", .079, .157, .187, .250, fixed),
        ("lower strip", .079, .157, .040, .135, fixed),
        ("front jamb of port", .079, .086, .135, .187, fixed),
        ("rear jamb of port", .149, .157, .135, .187, fixed),
    ]:
        box(f"Right enamel lining | {label}", group, (.097, (y1+y2)/2, (z1+z2)/2),
            (.002, y2-y1, z2-z1), enamel, .0006)
    for z, name in [(.267, "upper"), (.028, "lower")]:
        box(f"Front flange | {name}", fixed, (-.061, -.156, z), (.344, .018, .025), bezel, .003)
    box("Front flange | hinge", fixed, (-.228, -.156, .146), (.024, .018, .249), bezel, .003)
    box("Front flange | latch", fixed, (.108, -.156, .146), (.024, .018, .250), bezel, .003)
    box("Control panel face", fixed, (.180, -.154, .149), (.117, .021, .268), case, .008)
    for index, z in enumerate((.201, .132), 1):
        cylinder(f"Dial {index} mounting ring", fixed, (.178, -.165, z), .027, .006, seam, "Y")
        cylinder(f"Dial {index} | satin trim", fixed, (.178, -.170, z), .0245, .011, metal, "Y")
        cylinder(f"Dial {index} | grip", fixed, (.178, -.175, z), .0218, .009, bezel, "Y")
        box(f"Dial {index} | finger ridge", fixed, (.178, -.179, z), (.009, .002, .028), bezel, .0008)
    for x in (.160, .195):
        box("Unmarked push button", fixed, (x, -.168, .067), (.025, .008, .020), bezel, .0035)
    for x in (-.204, .098):
        for z in (.058, .232):
            cylinder("Cavity flange fastener", fixed, (x, -.1655, z), .0022, .0011, metal, "Y", 24)

    for x in (-.183, .065):
        box("Rounded roof rib", fixed, (x, .020, .247), (.017, .252, .006), lining, .0028)
    for z, width in [(.085, .238), (.204, .260)]:
        box("Pressed rear reinforcement", fixed, (cx, .167, z), (width, .007, .025), lining, .0034)
    for x in (-.152, .033):
        points = [(x, -.050, .236), (x, .122, .236)]
        points += [(x + .013 * (1 - cos(pi*j/14)), .122 + .013*sin(pi*j/14), .236)
                   for j in range(1, 15)]
        points += [(x + .026, -.050, .236)]
        tube("Upper grill element (unpowered)", fixed, points, .0029, metal)
    box("Lamp recess", fixed, (-.182, -.088, .245), (.030, .047, .007), seam, .002)
    box("Cavity lamp | opal diffuser", fixed, (-.182, -.089, .242), (.020, .037, .0035), bulb, .0017)

    # Right-side cover and duct stay aligned in both views.
    cover = box("Mica cover | cavity face", fixed, (.094, .1175, .161),
                (.003, .069, .056), mica, .002)
    cover["part"] = "Waveguide cover on the right cavity wall"
    for y in (.087, .148):
        for z in (.140, .182):
            cylinder("Mica cover retainer", fixed, (.0919, y, z), .002, .0015, metal, "X", 24)
    for z in (.136, .186):
        box("Waveguide | horizontal wall", fixed, (.130, .1175, z), (.064, .064, .0035), metal, .001)
    box("Waveguide | rear wall", fixed, (.130, .149, .161), (.064, .0032, .048), metal, .001)
    box("Waveguide | removable front wall", skin, (.130, .086, .161), (.064, .0032, .048), metal, .001)
    for z in (.136, .186):
        box("Waveguide section | exposed edge", section_only, (.130, .085, z),
            (.063, .0028, .0035), section, .0006)
    box("Exposed enamel cut edge", section_only, (.0968, .079, .215), (.0032, .003, .058), section, .0003)
    box("Exposed enamel cut edge", section_only, (.0968, .079, .087), (.0032, .003, .091), section, .0003)
    box("Chassis side cut rail", section_only, (.226, .012, .032), (.009, .325, .013), section, .0015)
    box("Magnetron | mounting flange", fixed, (.159, .117, .147), (.009, .075, .079), metal, .002)
    box("Magnetron | shielding body", fixed, (.183, .116, .147), (.045, .060, .061), bezel, .002)
    for i in range(7):
        box(f"Magnetron | cooling fin {i+1}", fixed, (.186, .115, .122+i*.0078),
            (.049, .067, .0022), metal, .00065)
    cylinder("Magnetron | coupling housing", fixed, (.156, .118, .161), .014, .013, lining, "X")
    box("Power module | generic enclosure", fixed, (.181, .009, .056), (.067, .079, .034), case, .002)
    for i in range(5):
        box("Power module | lamination edge", fixed, (.180, -.015+i*.007, .074),
            (.057, .0022, .003), metal, .0005)

    roller_ring = add_object("Roller ring carrier", None, rotor, (cx, .002, 0))
    roller_ring.empty_display_size = .016
    ring = lathe("Three-roller guide ring", rotor, (0, 0, 0),
                 [(.091, .043), (.098, .043), (.098, .047), (.091, .047), (.091, .043)], rubber)
    ring.parent = roller_ring
    for i in range(3):
        a = i*tau/3 + .24
        roller = cylinder(f"Turntable support roller {i+1}", rotor,
                          (.0945*cos(a), .0945*sin(a), .048), .0075, .010, rubber, "X", 32)
        roller.rotation_euler.z = a
        roller.parent = roller_ring
    cylinder("Drive coupler", fixed, (cx, .002, .048), .017, .015, seam, count=48)
    plate = add_object("Turntable pivot | Ø270 mm", None, rotor, (cx, .002, .058))
    plate.empty_display_size = .018
    disc = lathe("Pressed glass dish", rotor, (0, 0, 0),
                 [(0, -.0032), (.095, -.0032), (.112, -.004), (.127, -.0033),
                  (.133, -.0008), (.135, .0014), (.134, .0033), (.130, .0039),
                  (.122, .0005), (.108, 0), (0, 0)], glass, 160)
    disc.parent = plate
    rim_profile = [(.129, -.0011), (.133, -.0015), (.135, .0008), (.135, .0022),
                   (.133, .0038), (.130, .0039), (.129, .0023), (.129, -.0011)]
    lathe("Polished glass lip", rotor, (0, 0, 0), rim_profile, glass_rim, 160).parent = plate
    lathe("Molded underside ridge", rotor, (0, 0, 0),
          [(.105, -.004), (.107, -.004), (.108, -.003), (.106, -.0028), (.105, -.004)],
          glass_rim, 128).parent = plate

    hinge = add_object("Door hinge | adjust Open Degrees", None, door, (-.225, -.164, .144))
    hinge.empty_display_size = .024
    hinge["Open Degrees"] = 0.0
    hinge.id_properties_ui("Open Degrees").update(min=0.0, max=112.0,
                                                  description="Door rotation about the left hinge")
    driver = hinge.driver_add("rotation_euler", 2).driver
    variable = driver.variables.new()
    variable.name = "opening"
    variable.targets[0].id = hinge
    variable.targets[0].data_path = '["Open Degrees"]'
    driver.expression = "-opening * 0.0174532925199433"
    for label, center, size in [
        ("lower rail", (.168, -.006, -.104), (.341, .014, .037)),
        ("upper rail", (.168, -.006, .104), (.341, .014, .037)),
        ("hinge stile", (.013, -.006, 0), (.032, .014, .183)),
        ("handle stile", (.323, -.006, 0), (.035, .014, .183)),
    ]:
        box(f"Door frame | {label}", door, center, size, bezel, .003).parent = hinge
    screen = box("Door | perforated metal screen", door, (.168, -.005, 0),
                 (.291, .0003, .185), door_screen_material())
    screen.parent = hinge
    box("Door | smoked viewing pane", door, (.168, -.010, 0),
        (.293, .004, .188), door_glass, .0014).parent = hinge
    box("Door | vertical grip", door, (.324, -.0132, .002), (.015, .0056, .155), metal, .0025).parent = hinge
    for z in (-.076, .080):
        box("Door | handle mount", door, (.324, -.012, z), (.019, .006, .014),
            bezel, .0012).parent = hinge
    for z in (-.075, .075):
        cylinder("Door hinge pin", fixed, (-.225, -.157, .144+z), .0055, .024,
                 metal, count=32)

    model["outer_mm"] = "480 × 360 × 290"
    model["cavity_mm"] = "310 × 330 × 210"
    model["turntable_mm"] = 270
    return model, door, skin, section_only, plate, roller_ring


def foil_material(name, roughness, heat=0.0, wrinkled=True):
    mat, shader = material(name, (.78, .81, .84), .96, sum(roughness) / 2)
    grain(mat, shader, 2100, .000055 if wrinkled else 0, roughness)
    if wrinkled:
        tree = mat.node_tree
        mask = tree.nodes.new("ShaderNodeAttribute")
        mask.attribute_name = "hot_edges"
        intensity = tree.nodes.new("ShaderNodeValue")
        intensity.label = "Heat intensity"
        intensity.outputs[0].default_value = heat
        multiply = tree.nodes.new("ShaderNodeMath")
        multiply.operation = "MULTIPLY"
        tree.links.new(mask.outputs["Fac"], multiply.inputs[0])
        tree.links.new(intensity.outputs[0], multiply.inputs[1])
        tree.links.new(multiply.outputs[0], shader.inputs["Emission Strength"])
        shader.inputs["Emission Color"].default_value = (1, .027, .0025, 1)
    return mat


def custom_float(obj, name, values):
    attribute = obj.data.attributes.new(name, "FLOAT", "POINT")
    attribute.data.foreach_set("value", values)


def foil_grid(name, group, rows, cols, sample, mat, thickness, closed=False):
    vertices, faces, heat = [], [], []
    stride = cols if closed else cols + 1
    for i in range(rows + 1):
        for j in range(stride):
            position, mask = sample(i / rows, j / cols)
            vertices.append(position)
            heat.append(mask)
    for i in range(rows):
        for j in range(cols):
            a = i * stride + j
            b = i * stride + ((j + 1) % stride)
            c, d = a + stride, b + stride
            if (i + j) % 2:
                faces.extend([(a, b, c), (b, d, c)])
            else:
                faces.extend([(a, b, d), (a, d, c)])
    obj = mesh_object(name, group, vertices, faces, mat, smooth=True)
    obj.data.set_sharp_from_angle(angle=.45)
    solidify(obj, thickness)
    custom_float(obj, "hot_edges", heat)
    return obj


def potato_radius(u):
    return .0298 * max(0, 1 - u*u)**.69 * (1 + .13*u + .045*sin(6*u + .7))


def sweet_potato():
    model = collection("M2_foil_wrapped_sweet_potato")
    normal = collection("M2 | unheated wrap", model)
    hot = collection("M2 | red-hot wrap", model)
    cold_foil = foil_material("M2 silver foil", (.20, .34))
    hot_foil = foil_material("M2 silver foil | red-hot edges", (.20, .34), heat=8.5)
    skin, shader = material("Sweet potato | red-purple peel", (.26, .047, .063), 0, .51)
    tex = grain(skin, shader, 420, .00042, (.45, .61))
    gradient = skin.node_tree.nodes.new("ShaderNodeValToRGB")
    gradient.color_ramp.elements[0].color = (.076, .011, .021, 1)
    gradient.color_ramp.elements[1].color = (.39, .084, .076, 1)
    skin.node_tree.links.new(tex.outputs["Fac"], gradient.inputs["Fac"])
    skin.node_tree.links.new(gradient.outputs["Color"], shader.inputs["Base Color"])

    def tuber(a, b):
        u, t = 2*a-1, tau*b
        radius = potato_radius(u) * (1+.04*sin(4*t+3*u)+.03*sin(9*t-5*u))
        return ((.075*u, .004*sin(2.4*u) + radius*cos(t),
                 .031 + .003*u + .94*radius*sin(t)), 0)

    body = foil_grid("Sweet potato | spindle and root scars", normal,
                     64, 80, tuber, skin, 0, closed=True)
    body.modifiers.clear()
    rng = random.Random(815)
    for index in range(15):
        a = rng.uniform(.10, .90)
        b = rng.random()
        points = [tuber(a + delta, b + .12*delta)[0] for delta in (-.008, -.003, .003, .008)]
        tube(f"Sweet potato | root trace {index+1}", normal, points, .00032, skin)

    def wrapped(u, t, lift=0):
        y0, z0 = .004*sin(2.4*u), .032 + .003*u + .001*cos(4*u)
        cap = min(1.0, max(0, (abs(u)-.80)/.20))
        edible = potato_radius(max(-1, min(1, 1.08*u)))
        r = edible + .0040 + .0069*cap*cap
        curl = t + 1.40*cap*cap*(1 if u < 0 else -1)
        broad = .0015 * sin(4*curl + 5*u) + .0010 * cos(7*curl - 11*u)
        crease = .00135 * (1 - abs(sin(11*curl + 19*u + 1.2*sin(8*u-2*t))))
        wrinkle = .0010 * cos(21*t - 35*u) * sin(14*u+sin(6*t))
        fine = .00058 * noise.noise_vector((u*33, cos(t)*9, sin(t)*9))[0]
        r += (broad + crease + wrinkle + fine) * (1-.40*cap)
        r += cap*.0037*cos(6*curl + (2 if u < 0 else 0))
        r = max(.001, r + lift)
        x = .086*u + cap**4*(.0020*sin(5*curl)+.0014*cos(9*curl))
        return x, y0+r*cos(curl), z0+.94*r*sin(curl)

    def wrap_surface(a, b):
        u, t = 2*a - 1, tau*b
        w = max(0, (abs(u)-.946)/.054)
        flecks = max(0, sin(9*t+11*u))**3 * (.52+.48*cos(3*t-10*u))**2
        crest = max(0, 1-5*abs(sin(11*t+19*u+1.2*sin(8*u-2*t))))
        patch = exp(-((t-2.04)/.34)**2) * (
            exp(-((u-.49)/.13)**2) + .68*exp(-((u+.32)/.18)**2)
        )
        return wrapped(u, t), .67*w*w*flecks + .44*crest*crest*patch

    shell = foil_grid("Foil wrap | pinched and twisted ends", normal,
                      136, 112, wrap_surface, cold_foil, .00013, closed=True)

    def tucked_end(side, a, b):
        # The twisted foil folds back over the potato tip inside each open lip.
        angle = -side*tau*b
        outer = wrapped(side, angle)
        center = (side*.0815, .004*sin(2.4*side), .032+.003*side+.001*cos(4*side))
        radius = 1.003*a
        x, y, z = (inner + radius*(edge-inner) for inner, edge in zip(center, outer))
        folds = sin(pi*a) * (.0011*cos(6*angle) + .00065*cos(11*angle+side))
        glints = max(0, cos(6*angle+side))**6
        return (x + side*folds, y, z), .30*a**7*glints

    folded_ends = [
        foil_grid(f"Foil wrap | tucked {label} end", normal, 15, 112,
                  lambda a, b, side=side: tucked_end(side, a, b),
                  cold_foil, .00013, closed=True)
        for label, side in [("left", -1), ("right", 1)]
    ]

    def overlap(a, b):
        u = 1.93*a-.965
        center = 1.46+.24*sin(3.5*u)+.18*u+.09*sin(15*u)
        width = .25+.052*sin(12*u+.5)+.026*sin(29*u)
        t = center + width*b
        rise = .00027 + b*b*(.00058+.00021*sin(19*u))*(.78+.22*cos(40*u))
        gleam = .18 + .82*max(0, cos(u*9.2-.7)+.25*sin(u*28))**2
        edge = max(0, (b-.60)/.40)**1.35
        heat = edge * min(1.0, gleam) * (.86+.14*sin(u*52))
        return wrapped(u, t, rise), heat

    seam = foil_grid("Foil wrap | overlapping crimped seam", normal,
                     122, 12, overlap, cold_foil, .00013)
    for obj in list(normal.objects):
        duplicate = obj.copy()
        duplicate.name = obj.name + " | hot"
        hot.objects.link(duplicate)
        if obj in (shell, seam, *folded_ends):
            duplicate.material_slots[0].link = "OBJECT"
            duplicate.material_slots[0].material = hot_foil
    model["food_mm"] = "150 × approximately 60"
    model["variant"] = "Switch between the unheated and red-hot subcollections"
    return model, normal, hot


def crumpled_foil():
    model = collection("M3_crumpled_foil")
    mat = foil_material("M3 work-hardened aluminum", (.185, .35))
    # The folds are deformations of one continuous sheet.
    folds = [
        (-.62, -.65, -.69, .20, .55, .20),
        (-.27, -.59, .91, .18, .79, -.17),
        (.34, -.53, -.83, .34, .65, .26),
        (.69, -.52, .67, .22, .42, -.16),
        (-.56, -.22, .36, .26, .54, .28),
        (-.16, -.16, -.93, .16, .58, -.22),
        (.31, -.21, .77, .25, .44, .27),
        (.72, .02, 1.97, .14, .44, .17),
        (-.72, .23, 1.26, .28, .52, .20),
        (-.32, .43, -.63, .19, .55, -.28),
        (.19, .42, .25, .18, .49, .18),
        (.58, .64, -.80, .15, .38, -.22),
        (-.26, .71, .90, .14, .36, .19),
        (-.62, .64, -.92, .19, .45, .22),
    ]

    def sheet(a, b):
        # Swap the parameters so the grid winds counterclockwise from above.
        u, v = 2*b-1, 2*a-1
        z = .23 + .064*sin(3.7*u+1.75*v) + .06*cos(4.8*v-2.45*u)
        for x0, y0, tilt, width, length, lift in folds:
            dx, dy = u-x0, v-y0
            along = dx*cos(tilt) + dy*sin(tilt)
            height = dx*sin(tilt) - dy*cos(tilt) + .27*along*along
            z += lift * max(0, 1-abs(height)/width) * exp(-2.2*(along/length)**2)
        direction = 1.7*u - .8*v
        z += .036 * (1 - abs(sin(12*u + 13*v + sin(9*v-5*u)))) * cos(3.6*direction)
        z += .018 * noise.noise_vector((12*u, 12*v, 1.6))[0]
        # A triangular flap curls back out of the far edge into the macro frame.
        peak = max(0, 1-abs(u-.35-.14*(v-1))/.44 - (1-v)/.75)
        tip = peak**1.27
        z += 1.34*tip
        z += .25 * max(0, (v-.70)/.30) * max(0, 1-abs(u+.62)/.22)
        z += .23 * max(0, (-v-.73)/.27) * max(0, 1-abs(u-.83)/.26)
        x = .110*(u + .050*sin(8*v+1.5*u) + .023*sin(21*v-4*u)) + .017*tip
        y = .088*(v + .072*sin(5.4*u) + .033*sin(17*u+2*v)) - .031*tip*tip
        return (x, y, .058*z), 0

    foil_grid("Folded sheet | continuous creases and pointed lip", model,
              156, 183, sheet, mat, .00017)
    model["macro_tip"] = "Raised fold is exaggerated for legibility"
    return model


def smooth_foil():
    model = collection("M4_smooth_foil_food")
    food, shader = material("Food | pale baked skin", (.32, .158, .078), 0, .58)
    grain(food, shader, 790, .00016)
    mat = foil_material("M4 smooth aluminum", (.21, .235), wrinkled=False)

    def dome(a, b, shell):
        angle = a * (2.17 if shell else pi)
        t = -tau*b
        radius = sin(angle)
        shape = 1+.030*cos(3*t)+.016*cos(5*t+2*angle)
        x = (.074 if shell else .0736)*radius*cos(t)*shape
        y = (.049 if shell else .0486)*radius*sin(t)*shape
        z = .031 + (.033 if shell else .0326)*cos(angle)
        return (x, y+.0017*sin(2*angle), z), 0

    lump = foil_grid("Rounded food beneath close-fitting foil", model,
                     62, 100, lambda a, b: dome(a, b, False), food, 0, closed=True)
    lump.modifiers.clear()
    foil_grid("Smooth sheet | flush folded edge", model, 57, 100,
              lambda a, b: dome(a, b, True), mat, .00010, closed=True)
    model["finish"] = "Tight to the food with no raised corners"
    return model


def kitchen():
    model = collection("M5_counter_and_wall")
    counter, shader = material("Charcoal mineral countertop", (.050, .049, .048), .03, .56)
    grain(counter, shader, 350, .00015, (.51, .64))
    wall, shader = material("Graphite painted wall", (.038, .040, .042), 0, .63)
    grain(wall, shader, 125, .00011, (.57, .71))
    box("Counter | solid worktop", model, (0, -.145, -.023), (3.60, .92, .046), counter, .0055)
    box("Wall | continuous graphite backdrop", model, (0, .342, .54), (3.60, .054, 1.08), wall)
    return model


def new_scene(name):
    scene = bpy.data.scenes.new(name)
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 16
    scene.eevee.use_raytracing = False
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 30
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -.65
    scene.world = bpy.data.worlds.new(name + " | dark studio")
    scene.world.use_nodes = True
    shade = scene.world.node_tree.nodes.get("Background")
    shade.inputs["Color"].default_value = (.19, .205, .22, 1)
    shade.inputs["Strength"].default_value = .26
    return scene


def aim(obj, point):
    obj.rotation_euler = (Vector(point)-obj.location).to_track_quat("-Z", "Y").to_euler()


def camera(scene, group, name, location, target, lens, focus=None, aperture=8):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.sensor_fit = "VERTICAL"
    data.sensor_height = 32
    data.clip_start = .004
    data.clip_end = 15
    obj = add_object(name, data, group, location)
    aim(obj, target)
    if focus is not None:
        data.dof.use_dof = True
        data.dof.focus_distance = (obj.location-Vector(focus)).length
        data.dof.aperture_fstop = aperture
    if scene.camera is None:
        scene.camera = obj
    return obj


def area(group, name, position, target, power, color, width, height):
    light = bpy.data.lights.new(name, "AREA")
    light.energy = power
    light.color = color
    light.shape = "RECTANGLE"
    light.size, light.size_y = width, height
    obj = add_object(name, light, group, position)
    aim(obj, target)
    return obj


def exclude(scene, target):
    def visit(layer):
        if layer.collection == target:
            layer.exclude = True
        else:
            for child in layer.children:
                visit(child)
    visit(scene.view_layers[0].layer_collection)


def instance(name, group, model, location):
    obj = add_object(name, None, group, location)
    obj.instance_type = "COLLECTION"
    obj.instance_collection = model
    obj.empty_display_size = .025
    return obj


def dish_contact_shadow(group, plate):
    # A soft grounding shadow on the transparent plate, rotating with the parcel.
    mat, shader = material("Parcel contact shade", (.004, .004, .004), 0, .8)
    mat.surface_render_method = "BLENDED"
    attribute = mat.node_tree.nodes.new("ShaderNodeAttribute")
    attribute.attribute_name = "opacity"
    mat.node_tree.links.new(attribute.outputs["Fac"], shader.inputs["Alpha"])
    rings = [(1, 0), (.88, .035), (.70, .10), (.49, .24), (.30, .44), (0, .49)]
    shadow = lathe("Parcel | soft contact shadow", group, (.008, 0, .00024),
                   [(radius, 0) for radius, _ in rings], mat, 48)
    shadow.scale = (.073, .033, 1)
    shadow.parent = plate
    custom_float(shadow, "opacity", [opacity for _, opacity in rings for _ in range(48)])


def measured_bounds(objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in objects:
        if obj.type not in {"MESH", "CURVE"} or obj.name not in bpy.context.view_layer.objects:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        if obj.type == "CURVE":
            mesh = evaluated.to_mesh()
            points.extend(evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
            evaluated.to_mesh_clear()
        else:
            points.extend(evaluated.matrix_world @ Vector(vertex) for vertex in evaluated.bound_box)
    return tuple(min(point[i] for point in points) for i in range(3)), tuple(
        max(point[i] for point in points) for i in range(3))


def place_in_library(group, variants, position):
    delta = Vector(position)
    for obj in group.all_objects:
        if obj.parent is None:
            obj.location += delta
    group.instance_offset = delta
    for variant in variants:
        variant.instance_offset = delta


def main():
    initial = bpy.context.scene
    m1, door, skin, cut_edges, plate, ring = microwave()
    m2, normal, hot = sweet_potato()
    m3 = crumpled_foil()
    m4 = smooth_foil()
    m5 = kitchen()

    library = new_scene("05_model_library")
    for group in (m1, m2, m3, m4, m5):
        library.collection.children.link(group)
    place_in_library(m2, (normal, hot), (.43, -.025, 0))
    place_in_library(m3, (), (.41, .171, 0))
    place_in_library(m4, (), (.43, -.186, 0))
    library_rig = collection("Library camera and lights", library.collection)
    camera(library, library_rig, "Library | front three-quarter", (.69, -1.24, .74),
           (.15, .012, .105), 26)
    camera(library, library_rig, "Microwave | front elevation", (0, -.92, .147),
           (0, 0, .147), 25)
    camera(library, library_rig, "Microwave | overhead", (0, .005, 1.13),
           (0, .005, .10), 27)
    area(library_rig, "Library | high softbox", (-.43, -.52, .84), (0, 0, 0),
         9.5, (.95, .97, 1), .56, .44)
    area(library_rig, "Library | side strip", (.78, -.18, .48), (.13, .01, .08),
         4.4, (1, .94, .87), .23, .40)
    exclude(library, cut_edges)
    exclude(library, hot)

    hero = new_scene("01_hero_interior")
    hero.frame_start, hero.frame_end = 1, 48
    hero.collection.children.link(m1)
    hero.collection.children.link(m5)
    exclude(hero, door)
    exclude(hero, cut_edges)
    rig = collection("Interior camera and lights", hero.collection)
    camera(hero, rig, "Hero | cavity three-quarter", (-.182, -.600, .257),
           (-.058, -.006, .128), 25.7)
    camera(hero, rig, "Interior | axial", (-.059, -.536, .168), (-.059, .030, .125), 28)
    area(rig, "Interior | broad front softbox", (-.18, -.295, .249), (-.059, .06, .070),
         2.2, (.91, .94, 1), .210, .145)
    area(rig, "Interior | silver strip", (.049, -.194, .132), (-.081, .029, .075),
         .88, (.94, .97, 1), .070, .184)
    area(rig, "Interior | opal lamp", (-.179, -.087, .236), (-.038, .031, .061),
         .35, (1, .75, .49), .034, .047)
    area(rig, "Interior | rear foil rim", (-.034, .142, .218), (-.057, .008, .078),
         .68, (.87, .92, 1), .148, .048)
    area(rig, "Set | exterior soft fill", (-.44, -.47, .56), (-.07, 0, .17),
         2.1, (.95, .96, 1), .40, .32)
    hero_foil = collection("Unheated parcel on the plate", hero.collection)
    parcel = instance("M2 parcel on turntable", hero_foil, normal, (0, 0, 0))
    parcel.parent = plate
    dish_contact_shadow(rig, plate)
    for pivot, turn in ((plate, tau), (ring, tau/3)):
        for frame, angle in [(1, 0), (49, turn)]:
            pivot.rotation_euler.z = angle
            pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)
        for curve in pivot.animation_data.action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation = "LINEAR"
            curve.modifiers.new("CYCLES")

    hot_scene = new_scene("02_hero_interior_hot")
    for group in (m1, m5, rig):
        hot_scene.collection.children.link(group)
    hot_scene.camera = hero.camera
    exclude(hot_scene, door)
    exclude(hot_scene, cut_edges)
    hot_foil = collection("Red-hot parcel on the plate", hot_scene.collection)
    instance("M2 red-hot parcel on turntable", hot_foil, hot, (0, 0, 0)).parent = plate

    section = new_scene("03_cutaway_side")
    section.collection.children.link(m1)
    section.collection.children.link(m5)
    exclude(section, door)
    exclude(section, skin)
    cut_rig = collection("Cutaway camera and lights", section.collection)
    camera(section, cut_rig, "Cutaway | right side three-quarter", (.825, -.533, .398),
           (.005, .009, .139), 29)
    area(cut_rig, "Cutaway | top front key", (-.26, -.48, .58), (.01, .025, .122),
         4.9, (.94, .965, 1), .44, .32)
    area(cut_rig, "Cutaway | right rectangular softbox", (.47, -.09, .38), (.04, .07, .115),
         5.4, (1, .95, .88), .27, .39)
    area(cut_rig, "Cutaway | low cavity fill", (.05, -.25, .169), (-.10, .10, .113),
         .88, (.90, .94, 1), .16, .13)
    area(cut_rig, "Cutaway | right rear rim", (.37, .237, .36), (.12, .116, .15),
         1.6, (.91, .94, 1), .17, .27)

    macro = new_scene("04_foil_macro")
    macro_rig = collection("Foil studio and cameras", macro.collection)
    instance("M3 | macro sheet", macro.collection, m3, (0, 0, 0))
    macro.world.node_tree.nodes.get("Background").inputs["Strength"].default_value = .16
    substrate, shader = material("Macro stage | soot gray", (.027, .028, .029), 0, .69)
    grain(substrate, shader, 1100, .00010)
    sweep = [(-1.2, -.009), (.22, -.009)]
    sweep += [(.22 + .22*sin(i*pi/48), -.009 + .22*(1-cos(i*pi/48))) for i in range(1, 25)]
    sweep.append((.44, .80))
    vertices = [(x, y, z) for y, z in sweep for x in (-1.4, 1.4)]
    faces = [(2*i, 2*i+1, 2*i+3, 2*i+2) for i in range(len(sweep)-1)]
    mesh_object("Macro stage | curved seamless backdrop", macro_rig, vertices, faces, substrate, True)
    camera(macro, macro_rig, "Macro | pointed far fold", (.167, -.277, .134),
           (.058, .031, .055), 57, (.054, .062, .087), aperture=13)
    camera(macro, macro_rig, "Macro | overhead alternate", (-.012, -.002, .38),
           (.003, .014, .012), 26)
    area(macro_rig, "Foil | long white key", (-.17, -.115, .24), (.004, .035, .028),
         1.23, (.95, .97, 1), .20, .075)
    area(macro_rig, "Foil | right reflection strip", (.17, .054, .148), (.008, .017, .036),
         .90, (1, .97, .93), .073, .234)
    area(macro_rig, "Foil | slim rear light", (-.055, .176, .113), (.032, .027, .045),
         .62, (.91, .95, 1), .175, .046)
    area(macro_rig, "Foil | frontal fill", (.033, -.21, .094), (.022, .021, .028),
         .22, (.94, .97, 1), .106, .106)

    for scene in (hero, hot_scene, section, macro, library):
        scene.frame_set(1)
        scene.render.filepath = "//../renders/d01/"
    bpy.context.window.scene = library
    bpy.context.view_layer.update()
    for model in (m1, m2, m3, m4, m5):
        lo, hi = measured_bounds(model.all_objects)
        print(f"D01 BOUNDS {model.name} m: " + " × ".join(f"{b-a:.5f}" for a, b in zip(lo, hi)))
    lo, hi = measured_bounds(normal.objects)
    # Seat the lowest wrinkle on the dish in both views.
    parcel.location.z = hot_foil.objects[0].location.z = -lo[2] + .00009
    bpy.context.window.scene = hero
    for screen in bpy.data.screens:
        for editor in screen.areas:
            if editor.type == "VIEW_3D":
                editor.spaces.active.region_3d.view_perspective = "CAMERA"
    bpy.data.scenes.remove(initial)
    destination = ROOT / "assets" / "d01_models.blend"
    destination.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(destination), compress=True)


if __name__ == "__main__":
    main()
