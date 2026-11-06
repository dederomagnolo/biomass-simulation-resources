"""Deterministic metric eucalyptus meshes. Python 3 stdlib; optional Blender preview.
Run: python3 utils/generate_eucalyptus.py (writes only eucalyptus assets).
"""
import math, random, json, pathlib, sys
from collections import defaultdict
from xml.dom import minidom

def pretty_xml(xml):
    return minidom.parseString(xml).toprettyxml(indent='  ', encoding='utf-8').decode('utf-8')
ROOT = pathlib.Path(__file__).resolve().parents[1]
PALETTE = [(0.66,.65,.57),(.80,.79,.70),(.48,.45,.37),(.32,.28,.22),(.24,.32,.11),(.34,.42,.16),(.18,.27,.10),(.43,.48,.23)]
SPECS = [('eucalyptus_01',18.,.18,3.0,5.8,41),('eucalyptus_02',22.,.22,3.7,7.4,73),('eucalyptus_03',26.,.28,4.2,9.0,107)]
def add(a,b): return tuple(x+y for x,y in zip(a,b))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def mul(a,t): return tuple(x*t for x in a)
def norm(a): return math.sqrt(sum(x*x for x in a))
def unit(a): return mul(a,1/max(norm(a),1e-12))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
class Mesh:
    def __init__(self): self.v=[]; self.f=[]; self.m=[]
    def face(self,pts,mat):
        k=len(self.v); self.v.extend(pts); self.f.append(tuple(range(k,k+len(pts)))); self.m.append(mat)
    def tube(self,a,b,r1,r2,mat=0,sides=8,rng=None):
        w=unit(sub(b,a)); u=unit(cross(w,(0,1,0))); v=cross(w,u)
        rings=[[add(p,mul(add(mul(u,math.cos(i*2*math.pi/sides)),mul(v,math.sin(i*2*math.pi/sides))),r)) for i in range(sides)] for p,r in [(a,r1),(b,r2)]]
        for i in range(sides):
            j=(i+1)%sides
            m=rng.choices([0,1,2,3],[45,30,20,5])[0] if rng else mat
            for ids in [(rings[0][i],rings[0][j],rings[1][j]),(rings[0][i],rings[1][j],rings[1][i])]: self.face(ids,m)
        for i in range(1,sides-1):
            self.face([rings[0][0],rings[0][i+1],rings[0][i]],mat)
            self.face([rings[1][0],rings[1][i],rings[1][i+1]],mat)
    def leaf(self,p,rng):
        length=rng.uniform(.10,.18); width=rng.uniform(.018,.035); az=rng.uniform(0,math.tau)
        d=unit((math.cos(az)*.65,math.sin(az)*.65,-rng.uniform(.4,1.0))); u=(-math.sin(az),math.cos(az),0)
        mid=add(p,mul(d,length*.42)); tip=add(p,mul(d,length)); ridge=add(mid,(0,0,.006))
        left=add(mid,mul(u,width*.5)); right=add(mid,mul(u,-width*.5))
        mat=rng.randrange(4,8)
        for tri in [(p,left,ridge),(left,tip,ridge),(tip,right,ridge),(right,p,ridge)]:
            self.face(tri,mat); self.face(tri[::-1],mat) # explicit two-sided geometry across Ogre renderers
def dae(mesh,path):
    # Explicit per-corner normals: DART does not generate missing normals.
    normals=[None]*len(mesh.v)
    for face in mesh.f:
        a,b,c=(mesh.v[i] for i in face)
        n=unit(cross(sub(b,a),sub(c,a)))
        if norm(n)<.99: raise ValueError('Degenerate triangle')
        for i in face: normals[i]=n
    normal_coords=' '.join(f'{c:.9f}' for n in normals for c in n)
    normal_source=f'<source id="normals"><float_array id="normal_array" count="{len(normals)*3}">{normal_coords}</float_array><technique_common><accessor source="#normal_array" count="{len(normals)}" stride="3"><param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/></accessor></technique_common></source>'
    groups=defaultdict(list)
    for f,m in zip(mesh.f,mesh.m): groups[m].extend(f)
    effects=''.join(f'<effect id="e{i}"><profile_COMMON><technique sid="common"><lambert><diffuse><color>{r} {g} {b} 1</color></diffuse></lambert></technique></profile_COMMON></effect>' for i,(r,g,b) in enumerate(PALETTE))
    mats=''.join(f'<material id="m{i}"><instance_effect url="#e{i}"/></material>' for i in range(len(PALETTE)))
    triangles=''.join(f'<triangles material="m{i}" count="{len(fs)//3}"><input semantic="VERTEX" source="#verts" offset="0"/><input semantic="NORMAL" source="#normals" offset="1"/><p>{" ".join(str(i) for i in fs for _ in range(2))}</p></triangles>' for i,fs in groups.items())
    binds=''.join(f'<instance_material symbol="m{i}" target="#m{i}"/>' for i in groups)
    coords=' '.join(f'{c:.6f}' for p in mesh.v for c in p)
    path.write_text(f'''<?xml version="1.0" encoding="utf-8"?><COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1"><asset><created>2026-11-05T00:00:00Z</created><modified>2026-11-05T00:00:00Z</modified><unit name="meter" meter="1"/><up_axis>Z_UP</up_axis></asset><library_effects>{effects}</library_effects><library_materials>{mats}</library_materials><library_geometries><geometry id="tree"><mesh><source id="pos"><float_array id="arr" count="{len(mesh.v)*3}">{coords}</float_array><technique_common><accessor source="#arr" count="{len(mesh.v)}" stride="3"><param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/></accessor></technique_common></source>{normal_source}<vertices id="verts"><input semantic="POSITION" source="#pos"/></vertices>{triangles}</mesh></geometry></library_geometries><library_visual_scenes><visual_scene id="scene"><node id="tree_node"><instance_geometry url="#tree"><bind_material><technique_common>{binds}</technique_common></bind_material></instance_geometry></node></visual_scene></library_visual_scenes><scene><instance_visual_scene url="#scene"/></scene></COLLADA>''',encoding='utf-8')
def build(spec):
    name,h,dbh,radius,base,seed=spec; rng=random.Random(seed); wood=Mesh(); leaves=Mesh(); collision=Mesh()
    def center(z): return (.07*math.sin(z*.4)*z/h,.055*(math.cos(z*.5)-1)*z/h,z)
    def rad(z):
        if z<1.3: return dbh*.5*(1+.48*(1-z/1.3)**2)
        return max(.003,dbh*.5*((h-z)/(h-1.3))**.8)
    zs=sorted(set([0,.25,.65,1.3]+[h*i/64 for i in range(1,65)]))
    for z,z2 in zip(zs,zs[1:]):
        wood.tube(center(z),center(z2),rad(z),rad(z2),sides=16,rng=rng)
        collision.tube(center(z),center(z2),rad(z),rad(z2),sides=12)
    for i in range(64):
        t=min(.99,max(0,(i+rng.uniform(-.7,.7))/64)); z=base+(h-base-.5)*t; az=i*2.39996+rng.uniform(-.9,.9)
        reach=radius*(math.sin(math.pi*(.18+.82*t))**.65)*rng.uniform(.65,1)
        start=center(z); elbow=add(start,(math.cos(az)*reach*.52,math.sin(az)*reach*.52,.30+reach*.18))
        end=add(start,(math.cos(az)*reach,math.sin(az)*reach,min(reach*.32,h-z-.25)))
        r=rad(z)*rng.uniform(.22,.38)
        wood.tube(start,elbow,r,r*.5,2); wood.tube(elbow,end,r*.5,.006,2)
        collision.tube(start,elbow,r,r*.5,2); collision.tube(elbow,end,r*.5,.006,2)
        for j in range(12):
            f=.26+j*.06; anchor=add(elbow,mul(sub(end,elbow),(f-.26)/.72))
            a=az+(-1 if j%2 else 1)*rng.uniform(.45,1.25)
            extent=rng.uniform(.45,1.15)*(1-.35*t)
            tip=add(anchor,(math.cos(a)*extent,math.sin(a)*extent,rng.uniform(-.15,.35)))
            wood.tube(anchor,tip,.007,.0015,2,sides=5)
            for k in range(6):
                p=add(anchor,mul(sub(tip,anchor),.25+k*.15)); a2=a+(-1 if k%2 else 1)*.9
                tail=add(p,(math.cos(a2)*.30,math.sin(a2)*.30,-rng.uniform(.15,.40)))
                wood.tube(p,tail,.002,.0006,2,sides=4)
                for n in range(10):
                    q=add(p,mul(sub(tail,p),(n+1)/10)); q=add(q,(rng.uniform(-.055,.055),rng.uniform(-.055,.055),0))
                    leaves.leaf(q,rng)
    # terminal shoot carries a small leafy crown up to the trunk tip
    for i in range(180): leaves.leaf((rng.uniform(-.25,.25),rng.uniform(-.25,.25),rng.uniform(h-.7,h)),rng)
    path=ROOT/'models'/name; (path/'meshes').mkdir(parents=True,exist_ok=True)
    for mesh,fn in [(wood,'wood'),(leaves,'leaves'),(collision,'collision')]: dae(mesh,path/'meshes'/f'{fn}.dae')
    visuals=''.join(f'<visual name="{part}"><geometry><mesh><uri>model://{name}/meshes/{part}.dae</uri></mesh></geometry><cast_shadows>true</cast_shadows></visual>' for part in ['wood','leaves'])
    (path/'model.sdf').write_text(f'<?xml version="1.0"?><sdf version="1.6"><model name="{name}"><static>true</static><link name="tree">{visuals}<collision name="woody_collision"><geometry><mesh><uri>model://{name}/meshes/collision.dae</uri></mesh></geometry></collision></link></model></sdf>')
    (path/'model.config').write_text(f'<?xml version="1.0"?><model><name>{name}</name><version>1.0</version><sdf version="1.6">model.sdf</sdf><author><name>Biomass simulation resources</name></author><description>Procedural eucalyptus, {h} m, DBH {dbh} m; metric Z-up.</description></model>')
    meta=dict(name=name,height_m=h,dbh_m=dbh,crown_start_m=base,seed=seed,visual_triangles=len(wood.f)+len(leaves.f),collision_triangles=len(collision.f),bounds_min=[min(p[i] for p in wood.v+leaves.v) for i in range(3)],bounds_max=[max(p[i] for p in wood.v+leaves.v) for i in range(3)])
    (path/'dimensions.json').write_text(json.dumps(meta,indent=2)); print(json.dumps(meta),flush=True)
    return wood,leaves
def world(name, instances, mrs=False):
    """Write a Gazebo Classic world while preserving the deterministic tree poses."""
    (ROOT/'worlds').mkdir(exist_ok=True)
    includes = ''.join(
        f'<include><uri>model://{model}</uri><name>tree_{i:03}</name>'
        f'<pose>{x} {y} 0 0 0 {yaw}</pose></include>'
        for i, (model, x, y, yaw) in enumerate(instances)
    )
    plugin = ('<plugin name="mrs_gazebo_static_transform_republisher_plugin" '
              'filename="libMrsGazeboCommonResources_StaticTransformRepublisher.so"/>') if mrs else ''
    spherical = ('<spherical_coordinates><surface_model>EARTH_WGS84</surface_model>'
                 '<latitude_deg>47.397743</latitude_deg><longitude_deg>8.545594</longitude_deg>'
                 '<elevation>0.0</elevation><heading_deg>0</heading_deg>'
                 '</spherical_coordinates>') if mrs else ''
    physics = ('<physics name="default_physics" type="ode"><max_step_size>0.005</max_step_size>'
               '<real_time_update_rate>200</real_time_update_rate></physics>') if mrs else ''
    ground = ('<model name="ground"><static>true</static><link name="ground">'
              '<collision name="ground"><geometry><plane><normal>0 0 1</normal>'
              '<size>200 200</size></plane></geometry></collision>'
              '<visual name="ground"><geometry><plane><normal>0 0 1</normal>'
              '<size>200 200</size></plane></geometry><material>'
              '<ambient>0.24 0.29 0.12 1</ambient><diffuse>0.32 0.37 0.18 1</diffuse>'
              '</material></visual></link></model>')
    world_name = name.replace('-', '_') if mrs else name
    xml = (f'<?xml version="1.0"?><sdf version="1.6"><world name="{world_name}">'
           f'{plugin}{spherical}<gravity>0 0 -9.81</gravity>{physics}'
           '<scene><ambient>0.55 0.55 0.55 1</ambient>'
           '<background>0.72 0.81 0.88 1</background><shadows>true</shadows></scene>'
           '<light name="sun" type="directional"><pose>0 0 40 0 0 0</pose>'
           '<diffuse>0.95 0.93 0.85 1</diffuse><specular>0.1 0.1 0.1 1</specular>'
           '<direction>-0.4 0.2 -0.8</direction><cast_shadows>true</cast_shadows></light>'
           f'{ground}{includes}</world></sdf>')
    (ROOT/'worlds'/f'{name}.world').write_text(pretty_xml(xml), encoding='utf-8')

def preview(trees):
    import bpy
    from mathutils import Vector
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    mats=[]
    for i,c in enumerate(PALETTE):
        m=bpy.data.materials.new(str(i)); m.diffuse_color=(*c,1); mats.append(m)
    for idx,parts in enumerate(trees):
        for mesh in parts:
            data=bpy.data.meshes.new('tree'); data.from_pydata(mesh.v,[],mesh.f); data.update()
            obj=bpy.data.objects.new('eucalyptus',data); bpy.context.collection.objects.link(obj); obj.location.x=(idx-1)*10
            for m in mats:data.materials.append(m)
            for p,m in zip(data.polygons,mesh.m):p.material_index=m
    bpy.ops.mesh.primitive_plane_add(size=200); ground=bpy.context.object
    m=bpy.data.materials.new('ground'); m.diffuse_color=(.70,.72,.66,1); ground.data.materials.append(m)
    bpy.ops.object.light_add(type='SUN',location=(0,-10,30)); bpy.context.object.rotation_euler=(.4,-.5,-.5); bpy.context.object.data.energy=2.5
    bpy.ops.object.camera_add(location=(34,-68,28)); cam=bpy.context.object; cam.rotation_euler=(Vector((0,0,13))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='ORTHO'; cam.data.ortho_scale=41
    s=bpy.context.scene; s.camera=cam; s.render.engine='CYCLES'; s.cycles.samples=24
    s.world.use_nodes=True; s.world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.80,.85,1); s.world.node_tree.nodes['Background'].inputs[1].default_value=.8
    s.cycles.use_denoising=True; s.render.resolution_x=1500; s.render.resolution_y=1200; s.render.resolution_percentage=100
    (ROOT/'docs').mkdir(exist_ok=True); s.render.filepath=str(ROOT/'docs'/'eucalyptus_preview.png'); bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'docs'/'eucalyptus_preview.blend')); bpy.ops.render.render(write_still=True)
if __name__=='__main__':
    trees=[build(s) for s in SPECS]
    rng=random.Random(2026); rows=[(SPECS[rng.randrange(3)][0],r*6-15,c*3-13.5,rng.uniform(0,math.tau)) for r in range(6) for c in range(10)]
    world('eucalyptus_rows', rows)
    world('mrs-eucalyptus_rows', rows, mrs=True)
    from generate_ground_truth_json import generate, load_catalog, svg_for
    catalog = load_catalog(ROOT/'models'/'models.json')
    for world_name in ('eucalyptus_rows', 'mrs-eucalyptus_rows'):
        payload = generate(ROOT/'worlds'/f'{world_name}.world', catalog)
        destination = ROOT/'ground_truth'/world_name
        destination.mkdir(parents=True, exist_ok=True)
        (destination/'ground_truth.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (destination/f'{world_name}_ground_truth.svg').write_text(svg_for(payload), encoding='utf-8')
    if '--preview' in sys.argv: preview(trees)
