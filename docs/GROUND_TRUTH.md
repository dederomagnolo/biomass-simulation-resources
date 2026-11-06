# World ground truth JSON

The **`models/models.json`** catalog defines each model's type (`tree`, `bush`, or `object`) and, when available, trunk measurements. **`utils/generate_ground_truth_json.py`** reads that catalog and the world's SDF file. It writes `ground_truth/<world-name>/ground_truth.json` and `<world-name>_ground_truth.svg`.

## Create or update ground truth

From the `biomass-simulation-resources` package root:

```bash
python3 utils/generate_ground_truth_json.py my_new_world --print-only
python3 utils/generate_ground_truth_json.py my_new_world
python3 utils/generate_ground_truth_json.py --all
```

Pass the filename in `worlds/`, with or without `.world`. `--print-only` prints the JSON without writing either file. `--all` generates both files for every `.world` file in `worlds/`, including templates with no vegetation. Regenerate them whenever you change instances or poses in a world. The script reads `<model>` and `<include>` elements directly under `<world>`; it does not need earlier ground-truth files.

## Register a model

For each `models/models.json` entry, `source_model` must match the identifier after `model://` in the world. For an embedded `<model>` with a mesh URI, use the first component of that URI. If an asset lives in a collection subdirectory but the world uses a short name, register that name as an alias with `alias_of` pointing to the main entry. Names must match the URI exactly; the generator does not infer the type from the name.

```json
{"source_model": "<model-name>", "type": "tree", "trunks": [
  {"trunk_id": 1, "mesh_dbh_position": [0.0, 0.0], "dbh": 0.2}
]}
```

This example shows the structure only: **do not copy its DBH or local position without measuring the new model**. Accepted types:

- `tree`: instances go into `trunks`. A model can define one entry per physical trunk. If the trunk is not calibrated, omit `trunks`; the ground truth will contain only the model origin.
- `bush`: instances go into `bushes`.
- `object`: instances go into `misc` with `"type": "object"`.

`dbh` is the trunk **diameter**, not radius, at 1.30 m above the model origin, in meters. `mesh_dbh_position` is the XY center of that cross-section in model coordinates. Optional `height` and `biffurcation_height` are also in meters. Preserve existing measurements when editing the catalog. A new folder under `models/` is **not registered automatically**; add its entry manually. If a model used in a world is absent from the catalog, the generator places it in `misc` as an `object`; review that classification before using the ground truth.


**Measurement caveat:** the archived fit image for `new_tree_8` is labeled `z=1.00 m`, while the active catalog currently calls its 0.18884 m diameter `dbh` and records bifurcation at 1.17 m. That fit does not establish a diameter at the standard 1.30 m height. Treat this model's `dbh` and `mesh_dbh_position` as unverified for DBH-based evaluation until its 1.30 m cross-section is measured and the catalog and affected ground truth are updated.

## Ground-truth schema

```json
{
  "world_name": "<world-name>",
  "limits": {"x_min": -1, "x_max": 1, "y_min": -1, "y_max": 1},
  "trunks": [{"tree_id": 1, "name": "<tree-instance>", "source_model": "<tree-model>", "obj_position": [0, 0, 0], "yaw": 0}],
  "bushes": [],
  "misc": [{"object_id": 1, "type": "object", "name": "<object-instance>", "source_model": "<object-model>", "obj_position": [0, 0, 0], "yaw": 0}]
}
```

The example shows the structure only; a real file contains every instance and all available measurements. `world_name` comes from `<world name>`. `name` identifies the **instance**, not the model. `obj_position` contains the first three values of `<pose>`; `yaw` is its sixth value, a rotation around Z in **radians**. A missing pose means zero. `tree_id`, `bush_id`, and `object_id` start at 1 and follow world instance order within each category.

`mesh_dbh_position` is the trunk's local XY center at 1.30 m above the model origin. For a tree without roll or pitch, `dbh_world_position` is:

```text
dbh_x = obj_x + local_x*cos(yaw) - local_y*sin(yaw)
dbh_y = obj_y + local_x*sin(yaw) + local_y*cos(yaw)
```

The generator rejects a calibrated tree with nonzero roll or pitch until a full 3D transform is implemented. The DBH center can differ from the model origin; check each model's origin and local geometry. Do not present nominal modeling parameters as field measurements.

`limits` follows the historical convention: the minimum and maximum XY coordinates of **trees and bushes**, expanded by 1 m and rounded outward with `floor`/`ceil`. If there is no vegetation, it uses `misc` positions. This rectangle is an evaluation window, not the extent of foliage or ground. The `tree-mapper` tree reader ignores `misc`; those entries remain in the JSON to identify other objects.

## Check the result

Compare counts and names in `trunks`, `bushes`, and `misc` with the world's `<model>` and `<include>` elements. An instance with multiple physical trunks creates multiple `trunks` entries. Check that the SVG markers match the JSON vegetation entries. Review any unknown model placed in `misc` and register its correct type when needed. The generator uses only `models.json` and the world.
