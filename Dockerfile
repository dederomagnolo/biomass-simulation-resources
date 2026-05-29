FROM ros:noetic-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-catkin-tools \
    ros-noetic-gazebo-ros \
    ros-noetic-gazebo-plugins \
    gazebo11 \
    git \
    && rm -rf /var/lib/apt/lists/*

SHELL ["/bin/bash", "-c"]

RUN mkdir -p /catkin_ws/src
WORKDIR /catkin_ws

RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc
RUN echo "source /catkin_ws/devel/setup.bash 2>/dev/null || true" >> /root/.bashrc

CMD ["bash"]
