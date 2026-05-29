#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: run-world <world-name-or-path> [paused:=false gui:=true ...]"
  echo "Examples:"
  echo "  run-world world_jean"
  exit 1
fi

if command -v rospack >/dev/null 2>&1; then
  PKG_ROOT="$(rospack find biomass_simulation_resources)"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [ -d "${SCRIPT_DIR}/worlds" ] && [ -d "${SCRIPT_DIR}/models" ]; then
    PKG_ROOT="${SCRIPT_DIR}"
  elif [ -d "${SCRIPT_DIR}/../../share/biomass_simulation_resources/worlds" ]; then
    PKG_ROOT="${SCRIPT_DIR}/../../share/biomass_simulation_resources"
  else
    echo "Could not resolve package root. Source your catkin workspace first." >&2
    exit 2
  fi
fi

WORLD_ARG="$1"
shift || true

if [[ "$WORLD_ARG" == */* ]] || [[ "$WORLD_ARG" == *.world ]]; then
  if [ -f "$WORLD_ARG" ]; then
    WORLD_FILE="$(cd "$(dirname "$WORLD_ARG")" && pwd)/$(basename "$WORLD_ARG")"
  else
    CANDIDATE="${PKG_ROOT}/worlds/${WORLD_ARG}"
    if [ -f "$CANDIDATE" ]; then
      WORLD_FILE="$CANDIDATE"
    else
      echo "World not found: $WORLD_ARG" >&2
      exit 3
    fi
  fi
else
  CANDIDATE="${PKG_ROOT}/worlds/${WORLD_ARG}.world"
  if [ ! -f "$CANDIDATE" ]; then
    echo "World not found: ${CANDIDATE}" >&2
    exit 3
  fi
  WORLD_FILE="$CANDIDATE"
fi

MODELS_1="${PKG_ROOT}/models"
MODELS_2="${PKG_ROOT}/models/forest-gen-models"
WORLDS_DIR="${PKG_ROOT}/worlds"

export GAZEBO_MODEL_PATH="${MODELS_1}:${MODELS_2}:${GAZEBO_MODEL_PATH:-}"
export GAZEBO_RESOURCE_PATH="${WORLDS_DIR}:${GAZEBO_RESOURCE_PATH:-}"

exec roslaunch gazebo_ros empty_world.launch world_name:="${WORLD_FILE}" "$@"
