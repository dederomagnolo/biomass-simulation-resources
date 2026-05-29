#!/usr/bin/env sh

_bsr_share="${CATKIN_ENV_HOOK_WORKSPACE}/share/biomass_simulation_resources"
_bsr_models="${_bsr_share}/models:${_bsr_share}/models/forest-gen-models"
_bsr_worlds="${_bsr_share}/worlds"

if [ -z "${GAZEBO_MODEL_PATH}" ]; then
  export GAZEBO_MODEL_PATH="${_bsr_models}"
else
  export GAZEBO_MODEL_PATH="${GAZEBO_MODEL_PATH}:${_bsr_models}"
fi

if [ -z "${GAZEBO_RESOURCE_PATH}" ]; then
  export GAZEBO_RESOURCE_PATH="${_bsr_worlds}"
else
  export GAZEBO_RESOURCE_PATH="${GAZEBO_RESOURCE_PATH}:${_bsr_worlds}"
fi
