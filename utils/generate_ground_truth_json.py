#!/usr/bin/env python3

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a minimal ground_truth.json from a Gazebo world.")
    parser.add_argument("world_name", help="World base name, with or without .world")
    parser.add_argument("--worlds-dir", default="worlds", help="Directory containing .world files")
    parser.add_argument("--ground-truth-dir", default="ground_truth", help="Ground-truth root directory")
    parser.add_argument(
        "--models-path",
        default="ground_truth/models/models.json",
        help="Path to the calibrated model DAP catalog JSON",
    )
    parser.add_argument("--print-only", action="store_true", help="Print JSON instead of writing the file")
    return parser.parse_args()


def round_value(value, digits):
    return round(float(value), digits)


def classify_uri(mesh_uri):
    if "world_jean_tree" in mesh_uri:
        return "tree"
    if "new_tree_" in mesh_uri:
        return "tree"
    if "new_shrub_" in mesh_uri:
        return "bush"
    if "bush_" in mesh_uri:
        return "bush"
    return None


def get_base_model(mesh_uri):
    prefix = "model://"
    if not mesh_uri.startswith(prefix):
        return ""
    remainder = mesh_uri[len(prefix) :]
    return remainder.split("/", 1)[0]


def load_models_catalog(models_path):
    with open(models_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    if not isinstance(items, list):
        raise RuntimeError(f"Expected a list in models catalog: {models_path}")

    catalog = {}
    for item in items:
        source_model = (item.get("source_model") or item.get("name") or item.get("model_name") or "").strip()
        if not source_model:
            raise RuntimeError(f"Catalog entry missing source model key: {item}")
        if source_model in catalog:
            raise RuntimeError(f"Duplicate catalog entry for source model '{source_model}'")
        catalog[source_model] = item
    return catalog


def instance_sort_key(item):
    name = item["name"]
    clone_count = name.count("_clone")
    root_name = name.split("_clone", 1)[0]
    return (root_name, clone_count, name)


def read_instances(world_path):
    root = ET.parse(world_path).getroot()
    world = root.find("world")
    if world is None:
        raise RuntimeError(f"No <world> element found in {world_path}")

    instances = []
    for model in world.findall("model"):
        model_name = (model.get("name") or "").strip()
        mesh_uri = ""
        for mesh in model.findall(".//mesh"):
            uri = (mesh.findtext("uri") or "").strip()
            if uri:
                mesh_uri = uri
                break

        obj_type = classify_uri(mesh_uri)
        if obj_type is None:
            continue

        pose_text = (model.findtext("pose") or "").strip()
        values = pose_text.split()
        if len(values) < 6:
            continue

        x, y, z, _, _, yaw = map(float, values[:6])
        instances.append(
            {
                "type": obj_type,
                "name": model_name,
                "base_model": get_base_model(mesh_uri),
                "obj_position": [x, y, z],
                "yaw": yaw,
            }
        )

    if not instances:
        raise RuntimeError(f"No supported vegetation models found in {world_path}")

    tree_instances = sorted((item for item in instances if item["type"] == "tree"), key=instance_sort_key)
    bush_instances = sorted((item for item in instances if item["type"] == "bush"), key=instance_sort_key)
    return tree_instances, bush_instances


def build_trees(instances, models_catalog):
    trunks = []

    for tree_id, instance in enumerate(instances, start=1):
        base_model = instance["base_model"]
        model_meta = models_catalog.get(base_model)
        obj_x, obj_y, obj_z = instance["obj_position"]
        if model_meta is None:
            entry = {
                "tree_id": tree_id,
                "name": instance["name"],
                "source_model": base_model,
                "obj_position": [
                    round_value(obj_x, 5),
                    round_value(obj_y, 5),
                    round_value(obj_z, 5),
                ],
            }
            trunks.append(entry)
            continue

        cos_yaw = math.cos(instance["yaw"])
        sin_yaw = math.sin(instance["yaw"])
        bif_height = model_meta.get("biffurcation_height")
        model_trunks = model_meta.get("trunks", [])

        if not model_trunks:
            raise RuntimeError(f"Catalog entry for '{base_model}' has no trunks")

        sorted_trunks = sorted(model_trunks, key=lambda item: int(item.get("trunk_id", 0)))

        for trunk in sorted_trunks:
            trunk_id = trunk.get("trunk_id")
            if trunk_id is None:
                raise RuntimeError(f"Catalog entry for '{base_model}' has a trunk without trunk_id")

            entry = {
                "tree_id": tree_id,
                "name": instance["name"],
                "source_model": base_model,
                "obj_position": [
                    round_value(obj_x, 5),
                    round_value(obj_y, 5),
                    round_value(obj_z, 5),
                ],
            }

            if len(sorted_trunks) > 1:
                entry["trunk_id"] = int(trunk_id)

            if "dbh_meshe_center" in trunk:
                local_x = float(trunk["dbh_meshe_center"][0])
                local_y = float(trunk["dbh_meshe_center"][1])
                dap_x = obj_x + local_x * cos_yaw - local_y * sin_yaw
                dap_y = obj_y + local_x * sin_yaw + local_y * cos_yaw
                entry["mesh_dap_position"] = [round_value(local_x, 5), round_value(local_y, 5)]
                entry["dap_world_position"] = [round_value(dap_x, 5), round_value(dap_y, 5)]

            if bif_height is not None:
                entry["biffurcation_height"] = round_value(bif_height, 5)

            trunks.append(entry)

    return trunks


def build_bushes(instances):
    bushes = []

    for bush_id, instance in enumerate(instances, start=1):
        obj_x, obj_y, obj_z = instance["obj_position"]
        bushes.append(
            {
                "bush_id": bush_id,
                "name": instance["name"],
                "source_model": instance["base_model"],
                "obj_position": [
                    round_value(obj_x, 5),
                    round_value(obj_y, 5),
                    round_value(obj_z, 5),
                ],
            }
        )

    return bushes


def compute_limits(*collections):
    positions = []
    for collection in collections:
        for item in collection:
            positions.append(item["obj_position"])

    xs = [position[0] for position in positions]
    ys = [position[1] for position in positions]
    return {
        "x_min": math.floor(min(xs) - 1.0),
        "x_max": math.ceil(max(xs) + 1.0),
        "y_min": math.floor(min(ys) - 1.0),
        "y_max": math.ceil(max(ys) + 1.0),
    }


def build_payload(dataset_name, trunks, bushes):
    return {
        "world_name": dataset_name,
        "limits": compute_limits(trunks, bushes),
        "trunks": trunks,
        "bushes": bushes,
    }


def main():
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    world_filename = args.world_name if args.world_name.endswith(".world") else f"{args.world_name}.world"
    dataset_name = Path(world_filename).stem
    world_path = repo_root / args.worlds_dir / world_filename
    models_path = repo_root / args.models_path

    if not world_path.exists():
        raise FileNotFoundError(f"World file not found: {world_path}")
    if not models_path.exists():
        raise FileNotFoundError(f"Models file not found: {models_path}")

    models_catalog = load_models_catalog(models_path)
    tree_instances, bush_instances = read_instances(world_path)
    trunks = build_trees(tree_instances, models_catalog)
    bushes = build_bushes(bush_instances)

    payload = build_payload(dataset_name, trunks, bushes)
    json_text = json.dumps(payload, ensure_ascii=True, indent=2) + "\n"

    if args.print_only:
        print(json_text, end="")
        return

    out_dir = repo_root / args.ground_truth_dir / dataset_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ground_truth.json"
    out_path.write_text(json_text, encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
