"""Build the Phase 1 assembly. Run with blender -b --python production/build_escalator.py."""
from math import acos, atan2, cos, hypot, pi, sin
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from track import AXLE_OFFSET, PITCH, RADIUS, REAR_AXLE, STEP_COUNT, Track

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
track = Track()
upper_x, rise = track.upper
deck_height = AXLE_OFFSET + .118
fps = 24
period = 120
travel = 6 * PITCH
materials = {}


def material(name, color, metallic=0., roughness=.4, opacity=1.):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    shader = nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    if opacity < 1:
        mat.surface_render_method = 'BLENDED'
        mix = nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = opacity
        links = mat.node_tree.links
        links.new(nodes.new('ShaderNodeBsdfTransparent').outputs[0], mix.inputs[1])
        links.new(shader.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], nodes.get('Material Output').inputs['Surface'])
    materials[name] = mat


material('Tread | cast aluminum', (.31,.36,.43), .64)
material('Groove | recessed aluminum', (.105,.13,.17), .52)
material('Yellow demarcation', (.95,.59,.024), .22)
material('Wheel | blue', (.024,.21,.65), .35)
material('Axle and roller pins', (.47,.55,.64), .55)
material('Step chain | bronze steel', (.49,.26,.095), .62)
material('Front guide rail', (.13,.36,.43), .55)
material('Rear guide rail', (.13,.48,.32), .48)
material('Truss | painted steel', (.246,.35,.47), .52)
material('Floor slab', (.29,.32,.38))
material('Landing | brushed metal', (.37,.43,.50), .58)
material('Comb teeth', (.84,.54,.17), .48)
material('Motor | blue', (.034,.21,.54), .46)
material('Reducer | cast steel', (.16,.25,.34), .53)
material('Sprocket | machined steel', (.38,.44,.53), .67)
material('Handrail belt | rubber', (.055,.081,.11), .12)
material('Handrail drive | orange', (.85,.25,.052), .43)
material('Balustrade | far glass', (.19,.40,.53), .25, opacity=.18)
material('Balustrade | near glass', (.19,.40,.53), .25, opacity=.045)
material('Skirt guard | blue steel', (.12,.185,.24), .48)


def collection(name):
    result = bpy.data.collections.new(name)
    scene.collection.children.link(result)
    return result


m1 = collection('M1  全体・トラス・案内レール')
m2 = collection('M2  踏段・前輪・後輪・踏段チェーン')
m3 = collection('M3  上部機械室・駆動部')
m4 = collection('M4  手摺りベルト・欄干')
m5 = collection('M5  櫛板・乗降板')
studio = collection('Phase 1  QC cameras and lighting')


class Mesh:
    """Build joined primitive meshes with face-level material assignments."""
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.face_materials = []

    def add(self, vertices, faces, mat):
        base = len(self.vertices)
        self.vertices.extend(vertices)
        self.faces.extend(tuple(base+i for i in face) for face in faces)
        self.face_materials.extend([mat] * len(faces))

    def prism(self, profile, y0, y1, mat):
        n = len(profile)
        self.add([(x,y,z) for y in (y0,y1) for x,z in profile],
                 [tuple(range(n)), tuple(reversed(range(n,2*n)))] +
                 [(i,i+n,(i+1)%n+n,(i+1)%n) for i in range(n)], mat)

    def box(self, center, size, mat):
        x,y,z = center
        a,b,c = (dimension/2 for dimension in size)
        self.prism([(x-a,z-c),(x+a,z-c),(x+a,z+c),(x-a,z+c)], y-b,y+b,mat)

    def cylinder(self, x, y, z, r, width, mat, segments=24):
        profile = [(x+r*cos(i*2*pi/segments),z+r*sin(i*2*pi/segments))
                   for i in range(segments)]
        self.prism(profile,y-width/2,y+width/2,mat)

    def gear(self, x, y, z, r, width, teeth, mat):
        profile = []
        for i in range(teeth):
            for fraction, radius in ((0,r-.017),(.24,r+.010),(.62,r+.010),(.84,r-.017)):
                angle = 2*pi*(i+fraction)/teeth
                profile.append((x+radius*cos(angle),z+radius*sin(angle)))
        self.prism(profile,y-width/2,y+width/2,mat)

    def beam(self, a, b, y, width, height, mat):
        dx,dz = b[0]-a[0],b[1]-a[1]
        scale = height/(2*hypot(dx,dz))
        ox,oz = -dz*scale,dx*scale
        self.prism([(a[0]-ox,a[1]-oz),(b[0]-ox,b[1]-oz),
                    (b[0]+ox,b[1]+oz),(a[0]+ox,a[1]+oz)],
                   y-width/2,y+width/2,mat)

    def sweep(self, path, y, width, height, mat, closed=False):
        vertices = []
        for i, (x,z) in enumerate(path):
            a = path[i-1] if i or closed else path[0]
            b = path[(i+1)%len(path)] if i+1 < len(path) or closed else path[-1]
            dx,dz = b[0]-a[0],b[1]-a[1]
            scale = height/(2*hypot(dx,dz))
            ox,oz = -dz*scale,dx*scale
            vertices.extend([(x-ox,y-width/2,z-oz),(x-ox,y+width/2,z-oz),
                             (x+ox,y+width/2,z+oz),(x+ox,y-width/2,z+oz)])
        faces = []
        for i in range(len(path) if closed else len(path)-1):
            j = (i+1)%len(path)
            faces.extend((4*i+k,4*i+(k+1)%4,4*j+(k+1)%4,4*j+k)
                         for k in range(4))
        if not closed:
            faces.extend([(3,2,1,0),tuple(range(len(vertices)-4,len(vertices)))])
        self.add(vertices,faces,mat)

    def object(self, name, group):
        data = bpy.data.meshes.new(name)
        data.from_pydata(self.vertices, [], self.faces)
        slots = {name:i for i,name in enumerate(dict.fromkeys(self.face_materials))}
        for label in slots:
            data.materials.append(materials[label])
        data.polygons.foreach_set('material_index', [slots[label] for label in self.face_materials])
        data.update()
        return linked(name, data, group)


def linked(name, data, group):
    obj = bpy.data.objects.new(name, data)
    group.objects.link(obj)
    return obj


# The uphill front axle is outboard of the rear axle. The rib ends are
# aligned with the matching comb teeth by sharing the transverse pitch.
width = 1.004
rib_pitch = .024
rib_positions = [i*rib_pitch for i in range(-20,21)]
step = Mesh()
step.box((-.122,0,.095),(.391,width,.027),'Groove | recessed aluminum')
# Sweep the neighboring tread corner past the riser on both straight
# branches. The sampled envelope allows for the shorter horizontal axle
# separation in the transitions while maintaining a visible stair face.
neighbor_offsets = []
for i in range(6000):
    distance = track.length*i/6000
    _, previous, _, previous_angle = track.state(distance-PITCH)
    _, current, _, current_angle = track.state(distance)
    if abs(sin(current_angle)) < 1e-7 and cos(previous_angle-current_angle) > 1-1e-10:
        direction = cos(current_angle)
        neighbor_offsets.append(((previous[0]-current[0])*direction,
                                 (previous[1]-current[1])*direction))
riser_edge = []
for z in (.108,.086,.061,.036,.011,-.014,-.039,-.064,-.089,-.108):
    envelope = max(dx for dx,dz in neighbor_offsets if .081+dz <= z+.014 and .118+dz >= z-.014)
    riser_edge.append((max(-.316,.0735+envelope+.007),z))

riser = riser_edge + [(x+.013,z) for x,z in reversed(riser_edge)]
step.prism(riser,-.491,.491,'Groove | recessed aluminum')
for y in rib_positions:
    mat = 'Yellow demarcation' if abs(y) > .45 else 'Tread | cast aluminum'
    step.box((-.137,y,.112),(.360,.012,.012),mat)
    step.box((.055,y,.112),(.028,.012,.012),'Yellow demarcation')
    step.prism([(x-.003,z) for x,z in riser_edge]+riser_edge[::-1],
               y-.005,y+.005,mat)
for sign in (-1,1):
    step.prism([(-.26,.082),(.065,.082),(.016,-.025),
                (-.17,-.117),(-.261,-.139),(-.242,-.088)],
               sign*.398-.027,sign*.398+.027,'Tread | cast aluminum')
step.cylinder(0,0,0,.018,1.19,'Axle and roller pins')
step.cylinder(REAR_AXLE[0],0,REAR_AXLE[1],.017,1.02,'Axle and roller pins')
template = step.object('踏段 01 | tread and riser',m2)
steps = [template] + [linked(f'踏段 {i+1:02d} | tread and riser',template.data,m2)
                      for i in range(1,STEP_COUNT)]


def wheel_pair(y,radius,name):
    mesh = Mesh()
    for sign in (-1,1):
        mesh.cylinder(0,sign*y,0,radius,.040,'Wheel | blue')
        mesh.cylinder(0,sign*y,0,radius*.43,.051,'Axle and roller pins')
        for i in range(6):
            theta = i*pi/3
            mesh.cylinder(radius*.56*cos(theta),sign*y,radius*.56*sin(theta),
                          .005,.044,'Axle and roller pins',10)
    return [mesh.object(name+' 01',m2)]


front_wheels = wheel_pair(.58,.044,'前輪')
rear_wheels = wheel_pair(.484,.037,'後輪')
for pair in (front_wheels,rear_wheels):
    for i in range(1,STEP_COUNT):
        pair.append(linked(f'{pair[0].name[:-2]}{i+1:02d}',pair[0].data,m2))

chain = Mesh()
link_pitch = PITCH/6
for sign in (-1,1):
    y = sign*.637
    for side in (-1,1):
        chain.box((0,y+side*.011,0),(link_pitch+.010,.009,.027),'Step chain | bronze steel')
    chain.cylinder(-link_pitch/2,y,0,.010,.036,'Axle and roller pins',10)
chain_template = chain.object('踏段チェーン 001',m2)
links = [chain_template] + [linked(f'踏段チェーン {i+1:03d}',chain_template.data,m2)
                           for i in range(1,STEP_COUNT*6)]
attachment = Mesh()
for s in (-1,1):
    attachment.prism([(-link_pitch/2,0),(link_pitch/2,0),(0,AXLE_OFFSET+.012)],
                     s*.637-.009,s*.637+.009,'Step chain | bronze steel')
    attachment.cylinder(0,s*.611,AXLE_OFFSET,.014,.094,'Axle and roller pins',14)
attachment_template = attachment.object('三角リンク 01',m2)
attachments = [attachment_template] + [
    linked(f'三角リンク {i+1:02d}',attachment_template.data,m2) for i in range(1,STEP_COUNT)]

rail = Mesh()
states = [track.state(track.length*i/640) for i in range(640)]
for y, radius, state_index, mat in ((.58,.044,1,'Front guide rail'),
                                    (.484,.037,2,'Rear guide rail')):
    centers = [state[state_index] for state in states]
    running_face = []
    for i,(x,z) in enumerate(centers):
        a,b = centers[i-1],centers[(i+1)%len(centers)]
        dx,dz = b[0]-a[0],b[1]-a[1]
        scale = (radius+.009)/hypot(dx,dz)
        running_face.append((x+dz*scale,z-dx*scale))
    for sign in (-1,1):
        rail.sweep(running_face,sign*y,.061,.018,mat,closed=True)
rail.object('前輪案内レール・後輪案内レール | running faces',m1)


def motion(obj, frame, position, angle):
    x, z = position
    obj.location = (x, 0, z)
    obj.rotation_euler.y = angle
    obj.keyframe_insert('location',index=0,frame=frame,group='A1')
    obj.keyframe_insert('location',index=2,frame=frame,group='A1')
    obj.keyframe_insert('rotation_euler',index=1,frame=frame,group='A1')


def periodic(obj):
    for curve in obj.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
        modifier = curve.modifiers.new('CYCLES')
        if curve.data_path == 'rotation_euler':
            modifier.mode_before = modifier.mode_after = 'REPEAT_OFFSET'


for i,obj in enumerate(steps):
    previous_normal = None
    for frame in range(1,period+2):
        distance = i*PITCH + travel*(frame-1)/period
        center,front,rear,angle = track.state(distance)
        turns = int(distance/track.length)
        motion(obj,frame,front,angle+turns*2*pi)
        normal = -atan2(front[0]-center[0],front[1]-center[1])
        if previous_normal is not None:
            normal += 2*pi*round((previous_normal-normal)/(2*pi))
        previous_normal = normal
        motion(attachments[i],frame,center,normal)
        motion(front_wheels[i],frame,front,distance/PITCH * 9*pi/3)
        motion(rear_wheels[i],frame,rear,distance/PITCH * 11*pi/3)
for i,obj in enumerate(links):
    previous_angle = None
    for frame in range(1,period+2):
        distance = i*link_pitch + travel*(frame-1)/period
        a = track.state(distance-link_pitch/2)[0]
        b = track.state(distance+link_pitch/2)[0]
        angle = -atan2(b[1]-a[1],b[0]-a[0])
        if previous_angle is not None:
            angle += 2*pi*round((previous_angle-angle)/(2*pi))
        previous_angle = angle
        motion(obj,frame,((a[0]+b[0])/2,(a[1]+b[1])/2),angle)
for obj in steps+attachments+front_wheels+rear_wheels+links:
    # A given object takes 50 pitches to return. The rendered belt repeats
    # after six pitches because all step assemblies are interchangeable.
    for curve in obj.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'

# Truss chords and web members bridge between the two floor support angles.
truss = Mesh()
profile = [(-.55,0),(.95,0),(2.46,.42),(upper_x-2.35,rise-.42),
           (upper_x-1.0,rise),(upper_x+1.18,rise)]
for sign in (-1,1):
    y = sign*.745
    for a,b in zip(profile,profile[1:]):
        panels = max(1,round(hypot(b[0]-a[0],b[1]-a[1])/.73))
        def point(i,depth):
            t = i/panels
            return (a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])-depth)
        for depth in (.11,.86):
            truss.beam(point(0,depth),point(panels,depth),y,.078,.075,'Truss | painted steel')
        for i in range(panels):
            x,z = point(i,.86)
            truss.beam(point(i,.86),point(i,.11),y,.061,.060,'Truss | painted steel')
            truss.beam(point(i,.11),point(i+1,.86),y,.055,.055,'Truss | painted steel')
            truss.box((x,0,z),(.075,1.55,.07),'Truss | painted steel')
    truss.beam((profile[-1][0],rise-.86),(profile[-1][0],rise-.11),y,.078,.075,'Truss | painted steel')
truss_obj = truss.object('トラス | toggle Transparency in Custom Properties',m1)
truss_obj['Transparency'] = 1.0
truss_obj.id_properties_ui('Transparency').update(min=0.,max=1.,
    description='1: translucent cutaway, 0: opaque. Material switch for this truss.')
truss_mat = materials['Truss | painted steel']
truss_mat.surface_render_method = 'BLENDED'
nodes = truss_mat.node_tree.nodes
mix = nodes.new('ShaderNodeMixShader')
links_nodes = truss_mat.node_tree.links
links_nodes.new(nodes.get('Principled BSDF').outputs[0],mix.inputs[1])
links_nodes.new(nodes.new('ShaderNodeBsdfTransparent').outputs[0],mix.inputs[2])
links_nodes.new(mix.outputs[0],nodes.get('Material Output').inputs['Surface'])
driver = mix.inputs[0].driver_add('default_value').driver
var = driver.variables.new()
var.name = 'transparency'
var.targets[0].id = truss_obj
var.targets[0].data_path = '["Transparency"]'
driver.expression = '0.86*transparency'

floor = Mesh()
for x,z in ((-1.34,0),(upper_x+2.0,rise)):
    floor.box((x,0,z+deck_height-.185),(1.5,1.8,.37),'Floor slab')
    floor.box((x,0,z+deck_height-.014),(1.51,1.82,.028),'Landing | brushed metal')
for x,z in ((-.57,0),(upper_x+1.23,rise)):
    floor.box((x,0,z-.16),(.19,1.58,.08),'Axle and roller pins')
floor.object('上下階スラブ・支持アングル',m1)

landing_mesh = Mesh()
for sign,z,edge in ((-1,0,.25),(1,rise,upper_x-.40)):
    end = -.60 if sign < 0 else upper_x+1.25
    landing_mesh.box(((edge+end)/2,0,z+deck_height-.014),
                     (abs(edge-end),1.22,.028),'Landing | brushed metal')
    for y in rib_positions[:-1]:
        tip = edge-sign*.105
        landing_mesh.prism([(edge,z+deck_height),(tip,z+deck_height-.009),
                            (tip,z+deck_height-.015),(edge,z+deck_height-.023)],
                           y+.008,y+.016,'Comb teeth')
landing_mesh.object('上下階 櫛板・乗降板 | interleaved comb teeth',m5)

# Upper machinery lies behind the main shaft, beneath the upper landing.
def animate_gear(obj, x, z, radians):
    for frame, angle in ((1,0),(period+1,radians)):
        motion(obj,frame,(x,z),angle)
    periodic(obj)


for x,z,label in ((0,-RADIUS,'従動スプロケット'),
                  (upper_x,rise-RADIUS,'主駆動スプロケット')):
    gear = Mesh()
    gear.cylinder(0,0,0,.059,1.42,'Axle and roller pins')
    for sign in (-1,1):
        gear.gear(0,sign*.637,0,RADIUS,.032,30,'Sprocket | machined steel')
        gear.cylinder(0,sign*.637,0,.105,.071,'Reducer | cast steel')
    if x:
        gear.gear(0,-.711,0,.211,.027,20,'Sprocket | machined steel')
    animate_gear(gear.object(label,m3),x,z,2*pi*36/30)

motor_x,motor_z = upper_x+.89,rise-.42
drive = Mesh()
drive.cylinder(motor_x,.23,motor_z,.149,.39,'Motor | blue',32)
for i in range(18):
    a = i*2*pi/18
    drive.box((motor_x+.141*cos(a),.23,motor_z+.141*sin(a)),
              (.031,.345,.031),'Motor | blue')
drive.cylinder(motor_x,.449,motor_z,.13,.057,'Reducer | cast steel')
drive.box((motor_x,-.157,motor_z),(.318,.369,.31),'Reducer | cast steel')
drive.box((motor_x,.09,motor_z+.152),(.125,.147,.064),'Motor | blue')
drive.cylinder(motor_x,-.48,motor_z,.040,.46,'Axle and roller pins')
drive.box((motor_x,.02,motor_z-.19),(.37,.89,.045),'Truss | painted steel')
drive.object('モーター・減速機・取付台',m3)
output = Mesh()
output.gear(0,-.711,0,.101,.025,12,'Sprocket | machined steel')
animate_gear(output.object('出力スプロケット',m3),motor_x,motor_z,2*pi*24/12)


def belt_path(a,b,ra,rb):
    # Common external tangents, with outward cap arcs on each pulley.
    axis = atan2(b[1]-a[1],b[0]-a[0])
    cap = acos((ra-rb)/hypot(b[0]-a[0],b[1]-a[1]))
    points = []
    for (x,z),r,start,end in ((a,ra,axis+cap,axis+2*pi-cap),
                              (b,rb,axis-cap,axis+cap)):
        points.extend((x+r*cos(start+(end-start)*i/48),z+r*sin(start+(end-start)*i/48))
                      for i in range(49))
    return points


drive_chain = Mesh()
path = belt_path((upper_x,rise-RADIUS),(motor_x,motor_z),.212,.101)
drive_chain.sweep(path,-.711,.042,.024,'Step chain | bronze steel',closed=True)
for segment,(a,b) in enumerate(zip(path,path[1:]+path[:1])):
    length = hypot(b[0]-a[0],b[1]-a[1])
    n = max(1,round(length/.048))
    for i in range(n):
        if length < .017 and segment%3:
            continue
        t = i/n
        drive_chain.cylinder(a[0]+t*(b[0]-a[0]),-.711,a[1]+t*(b[1]-a[1]),
                             .011,.054,'Axle and roller pins',10)
drive_chain.object('駆動チェーン | reducer to main shaft',m3)

# Visible handrail rises above the deck; its lower strand runs inside the
# skirt and wraps the upper drive roller before returning to the lower inlet.
handrail = Mesh()
balustrade = Mesh()
roller_x, roller_z = upper_x-1.13,rise-.15
top = [(x,z+deck_height+.91) for x,z,_,_ in track.samples[:801:8]]
top[-1] = (upper_x,rise+deck_height+.91)
outer = [(upper_x+.455*sin(pi*i/60),rise+deck_height+.455*(1+cos(pi*i/60)))
         for i in range(1,61)]
inner = [(upper_x-.54,rise+deck_height-.066),(upper_x-.84,rise-.15),
         (roller_x+.13,rise-.28),(roller_x-.055,rise-.294),
         (roller_x-.156,rise-.20),(roller_x-.15,rise-.03),
         (upper_x-1.59,rise+deck_height-.069)]
inner.extend((x,z+deck_height-.069) for x,z,_,_ in reversed(track.samples[:650:8])
             if x < upper_x-1.65 and x > .55)
inner.extend([(.36,deck_height-.069),(0,deck_height)])
lower_cap = [(-.455*sin(pi*i/60),deck_height+.455*(1-cos(pi*i/60)))
             for i in range(1,60)]
rail_loop = top+outer+inner+lower_cap
for sign in (-1,1):
    y = sign*.689
    handrail.sweep(rail_loop,y,.086,.047,'Handrail belt | rubber',closed=True)
    panel = top+outer[:56]+list(reversed([(x,z-.84) for x,z in top]))+lower_cap[7:]
    balustrade.prism(panel,y-.014,y+.014,
                      'Balustrade | near glass' if sign < 0 else 'Balustrade | far glass')
    balustrade.sweep([(x,z-.83) for x,z in top],y,.10,.106,'Skirt guard | blue steel')
    for x,z in ((.03,deck_height),(upper_x-.02,rise+deck_height)):
        balustrade.box((x,y,z+.021),(.176,.122,.093),'Skirt guard | blue steel')
    for x,z in ((upper_x-.67,rise+.065),(upper_x-1.54,rise+.09)):
        handrail.cylinder(x,y,z,.052,.083,'Handrail drive | orange')
    coupling = belt_path((roller_x,roller_z),(upper_x,rise-RADIUS),.099,.087)
    handrail.sweep(coupling,sign*.772,.025,.016,'Handrail belt | rubber',closed=True)
handrail.object('手摺りベルト・案内ローラ・連結ベルト',m4)
balustrade.object('欄干・スカートガード・インレット部',m4)
roller = Mesh()
for sign in (-1,1):
    roller.cylinder(0,sign*.689,0,.153,.086,'Handrail drive | orange',40)
    roller.gear(0,sign*.772,0,.098,.029,18,'Handrail drive | orange')
    roller.cylinder(0,sign*.747,0,.047,.08,'Axle and roller pins')
animate_gear(roller.object('手摺り駆動スプロケット・駆動ローラ',m4),
             roller_x,roller_z,2*pi*46/18)

# Orthographic QC cameras and a dark mechanism background.
def camera(name, target, offset, scale):
    data = bpy.data.cameras.new(name)
    data.type = 'ORTHO'
    data.ortho_scale = scale
    obj = linked(name,data,studio)
    obj.location = Vector(target)+Vector(offset)
    obj.rotation_euler = (-Vector(offset)).to_track_quat('-Z','Y').to_euler()
    return obj


scene.camera = camera('QC | whole loop', (upper_x*.5+.32,0,rise*.5+.06),
                      (0,-20,2.8),upper_x+5.45)
camera('QC | upper landing', (upper_x-1.10,0,rise+.06),(-2,-7,3.4),3.85)
camera('QC | upper drive', (upper_x+.24,-.18,rise-.35),(4.3,-7,3.0),3.25)


def area(name, location, target, power, size, color):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = power
    data.shape = 'DISK'
    data.size = size
    data.color = color
    data.use_shadow = False
    obj = linked(name,data,studio)
    obj.location = location
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()


area('Large front softbox',(upper_x*.4,-4,6),(upper_x*.5,0,rise/2),2800,7,(.84,.91,1))
area('Upper landing softbox',(upper_x+2,-2,7),(upper_x,0,rise),1250,4,(1,.90,.74))
area('Back rim',(upper_x*.67,4,6),(upper_x*.6,0,rise/2),2400,6,(.66,.80,1))
scene.world = bpy.data.worlds.new('Dark mechanism studio')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.018,.024,.036,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .38
scene.view_settings.view_transform = 'AgX'
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.eevee.taa_render_samples = 16
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.render.fps = fps
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.compression = 15
scene.render.filepath = '//renders/'
scene.frame_start = 1
scene.frame_end = period
scene.frame_set(1)
for name,frame in (('A1 | five-second cycle',1),('QC | upper landing',37),('QC | drive',73)):
    scene.timeline_markers.new(name,frame=frame)
bpy.context.view_layer.update()
for screen in bpy.data.screens:
    for region in screen.areas:
        if region.type == 'VIEW_3D':
            region.spaces.active.region_3d.view_perspective = 'CAMERA'
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'escalator_phase1.blend'), compress=True)
