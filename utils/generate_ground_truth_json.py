#!/usr/bin/env python3
"""Generate JSON GT for SDF worlds using models/models.json classifications."""
import argparse, json, math, pathlib, xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

def pose_of(element):
    raw=(element.findtext('pose') or '').split()
    if not raw:return [0.0]*6
    if len(raw)!=6:raise ValueError(f'Expected x y z roll pitch yaw: {raw}')
    values=[float(x) for x in raw]
    if not all(math.isfinite(x) for x in values):raise ValueError('Non-finite pose')
    return values

def model_key(element):
    if element.tag=='include':
        uri=(element.findtext('uri') or '').strip()
        if uri.startswith('model://'):return uri[8:].strip('/')
        return uri or (element.findtext('name') or 'unknown')
    for mesh in element.findall('.//mesh'):
        uri=(mesh.findtext('uri') or '').strip()
        if uri.startswith('model://'):
            value=uri[8:].strip('/')
            if value.startswith('forest-gen-models/'):return '/'.join(value.split('/')[:2])
            return value.split('/')[0]
    return element.get('name') or 'unknown'

def load_catalog(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    catalog={}
    for item in data:
        key=item['source_model']
        if key in catalog or item['type'] not in ('tree','bush','object'):raise ValueError(f'Invalid catalog entry: {key}')
        catalog[key]=item
    for key,item in list(catalog.items()):
        if 'alias_of' in item:
            target=item['alias_of']
            if target not in catalog:raise ValueError(f'Unknown catalog alias target: {target}')
            catalog[key]={**catalog[target],'source_model':key}
    return catalog

def generate(world_path,catalog):
    world=ET.parse(world_path).getroot().find('world')
    if world is None:raise ValueError('No <world>')
    trunks=[];bushes=[];misc=[];tree_id=0;seen=set()
    for element in world:
        if element.tag not in ('include','model'):continue
        key=model_key(element)
        name=(element.findtext('name') if element.tag=='include' else element.get('name')) or key
        if name in seen:raise ValueError(f'Duplicate instance name: {name}')
        seen.add(name)
        x,y,z,roll,pitch,yaw=pose_of(element)
        entry={'name':name,'source_model':key,'obj_position':[x,y,z],'yaw':yaw}
        meta=catalog.get(key,{'type':'object'})
        if meta['type']=='tree':
            tree_id+=1
            stems=meta.get('trunks') or [{'trunk_id':1}]
            for stem in stems:
                tree={'tree_id':tree_id,**entry}
                if len(stems)>1:tree['trunk_id']=int(stem['trunk_id'])
                center=stem.get('mesh_dbh_position')
                if center is not None:
                    if abs(roll)>1e-9 or abs(pitch)>1e-9:raise ValueError(f'Tilted calibrated tree: {name}')
                    dx,dy=map(float,center)
                    tree['mesh_dbh_position']=[dx,dy]
                    tree['dbh_world_position']=[round(x+dx*math.cos(yaw)-dy*math.sin(yaw),6),round(y+dx*math.sin(yaw)+dy*math.cos(yaw),6)]
                for field in ('dbh','height'):
                    value=stem.get(field,meta.get(field))
                    if value is not None:tree[field]=value
                if 'biffurcation_height' in meta:tree['biffurcation_height']=meta['biffurcation_height']
                trunks.append(tree)
        elif meta['type']=='bush':bushes.append({'bush_id':len(bushes)+1,**entry})
        else:misc.append({'object_id':len(misc)+1,'type':'object',**entry})
    # Match legacy GT convention: vegetation extent with a 1 m margin.
    positions=[a['obj_position'] for a in trunks+bushes]
    if not positions:positions=[a['obj_position'] for a in misc]
    if positions:
        xs=[p[0] for p in positions];ys=[p[1] for p in positions]
        limits={'x_min':math.floor(min(xs)-1),'x_max':math.ceil(max(xs)+1),'y_min':math.floor(min(ys)-1),'y_max':math.ceil(max(ys)+1)}
    else:raise ValueError('World has no positioned models/includes')
    return {'world_name':world.get('name'),'limits':limits,'trunks':trunks,'bushes':bushes,'misc':misc}

def tick_step(span):
    """Choose a readable metric grid step (1, 2, or 5 times a power of ten)."""
    target = span / 8
    power = 10 ** math.floor(math.log10(target))
    for multiplier in (1, 2, 5, 10):
        step = multiplier * power
        if step >= target:
            return step


def svg_for(payload):
    """Draw the same top-down vegetation map style as the existing forest SVG."""
    width, height = 880, 800
    left, top, plot_width, plot_height = 100, 60, 720, 640
    limits = payload['limits']
    x_min, x_max = limits['x_min'], limits['x_max']
    y_min, y_max = limits['y_min'], limits['y_max']
    if x_min >= x_max or y_min >= y_max:
        raise ValueError('Invalid GT limits for SVG')

    def point(x, y):
        return (left + (x - x_min) * plot_width / (x_max - x_min),
                top + (y_max - y) * plot_height / (y_max - y_min))

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'  <rect width="{width}" height="{height}" fill="#fcfcf8"/>',
        f'  <text x="100" y="36" font-size="24" font-family="Arial" fill="#222">{escape(str(payload["world_name"]))} Ground Truth</text>',
        '  <text x="100" y="58" font-size="14" font-family="Arial" fill="#555">Trees and bushes extracted from the Gazebo world file</text>',
        f'  <rect x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" fill="#f7faf7" stroke="#b9c7b9" stroke-width="1.5"/>',
    ]

    for axis, low, high in (('x', x_min, x_max), ('y', y_min, y_max)):
        step = tick_step(high - low)
        start = math.ceil(low / step)
        end = math.floor(high / step)
        for index in range(start, end + 1):
            value = index * step
            label = f'{value:g}'
            if axis == 'x':
                pixel, _ = point(value, y_min)
                lines.append(f'  <line x1="{pixel:.2f}" y1="{top}" x2="{pixel:.2f}" y2="{top + plot_height}" stroke="#d9dfd9" stroke-width="1"/>')
                lines.append(f'  <text x="{pixel:.2f}" y="728" font-size="12" font-family="Arial" fill="#444" text-anchor="middle">{label}</text>')
            else:
                _, pixel = point(x_min, value)
                lines.append(f'  <line x1="{left}" y1="{pixel:.2f}" x2="{left + plot_width}" y2="{pixel:.2f}" stroke="#d9dfd9" stroke-width="1"/>')
                lines.append(f'  <text x="82" y="{pixel + 4:.2f}" font-size="12" font-family="Arial" fill="#444" text-anchor="end">{label}</text>')

    if x_min <= 0 <= x_max:
        zero_x, _ = point(0, y_min)
        lines.append(f'  <line x1="{zero_x:.2f}" y1="{top}" x2="{zero_x:.2f}" y2="{top + plot_height}" stroke="#8f9d8f" stroke-width="2"/>')
    if y_min <= 0 <= y_max:
        _, zero_y = point(x_min, 0)
        lines.append(f'  <line x1="{left}" y1="{zero_y:.2f}" x2="{left + plot_width}" y2="{zero_y:.2f}" stroke="#8f9d8f" stroke-width="2"/>')

    lines += [
        '  <text x="460" y="770" font-size="16" font-family="Arial" fill="#333" text-anchor="middle">X (m)</text>',
        '  <text x="28" y="380" font-size="16" font-family="Arial" fill="#333" text-anchor="middle" transform="rotate(-90 28 380)">Y (m)</text>',
    ]

    for tree in payload['trunks']:
        x, y = tree.get('dbh_world_position', tree['obj_position'])[:2]
        pixel_x, pixel_y = point(x, y)
        title = escape(f'{tree["name"]} | tree {tree["tree_id"]} | ({x:g}, {y:g}) m')
        lines.append(f'  <circle cx="{pixel_x:.2f}" cy="{pixel_y:.2f}" r="8" fill="#2f7d32" stroke="#184d1d" stroke-width="1.5"><title>{title}</title></circle>')
    for bush in payload['bushes']:
        x, y = bush['obj_position'][:2]
        pixel_x, pixel_y = point(x, y)
        title = escape(f'{bush["name"]} | bush {bush["bush_id"]} | ({x:g}, {y:g}) m')
        lines.append(f'  <rect x="{pixel_x - 6:.2f}" y="{pixel_y - 6:.2f}" width="12" height="12" fill="#c96b1f" stroke="#7a3f10" stroke-width="1.5"><title>{title}</title></rect>')

    tree_count = len({tree['tree_id'] for tree in payload['trunks']})
    bush_count = len(payload['bushes'])
    if not tree_count and not bush_count:
        lines.append('  <text x="460" y="380" font-size="18" font-family="Arial" fill="#666" text-anchor="middle">No trees or bushes in this world</text>')
    lines += [
        '  <rect x="620" y="84" width="180" height="78" rx="8" fill="#ffffff" stroke="#cfd7cf"/>',
        '  <circle cx="642" cy="108" r="7" fill="#2f7d32" stroke="#184d1d" stroke-width="1.5"/>',
        '  <text x="658" y="113" font-size="14" font-family="Arial" fill="#333">Tree</text>',
        '  <rect x="635" y="127" width="12" height="12" fill="#c96b1f" stroke="#7a3f10" stroke-width="1.5"/>',
        '  <text x="658" y="138" font-size="14" font-family="Arial" fill="#333">Bush</text>',
        f'  <text x="635" y="154" font-size="12" font-family="Arial" fill="#666">{tree_count} trees, {bush_count} bushes</text>',
        '</svg>',
    ]
    return '\n'.join(lines) + '\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('world_name',nargs='?',help='Name with or without .world')
    parser.add_argument('--all',action='store_true',help='Generate JSON and SVG for every .world file')
    parser.add_argument('--package-root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument('--output-root',type=pathlib.Path)
    parser.add_argument('--print-only',action='store_true')
    args=parser.parse_args()
    if args.all == bool(args.world_name):
        parser.error('Specify one world name or --all')
    if args.all and args.print_only:
        parser.error('--print-only requires one world name')
    root=args.package_root.resolve()
    worlds=sorted((root/'worlds').glob('*.world')) if args.all else [root/'worlds'/f'{pathlib.Path(args.world_name).stem}.world']
    if not worlds:parser.error('No .world files found')
    catalog=load_catalog(root/'models/models.json')
    for world in worlds:
        payload=generate(world,catalog)
        if args.print_only:
            print(json.dumps(payload,ensure_ascii=False,indent=2));return
        out_dir=(args.output_root or root)/'ground_truth'/world.stem
        out_dir.mkdir(parents=True,exist_ok=True)
        json_path=out_dir/'ground_truth.json'
        svg_path=out_dir/f'{world.stem}_ground_truth.svg'
        json_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        svg_path.write_text(svg_for(payload),encoding='utf-8')
        print(f'{world.name}: {len(payload["trunks"])} trunks, {len(payload["bushes"])} bushes, {len(payload["misc"])} misc -> {json_path}, {svg_path}')

if __name__=='__main__':main()
