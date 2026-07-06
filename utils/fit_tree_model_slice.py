#!/usr/bin/env python3

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import DBSCAN


def parse_args():
    parser = argparse.ArgumentParser(
        description="Slice a source tree model at DBH height, fit circles, and save a diagnostic image."
    )
    parser.add_argument("source_model", help="Source model name, e.g. new_tree_2")
    parser.add_argument("--models-dir", default="models")
    parser.add_argument("--dbh-height", type=float, default=1.3)
    parser.add_argument("--slice-half-thickness", type=float, default=0.05)
    parser.add_argument("--cluster-eps", type=float, default=0.14)
    parser.add_argument("--cluster-min-samples", type=int, default=4)
    parser.add_argument("--max-trunks", type=int, default=3)
    parser.add_argument("--auto-merge-distance", type=float, default=0.18)
    parser.add_argument("--track-distance-threshold", type=float, default=0.45)
    parser.add_argument("--output-image", default=None)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--consolidated-json", default="ground_truth/models/fitted_models.json")
    parser.add_argument("--print-only", action="store_true", help="Only print JSON result")
    return parser.parse_args()


def load_obj_vertices(obj_path):
    verts = []
    with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                parts = line.split()
                verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
    if not verts:
        raise RuntimeError(f"No vertices found in {obj_path}")
    return np.asarray(verts, dtype=float)


def cluster_xy(points, eps, min_samples):
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit(points).labels_
    clusters = []
    for label in sorted(set(labels)):
        if label < 0:
            continue
        cluster = points[labels == label]
        center = cluster.mean(axis=0)
        clusters.append({"label": int(label), "points": cluster, "center": center, "count": len(cluster)})
    clusters.sort(key=lambda item: item["count"], reverse=True)
    return clusters


def circle_fit(points):
    x = points[:, 0]
    y = points[:, 1]
    a = np.column_stack((2 * x, 2 * y, np.ones(len(points))))
    b = x * x + y * y
    c, d, e = np.linalg.lstsq(a, b, rcond=None)[0]
    radius = math.sqrt(max(0.0, e + c * c + d * d))
    return np.array([c, d]), radius


def track_center_below_dbh(verts, dbh_height, eps, min_samples):
    heights = [h for h in [0.3, 0.5, 0.7, 0.9, 1.1] if h < dbh_height]
    current = None
    for h in heights:
        slab = verts[np.abs(verts[:, 2] - h) <= 0.05][:, :2]
        if len(slab) < min_samples:
            continue
        clusters = cluster_xy(slab, eps, min_samples)
        if not clusters:
            continue
        if current is None:
            current = clusters[0]["center"]
        else:
            current = min(clusters, key=lambda item: np.linalg.norm(item["center"] - current))["center"]
    return current


def merge_close_clusters(clusters, merge_distance):
    if not clusters:
        return []
    kept = []
    for cluster in clusters:
        center = cluster["center"]
        if any(np.linalg.norm(center - existing["center"]) < merge_distance for existing in kept):
            continue
        kept.append(cluster)
    return kept


def analyze_model(
    obj_path,
    dbh_height,
    half_thickness,
    eps,
    min_samples,
    max_trunks,
    auto_merge_distance,
    track_distance_threshold,
):
    verts = load_obj_vertices(obj_path)
    slab_xy = verts[np.abs(verts[:, 2] - dbh_height) <= half_thickness][:, :2]
    if len(slab_xy) < min_samples:
        raise RuntimeError(f"Not enough slice points at {dbh_height} m in {obj_path}")

    ref_center = track_center_below_dbh(verts, dbh_height, eps, min_samples)
    if ref_center is None:
        raise RuntimeError(f"Could not track trunk center below DBH in {obj_path}")

    local_points = slab_xy[np.linalg.norm(slab_xy - ref_center, axis=1) <= 0.90]
    if len(local_points) < max(8, min_samples):
        raise RuntimeError(f"Not enough local points near tracked trunk center in {obj_path}")

    dbscan_clusters = cluster_xy(local_points, eps, min_samples)
    dbscan_clusters = merge_close_clusters(dbscan_clusters, auto_merge_distance)
    dbscan_clusters = [
        cluster
        for cluster in dbscan_clusters
        if np.linalg.norm(cluster["center"] - ref_center) <= track_distance_threshold
    ]

    selected = []
    if dbscan_clusters:
        selected = dbscan_clusters[:max_trunks]
        selected.sort(key=lambda item: item["center"][1])
    else:
        selected = [{"points": local_points, "center": local_points.mean(axis=0)}]

    trunks = []
    for idx, cluster in enumerate(selected, start=1):
        center, radius = circle_fit(cluster["points"])
        trunks.append(
            {
                "trunk_id": idx,
                "dbh_meshe_center": [round(float(center[0]), 5), round(float(center[1]), 5)],
                "dbh": round(float(2.0 * radius), 5),
                "cluster_points": cluster["points"],
                "fit_center": center,
                "fit_radius": radius,
            }
        )
    return {"slab_xy": slab_xy, "trunks": trunks, "tracked_center": ref_center}


def save_plot(output_path, model_name, dbh_height, slab_xy, trunks):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(slab_xy[:, 0], slab_xy[:, 1], s=8, c="#cccccc", label="slice points")

    colors = ["#d62728", "#1f77b4", "#2ca02c", "#ff7f0e"]
    theta = np.linspace(0.0, 2.0 * math.pi, 240)
    for idx, trunk in enumerate(trunks):
        points = trunk["cluster_points"]
        center = trunk["fit_center"]
        radius = trunk["fit_radius"]
        color = colors[idx % len(colors)]
        ax.scatter(points[:, 0], points[:, 1], s=12, c=color, label=f"trunk {trunk['trunk_id']} cluster")
        ax.plot(center[0] + radius * np.cos(theta), center[1] + radius * np.sin(theta), color=color, linewidth=2)
        ax.scatter([center[0]], [center[1]], c=color, s=35, marker="x")

    ax.set_title(f"{model_name} @ z={dbh_height:.2f} m")
    ax.set_xlabel("mesh x [m]")
    ax.set_ylabel("mesh y [m]")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)
        f.write("\n")


def update_consolidated_json(path, payload):
    items = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, list):
            items = []
            for item in loaded:
                if not isinstance(item, dict):
                    continue
                cleaned = {
                    "source_model": item.get("source_model"),
                    "slice_half_thickness": item.get("slice_half_thickness"),
                    "output_image": item.get("output_image"),
                    "trunks": [
                        {
                            "trunk_id": trunk.get("trunk_id"),
                            "dbh_meshe_center": trunk.get("dbh_meshe_center", trunk.get("mesh_center")),
                            "dbh": trunk.get("dbh"),
                        }
                        for trunk in item.get("trunks", [])
                        if isinstance(trunk, dict)
                    ],
                }
                items.append(cleaned)

    items = [item for item in items if item.get("source_model") != payload.get("source_model")]
    items.append(payload)
    items.sort(key=lambda item: item.get("source_model", ""))
    write_json(path, items)


def main():
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent

    obj_path = repo_root / args.models_dir / args.source_model / "meshes" / f"{args.source_model}.obj"
    output_image = (
        Path(args.output_image)
        if args.output_image
        else repo_root / "ground_truth" / "models" / "slice_fits" / f"{args.source_model}_slice_fit.png"
    )
    output_json = (
        Path(args.output_json)
        if args.output_json
        else repo_root / "ground_truth" / "models" / f"{args.source_model}_slice_fit.json"
    )
    consolidated_json = (
        Path(args.consolidated_json)
        if Path(args.consolidated_json).is_absolute()
        else repo_root / args.consolidated_json
    )
    output_image.parent.mkdir(parents=True, exist_ok=True)

    result = analyze_model(
        obj_path=obj_path,
        dbh_height=args.dbh_height,
        half_thickness=args.slice_half_thickness,
        eps=args.cluster_eps,
        min_samples=args.cluster_min_samples,
        max_trunks=args.max_trunks,
        auto_merge_distance=args.auto_merge_distance,
        track_distance_threshold=args.track_distance_threshold,
    )

    save_plot(
        output_path=output_image,
        model_name=args.source_model,
        dbh_height=args.dbh_height,
        slab_xy=result["slab_xy"],
        trunks=result["trunks"],
    )

    payload = {
        "source_model": args.source_model,
        "slice_half_thickness": args.slice_half_thickness,
        "track_distance_threshold": args.track_distance_threshold,
        "output_image": str(output_image.relative_to(repo_root)),
        "tracked_mesh_center": [round(float(v), 5) for v in result["tracked_center"]],
        "trunks": [
            {
                "trunk_id": trunk["trunk_id"],
                "dbh_meshe_center": trunk["dbh_meshe_center"],
                "dbh": trunk["dbh"],
            }
            for trunk in result["trunks"]
        ],
    }

    write_json(output_json, payload)
    update_consolidated_json(consolidated_json, payload)
    print(json.dumps(payload, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
