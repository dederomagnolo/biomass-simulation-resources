# Biomass Simulation Resources

This package aims to centralize 3D simulation assets used by the Biomass Group at LARIS (Laboratory of Autonomous Robots & Intelligent Systems), UFSCar.

The main goal is to provide reusable, research-oriented 3D models and worlds that better represent real forest environments, with special focus on the Brazilian Cerrado.

> [!IMPORTANT]
> This branch is the solution for **ROS 2**.
> If you are using **ROS Noetic**, go to the `ros-noetic` branch:
> https://github.com/dederomagnolo/biomass-simulation-resources/tree/ros-noetic

## Required versions
- Ubuntu: 24.04 (Noble)
- ROS 2: Jazzy
- Gazebo Sim: Harmonic (via `ros_gz_sim`)

## What this package provides

- `models/`: main model library
- `models/models.json`: model classification and optional tree measurements used by the JSON ground-truth generator
- `models/forest-gen-models/`: additional forest assets, originally from [kubja/gazebo-vegetation](https://github.com/kubja/gazebo-vegetation)
- `worlds/`: Gazebo world files
- `ground_truth/<world-name>/ground_truth.json` and `<world-name>_ground_truth.svg`: generated data and top-down map for each world
- `utils/generate_ground_truth_json.py`: generate the JSON and SVG from a world and the model catalog
- `worlds/world_template_empty.world`: empty template to create new worlds
- `run-world`: generic bash entrypoint to open worlds in Gazebo Sim

## Running from root

This flow assumes you already have a working ROS 2 + Gazebo Sim setup on your machine.

1. Build from the repository root:

```bash
colcon build --symlink-install --packages-select biomass_simulation_resources
```

2. Source your workspace:

```bash
source install/setup.bash
```

3. Run a world:

```bash
ros2 run biomass_simulation_resources run-world my_new_world
```

You can also pass:

- world name with extension:

```bash
ros2 run biomass_simulation_resources run-world world_template_empty.world
```

- absolute path to a `.world` file:

```bash
ros2 run biomass_simulation_resources run-world /absolute/path/to/my_new_world.world
```

`run-world` automatically exports the required resource paths for `models/`, `models/forest-gen-models/`, and `worlds/`.

## Add a new model

1. Place the asset under `models/<model-name>/` with a valid `model.config`, `model.sdf`, and any referenced meshes or textures. Keep geometry in meters and check its local origin; Gazebo uses the instance `<pose>` relative to that origin.
2. Add an entry to `models/models.json` with `source_model` matching the `model://<model-name>` URI and `type` set to `tree`, `bush`, or `object`. For a tree, add measured trunk data only when available using 3D tools. For other models, `type: "object"` puts their instances in `misc`.
3. Add the model to a world and regenerate that world's ground truth. Review `misc`: an uncataloged model is classified as `object`.

The catalog is the source of classification. Adding a folder under `models/` does not automatically add it to `models/models.json`. See [the ground-truth guide](docs/GROUND_TRUTH.md) for the entry format, units, and pose transformation.

## Create a new world

1. Copy the template:

```bash
cp worlds/world_template_empty.world worlds/my_new_world.world
```

2. Edit `worlds/my_new_world.world`: set `<world name="my_new_world">`, give every instance a unique `<name>`, and add each model with `<include>` and `<pose>x y z roll pitch yaw</pose>` (meters and radians). Embedded `<model>` elements are supported too.
3. Add a catalog entry in `models/models.json` for every new model (see below), then generate the JSON ground truth:

```bash
python3 utils/generate_ground_truth_json.py my_new_world --print-only
python3 utils/generate_ground_truth_json.py my_new_world
# To refresh every world:
python3 utils/generate_ground_truth_json.py --all
```

Check that `trunks`, `bushes`, and `misc` contain the expected instances and positions. The outputs are `ground_truth/my_new_world/ground_truth.json` and `ground_truth/my_new_world/my_new_world_ground_truth.svg`. See [the ground-truth guide](docs/GROUND_TRUTH.md) for the schema and validation rules.

4. Build/source the package as above, then run it:

```bash
ros2 run biomass_simulation_resources run-world my_new_world
```

## Docker (optional alternative)

If you are using Windows or prefer Docker, run the Compose command from the **parent project root** in Ubuntu WSL:

```bash
docker compose -f compose.ros2.yaml up biomass_ros2
```

In a second WSL terminal, enter the running container with `docker exec -it biomass-uav-stack-ros2 bash`. Inside it:

```bash
cd /root/biomass-uav-ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select biomass_simulation_resources
source /root/biomass-uav-ws/install/setup.bash
ros2 run biomass_simulation_resources run-world my_new_world
```
