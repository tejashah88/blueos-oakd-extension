# BlueOS Oak-D Extension (Improved)

This extension is a [fork of Willian Galvani's Oakd-extension project](https://github.com/Williangalvani/Oakd-extension), which originally "exposes the Stereo Depth Disparity and RGB video from Oak-D cameras into RTSP streams that can be displayed in Cockpit". This fork adds a few tweaks for improved stability and more reliable building for use by the CSUC MATE ROV team.

Tweaks:
- Added debugging messages and proper handling of missing Oak-D device
- Added support for viewing mono-camera feeds independently
- Added reliable building for `linux/arm64/v8` thanks to QEMU binary injection in the `Dockerfile`
  - Would sometimes fail due to "Segmentation fault" from the `ninja-build` dependency (cause is unknown at the moment)
- Added Github Action for deployment to Docker Hub, with retry logic if builds intermittently failed

## Building

### For All Architectures (Recommended)
```bash
# NOTE: Run this to setup QEMU stuff
docker run --privileged --rm tonistiigi/binfmt --install all

# NOTE: Run this to allow multi-arch builds. "multi-arch-builder" is an example name
docker buildx create --use --name multi-arch-builder

docker buildx build --platform linux/arm/v7,linux/arm64/v8,linux/amd64 . -t tejashah88/blueos-oakd-ext:latest --output type=image,push=false
```

### For Specific Architectures
```bash
# ARM Support (for Raspberry Pi 3-like devices)
docker buildx build --platform linux/arm/v7 . -t tejashah88/blueos-oakd-ext:latest --output type=image,push=false

# ARM 64 Support (for Raspberry Pi 4-like devices)
docker buildx build --platform linux/arm64/v8 . -t tejashah88/blueos-oakd-ext:latest --output type=image,push=false

# x86_64 Arch Support
docker buildx build --platform linux/amd64 . -t tejashah88/blueos-oakd-ext:latest --output type=image,push=false
```

## Loading onto BlueOS
1. Go to http://192.168.2.2/tools/extensions-manager
2. Click the "+" button on the bottom right
3. Fill out the details
    * Extension Identifier: `tejashah88.blueos-oakd`
    * Extension Name: `Oak-D Video Streams (Improved)`
    * Docker image: `tejashah88/blueos-oakd-ext`
    * Docker tag: `latest`
    * Original Settings:
```json
{
   "NetworkMode":"host",
   "HostConfig":{
      "Privileged":true,
      "NetworkMode":"host",
      "Binds":[
         "/dev/bus/usb:/dev/bus/usb"
      ],
      "DeviceCgroupRules":[
         "c 189:* rmw"
      ]
   }
}
```

4. Click "Create" to pull the image

## Updating the extension
1. Enable "Pirate Mode"
2. Go to http://192.168.2.2/tools/extensions-manager
3. Click the "Edit" button on the "Oak-D Video Streams (Improved)" extension.
4. Click the "Save" button to pull the latest version from Docker Cloud.
