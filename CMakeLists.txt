cmake_minimum_required(VERSION 3.0.2)
project(biomass_simulation_resources)

find_package(catkin REQUIRED)

catkin_package()

catkin_add_env_hooks(50.${PROJECT_NAME}
  SHELLS sh
  DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/env-hooks
)

install(DIRECTORY launch models worlds
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
  USE_SOURCE_PERMISSIONS
)

install(PROGRAMS
  run-world.sh
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
