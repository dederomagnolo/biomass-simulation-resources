cmake_minimum_required(VERSION 3.8)
project(biomass_simulation_resources)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch models worlds
  DESTINATION share/${PROJECT_NAME}
  USE_SOURCE_PERMISSIONS
)

install(PROGRAMS
  run-world.sh
  DESTINATION lib/${PROJECT_NAME}
  RENAME run-world
)

install(DIRECTORY ground_truth
  DESTINATION share/${PROJECT_NAME}
  USE_SOURCE_PERMISSIONS
)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
