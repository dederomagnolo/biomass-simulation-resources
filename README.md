# Biomass Simulation Resources - ROS Noetic Solution

> [!IMPORTANT]
> This branch is configured for **ROS Noetic**.
> If you are using **ROS 2**, go to the `master` branch:
> https://github.com/dederomagnolo/biomass-simulation-resources/tree/master

This repository centralizes 3D simulation assets used by the Biomass Group at LARIS (Laboratory of Autonomous Robots & Intelligent Systems), UFSCar.

The goal is to provide reusable, research-oriented models and worlds that better represent forest environments, with special focus on the Brazilian Cerrado.

## Required versions

- Ubuntu: 20.04 (Focal)
- ROS: Noetic
- Gazebo: Classic 11

## What this package provides

- `models/`: main model library
- `models/forest-gen-models/`: additional forest assets, originally from [kubja/gazebo-vegetation](https://github.com/kubja/gazebo-vegetation)
- `worlds/`: Gazebo world files
- `worlds/world_template.world`: empty template to create new worlds
- `run-world`: generic bash entrypoint to open worlds in Gazebo Classic

## Running from repository root (ROS Noetic)

This flow assumes ROS Noetic is already installed on your machine.

1. Build the catkin workspace from the repository root:

```bash
cd <your_catkin_ws>
catkin_make
```

2. Source the workspace:

```bash
source devel/setup.bash
```

3. Run a world:

```bash
rosrun biomass_simulation_resources run-world world_jean
```

You can also pass:

- world name with extension:

```bash
rosrun biomass_simulation_resources run-world world_template.world
```

- absolute path to a `.world` file:

```bash
rosrun biomass_simulation_resources run-world /absolute/path/to/world_jean.world
```

`run-world` automatically configures `GAZEBO_MODEL_PATH` and `GAZEBO_RESOURCE_PATH`.

## Launch files

Generic launch:

```bash
roslaunch biomass_simulation_resources view_world.launch
```

Choose a specific world:

```bash
roslaunch biomass_simulation_resources view_world.launch \
  world_file:=$(rospack find biomass_simulation_resources)/worlds/world_template.world
```

## Create a new world

1. Copy the template:

```bash
cp worlds/world_template.world worlds/my_new_world.world
```

2. Edit `worlds/my_new_world.world` and add your `model://...` includes.
3. Run it:

```bash
rosrun biomass_simulation_resources run-world my_new_world
```

## Docker (optional)

If you prefer a containerized setup:

```bash
docker compose build --no-cache
docker compose run --rm ros_noetic
```

Inside the container:

```bash
cd /catkin_ws
source /opt/ros/noetic/setup.bash
catkin build
source /catkin_ws/devel/setup.bash
rosrun biomass_simulation_resources run-world.sh world_jean
```
