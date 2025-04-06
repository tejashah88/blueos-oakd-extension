# Use multiarch/qemu-user-static only for non-native architectures. Ending tag is excluded due to specifying platform
# See https://docs.docker.com/reference/dockerfile/#automatic-platform-args-in-the-global-scope for more info
FROM --platform=$BUILDPLATFORM multiarch/qemu-user-static AS qemu

# Start with base image
FROM luxonis/depthai-library:latest

# Copy QEMU binary only when cross-compiling with ARM and ARM64
COPY --from=qemu /usr/bin/qemu-*-static /usr/bin/

# Setup dependencies for RTSP streaming
RUN apt-get update && \
    apt-get install -y \
        libgirepository1.0-dev \
        gstreamer1.0-plugins-base \
        libopenblas-dev \
        gir1.2-gst-rtsp-server-1.0 \
        python3-gi

# Install python dependencies
COPY requirements.txt /requirements.txt

RUN apt-get install -y ninja-build && \
    pip install -r /requirements.txt && \
    apt auto-remove -y ninja-build

# Copy source code
COPY src /src
ENTRYPOINT ["python", "/src/stream.py"]

LABEL version="1.0.0"
LABEL permissions='\
{\
   "NetworkMode":"host",\
   "HostConfig":{\
      "Privileged":true,\
      "NetworkMode":"host",\
      "Binds":[\
         "/dev/bus/usb:/dev/bus/usb"\
      ],\
      "DeviceCgroupRules":[\
         "c 189:* rmw"\
      ]\
   }\
}'

LABEL authors='[\
    {\
        "name": "Tejas Shah",\
        "email": "tbshah@csuchico.edu"\
    }\
]'
LABEL company='{\
        "about": "American Institute of Mechatronics Engineers",\
        "name": "AIME - MATE ROV",\
        "email": "tbshah@csuchico.edu"\
    }'
LABEL type="device-integration"
LABEL readme='https://raw.githubusercontent.com/tejashah88/blueos-oakd-extension/{tag}/Readme.md'
LABEL links='{\
        "website": "https://github.com/tejashah88/blueos-oakd-extension/",\
        "support": "https://github.com/tejashah88/blueos-oakd-extension/"\
    }'
LABEL requirements="core >= 1.1"
