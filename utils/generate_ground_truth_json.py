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
    return {item["model_name"]: item for item in items}


def instance_sort_key(item):
    name = item["name"]
    clone_count = name.count("_clone")
    root_name = name.split("_clone", 1)[0]
    return (root_name, clone_count, name)


def read_tree_instances(world_path):
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

        if classify_uri(mesh_uri) != "tree":
            continue

        pose_text = (model.findtext("pose") or "").strip()
        values = pose_text.split()
        if len(values) < 6:
            continue

        x, y, z, _, _, yaw = map(float, values[:6])
        instances.append(
            {
                "name": model_name,
                "base_model": get_base_model(mesh_uri),
                "obj_position": [x, y, z],
                "yaw": yaw,
            }
        )

    if not instances:
        raise RuntimeError(f"No tree models found in {world_path}")

    instances.sort(key=instance_sort_key)
    return instances


def build_trees(instances, models_catalog):
    trunks = []

    for instance in instances:
        base_model = instance["base_model"]
        model_meta = models_catalog.get(base_model)
        if model_meta is None:
            continue

        cos_yaw = math.cos(instance["yaw"])
        sin_yaw = math.sin(instance["yaw"])
        obj_x, obj_y, obj_z = instance["obj_position"]
        bif_height = model_meta.get("biffurcation_height")

        for trunk in model_meta.get("bh_trunks", []):
            local_x = float(trunk["position"][0])
            local_y = float(trunk["position"][1])
            dap_x = obj_x + local_x * cos_yaw - local_y * sin_yaw
            dap_y = obj_y + local_x * sin_yaw + local_y * cos_yaw
            entry = {
                "name": instance["name"],
                "source_model": base_model,
                "trunk_id": int(trunk["trunk_id"]),
                "obj_position": [
                    round_value(obj_x, 5),
                    round_value(obj_y, 5),
                    round_value(obj_z, 5),
                ],
                "dap_position": [round_value(dap_x, 5), round_value(dap_y, 5)],
            }
            if bif_height is not None:
                entry["biffurcation_height"] = round_value(bif_height, 5)
            trunks.append(entry)

    return trunks


def compute_limits(trunks):
    xs = [trunk["obj_position"][0] for trunk in trunks]
    ys = [trunk["obj_position"][1] for trunk in trunks]
    return {
        "x_min": math.floor(min(xs) - 1.0),
        "x_max": math.ceil(max(xs) + 1.0),
        "y_min": math.floor(min(ys) - 1.0),
        "y_max": math.ceil(max(ys) + 1.0),
    }


def build_payload(dataset_name, world_path, repo_root, trunks):
    return {
        "world_name": dataset_name,
        "source_world": str(world_path.relative_to(repo_root)),
        "limits": compute_limits(trunks),
        "trunks": trunks,
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
    instances = read_tree_instances(world_path)
    trunks = build_trees(instances, models_catalog)

    payload = build_payload(dataset_name, world_path, repo_root, trunks)
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
