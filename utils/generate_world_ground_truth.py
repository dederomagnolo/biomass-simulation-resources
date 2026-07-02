#!/usr/bin/env python3

import argparse
import csv
import math
import xml.etree.ElementTree as ET
from pathlib import Path

TREE_STEM_BASE_OFFSETS = {
    "new_tree_1": {"x": 0.069135, "y": -0.320312, "z": 0.0},
    "new_tree_2": {"x": 0.414917, "y": 0.000001, "z": 0.0},
    "new_tree_3": {"x": 0.458424, "y": -0.092327, "z": 0.025507},
}


def parse_args():
    parser = argparse.ArgumentParser(description="Generate CSV/SVG ground truth from a Gazebo world.")
    parser.add_argument("--world", required=True, help="Path to the .world file")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    parser.add_argument("--name", required=True, help="Dataset base name, e.g. forest-test")
    return parser.parse_args()


def classify_uri(mesh_uri):
    if "world_jean_tree" in mesh_uri:
        return "tree"
    if "new_tree_" in mesh_uri:
        return "tree"
    if "new_shrub_" in mesh_uri:
        return "bush"
    return None


def model_offset(mesh_uri):
    for model_name, offset in TREE_STEM_BASE_OFFSETS.items():
        if f"model://{model_name}/" in mesh_uri:
            return offset
    return None


def read_objects(world_path):
    root = ET.parse(world_path).getroot()
    world = root.find("world")
    if world is None:
        raise RuntimeError("No <world> element found")

    rows = []
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

        pose_txt = (model.findtext("pose") or "").strip()
        vals = pose_txt.split()
        if len(vals) < 6:
            continue
        x, y, z, roll, pitch, yaw = map(float, vals[:6])
        offset = model_offset(mesh_uri)
        if offset is not None:
            cos_yaw = math.cos(yaw)
            sin_yaw = math.sin(yaw)
            x += offset["x"] * cos_yaw - offset["y"] * sin_yaw
            y += offset["x"] * sin_yaw + offset["y"] * cos_yaw
            z += offset["z"]
        rows.append(
            {
                "type": obj_type,
                "model_name": model_name,
                "source_uri": mesh_uri,
                "x": x,
                "y": y,
                "z": z,
                "roll": roll,
                "pitch": pitch,
                "yaw": yaw,
            }
        )

    rows.sort(key=lambda row: (0 if row["type"] == "tree" else 1, row["model_name"]))
    for idx, row in enumerate(rows, start=1):
        row["id"] = idx
    return rows


def write_csv(rows, csv_path):
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "type", "model_name", "source_uri", "x", "y", "z", "roll", "pitch", "yaw"])
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["type"],
                    row["model_name"],
                    row["source_uri"],
                    f"{row['x']:.5f}".rstrip("0").rstrip("."),
                    f"{row['y']:.5f}".rstrip("0").rstrip("."),
                    f"{row['z']:.5f}".rstrip("0").rstrip("."),
                    f"{row['roll']:.6f}".rstrip("0").rstrip("."),
                    f"{row['pitch']:.6f}".rstrip("0").rstrip("."),
                    f"{row['yaw']:.6f}".rstrip("0").rstrip("."),
                ]
            )


def compute_limits(rows):
    xs = [row["x"] for row in rows]
    ys = [row["y"] for row in rows]
    return (
        math.floor(min(xs) - 1.0),
        math.ceil(max(xs) + 1.0),
        math.floor(min(ys) - 1.0),
        math.ceil(max(ys) + 1.0),
    )


def write_limits(limits_path, x_min, x_max, y_min, y_max):
    limits_path.write_text(
        f"x_min={x_min}\n"
        f"x_max={x_max}\n"
        f"y_min={y_min}\n"
        f"y_max={y_max}\n",
        encoding="utf-8",
    )


def write_svg(rows, svg_path, title, x_min, x_max, y_min, y_max):
    width = 880
    height = 800
    left = 100
    right = 60
    top = 60
    bottom = 100
    plot_w = width - left - right
    plot_h = height - top - bottom

    def sx(x):
        return left + (x - x_min) / float(x_max - x_min) * plot_w

    def sy(y):
        return top + (1.0 - (y - y_min) / float(y_max - y_min)) * plot_h

    tree_count = sum(1 for row in rows if row["type"] == "tree")
    bush_count = sum(1 for row in rows if row["type"] == "bush")

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'  <rect width="{width}" height="{height}" fill="#fcfcf8"/>',
        f'  <text x="100" y="36" font-size="24" font-family="Arial" fill="#222">{title}</text>',
        '  <text x="100" y="58" font-size="14" font-family="Arial" fill="#555">Trees and bushes extracted from the Gazebo world file</text>',
        f'  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f7faf7" stroke="#b9c7b9" stroke-width="1.5"/>',
    ]

    for y in range(y_min, y_max + 1):
        py = sy(y)
        lines.append(
            f'  <line x1="{left}" y1="{py:.2f}" x2="{left + plot_w}" y2="{py:.2f}" stroke="#d9dfd9" stroke-width="1"/>'
        )
    for x in range(x_min, x_max + 1):
        px = sx(x)
        lines.append(
            f'  <line x1="{px:.2f}" y1="{top}" x2="{px:.2f}" y2="{top + plot_h}" stroke="#d9dfd9" stroke-width="1"/>'
        )
    if x_min <= 0 <= x_max:
        px = sx(0)
        lines.append(
            f'  <line x1="{px:.2f}" y1="{top}" x2="{px:.2f}" y2="{top + plot_h}" stroke="#8f9d8f" stroke-width="2"/>'
        )
    if y_min <= 0 <= y_max:
        py = sy(0)
        lines.append(
            f'  <line x1="{left}" y1="{py:.2f}" x2="{left + plot_w}" y2="{py:.2f}" stroke="#8f9d8f" stroke-width="2"/>'
        )

    for x in range(x_min, x_max + 1):
        lines.append(
            f'  <text x="{sx(x):.2f}" y="728" font-size="12" font-family="Arial" fill="#444" text-anchor="middle">{x}</text>'
        )
    for y in range(y_min, y_max + 1):
        lines.append(
            f'  <text x="82" y="{sy(y) + 4:.2f}" font-size="12" font-family="Arial" fill="#444" text-anchor="end">{y}</text>'
        )

    lines.append(
        f'  <text x="{left + plot_w / 2:.2f}" y="770" font-size="16" font-family="Arial" fill="#333" text-anchor="middle">X (m)</text>'
    )
    lines.append(
        f'  <text x="28" y="{top + plot_h / 2:.2f}" font-size="16" font-family="Arial" fill="#333" text-anchor="middle" transform="rotate(-90 28 {top + plot_h / 2:.2f})">Y (m)</text>'
    )

    for row in rows:
        px = sx(row["x"])
        py = sy(row["y"])
        if row["type"] == "tree":
            lines.append(
                f'  <circle cx="{px:.2f}" cy="{py:.2f}" r="8" fill="#2f7d32" stroke="#184d1d" stroke-width="1.5"/>'
            )
        else:
            lines.append(
                f'  <rect x="{px - 6:.2f}" y="{py - 6:.2f}" width="12" height="12" fill="#c96b1f" stroke="#7a3f10" stroke-width="1.5"/>'
            )

    lines.extend(
        [
            '  <rect x="620" y="84" width="180" height="78" rx="8" fill="#ffffff" stroke="#cfd7cf"/>',
            '  <circle cx="642" cy="108" r="7" fill="#2f7d32" stroke="#184d1d" stroke-width="1.5"/>',
            '  <text x="658" y="113" font-size="14" font-family="Arial" fill="#333">Tree</text>',
            '  <rect x="635" y="127" width="12" height="12" fill="#c96b1f" stroke="#7a3f10" stroke-width="1.5"/>',
            '  <text x="658" y="138" font-size="14" font-family="Arial" fill="#333">Bush</text>',
            f'  <text x="635" y="154" font-size="12" font-family="Arial" fill="#666">{tree_count} trees, {bush_count} bushes</text>',
            "</svg>",
        ]
    )

    svg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    world_path = Path(args.world)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = read_objects(world_path)
    if not rows:
        raise RuntimeError("No tree or bush models found in world")

    csv_path = out_dir / f"{args.name}_ground_truth.csv"
    svg_path = out_dir / f"{args.name}_ground_truth.svg"
    limits_path = out_dir / "limits.txt"

    x_min, x_max, y_min, y_max = compute_limits(rows)
    write_csv(rows, csv_path)
    write_limits(limits_path, x_min, x_max, y_min, y_max)
    write_svg(rows, svg_path, f"{args.name} Ground Truth", x_min, x_max, y_min, y_max)

    print(csv_path)
    print(svg_path)
    print(limits_path)
    print(f"rows={len(rows)} trees={sum(1 for r in rows if r['type']=='tree')} bushes={sum(1 for r in rows if r['type']=='bush')}")


if __name__ == "__main__":
    main()
