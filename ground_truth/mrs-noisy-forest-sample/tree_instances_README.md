# tree_instances.json

Ground-truth per-trunk data for the **mrs-noisy-forest-sample** scene.
Complements `mrs-noisy-forest-sample_ground_truth.csv`, which only contains
one (x, y) position per tree instance (the model origin). This file adds
individual trunk positions and diameters extracted from the 3-D mesh of each
tree model.

---

## Schema

### Top-level key

Each key (`"T1"` … `"T8"`) identifies a **tree instance** in the scene.

### Instance fields

| Field | Type | Description |
|---|---|---|
| `tree_id` | int | Numeric ID matching the CSV ground-truth file |
| `model_name` | string | Name of the Gazebo/SDF instance (unique per scene) |
| `base_model` | string | Name of the source 3-D model shared by clones |
| `instance_world_x/y` | float | World-frame origin of the model as placed in Gazebo (metres) — this is what the CSV stores |
| `n_trunks` | int | Number of distinct trunks (1 for single-stem, 2 for bifurcated) |
| `bifurcated` | bool | True if the tree splits into 2 stems above the base |
| `bifurcation_height_m` | float \| null | Height at which the split occurs (metres above ground) |
| `d_base_cm` | float | Diameter of the single base trunk at ~0.1 m height (cm) |
| `coord_note` | string | Present only when there is known positional uncertainty (see new_tree_3 below) |

### Per-trunk fields (`trunks[]`)

| Field | Type | Description |
|---|---|---|
| `trunk_id` | int | 1-indexed within the instance |
| `dap_cm` | float | **DAP** — Diameter at Breast Height (1.3 m). Standard forestry measurement (cm) |
| `world_x/y` | float | World-frame centre of this trunk at DBH height (metres). Use this for detector evaluation |
| `model_local_x/y` | float | Same centre expressed as offset from the model origin (`world = instance_world + model_local`) |

> **Note:** DAP height is always 1.3 m (standard); it is not stored in the JSON
> to avoid redundancy.

---

## How this file was generated

### 1. Instance origin positions

`instance_world_x/y` were read directly from the Gazebo world file
(`.world` / SDF). These match the coordinates in the CSV ground-truth file.

### 2. OBJ mesh analysis — coordinate systems

Each model is an OBJ file. Two different conventions were found:

| Model | Convention | Height axis | Horizontal axes |
|---|---|---|---|
| `new_tree_1`, `new_tree_2` | **Z-up** (standard) | OBJ `z` | OBJ `x`, `y` |
| `new_tree_3` | **Y-up** (Blender export) | OBJ `y` | OBJ `x`, `-z` |

For Y-up models the world offset is computed as
`model_local = (OBJ_x, -OBJ_z)`.
This introduces ~0.2 m positional uncertainty because Blender's Y-up export
does not perfectly round-trip through the SDF `<scale>` and rotation chain;
hence the `coord_note` on T7/T8.

### 3. Trunk centre extraction

For each model, all OBJ vertices were loaded in Python (`numpy`).

**Step A — horizontal slicing.**
A thin slab of vertices was taken at the target height (0.1 m for base
diameter, 1.3 m for DAP). Slab thickness: ±0.05 m.

**Step B — DBSCAN clustering.**
DBSCAN (eps ≈ 0.15 m, min_samples = 5) was applied to the XY coordinates
of the slab to separate individual trunks from branches or foliage vertices.
The number of clusters at each height was tracked to detect bifurcations
(new_tree_3: 1 cluster below 0.5 m → 2 clusters above 0.5 m).

**Step C — circle fitting.**
For each cluster, a circle was fitted to the outermost vertices using
**Nelder-Mead minimisation** (scipy):

```
minimise  Σ (dist(vᵢ, circle_centre) − r)²
```

The resulting centre is `model_local_x/y` and the diameter is
`2r × 100` cm.

**Step D — world coordinates.**
`world_x = instance_world_x + model_local_x`
`world_y = instance_world_y + model_local_y`

### 4. Bifurcation confirmation

For new_tree_3 (T7, T8) the bifurcation was also confirmed independently
via a 2-D LiDAR density map (`numpy.histogram2d`) of the accumulated bag
point cloud, which shows two distinct trunk hotspots ~0.25–0.3 m apart,
consistent with the OBJ analysis.

---

## Reproducing for a new model

1. Load the OBJ vertices with numpy:
   ```python
   verts = []
   with open("model.obj") as f:
       for line in f:
           if line.startswith("v "):
               verts.append(list(map(float, line.split()[1:4])))
   verts = np.array(verts)
   ```

2. Identify the height axis (Z-up → axis 2; Y-up → axis 1).

3. For each target height h, extract the slab:
   ```python
   slab = verts[np.abs(verts[:, height_axis] - h) < 0.05]
   xy = slab[:, [x_axis, y_axis]]
   ```

4. Run DBSCAN to count and separate trunks.

5. Fit a circle per cluster with scipy Nelder-Mead.

6. Add `instance_world_x/y` to get world coordinates.
   For Y-up models: `world_local = (OBJ_x, -OBJ_z)`.
