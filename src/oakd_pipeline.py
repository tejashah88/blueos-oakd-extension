import depthai as dai

"""
Pipeline Visualization (auto-generated by ChatGPT as of 02/12/2025).
Prompt Source: https://gist.github.com/tejashah88/3672eb69bbeeceaccc246d60af852531

+-------------------+      +------------------+      +--------------------+
| Color Camera      | ---> | Video Encoder    | ---> | XLinkOut ('rgb')   |
| (camRgb)          |      | (videoRgbEnc)    |      | (rgbEncOut)        |
+-------------------+      +------------------+      +--------------------+

+-------------------+      +------------------+      +-------------------+
| Mono Camera Right | ---> |  Stereo Depth    | <--- | Mono Camera Left  |
| (monoRight)       |      |  (depth)         |      | (monoLeft)        |
+-------------------+      +------------------+      +-------------------+
                                   |
                                   v
+-------------------+      +------------------+      +--------------------+
| Colormap          | ---> | Video Encoder    | ---> | XLinkOut ('depth') |
| (colormap)        |      | (videoDepthEnc)  |      | (xout)             |
+-------------------+      +------------------+      +--------------------+
"""
def build_processing_pipeline():
    # Create pipeline
    pipeline = dai.Pipeline()

    # Create Color Camera Node
    camRgb = pipeline.create(dai.node.ColorCamera)
    camRgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)

    # Create Video Encoder Node
    videoRgbEnc = pipeline.create(dai.node.VideoEncoder)
    videoRgbEnc.setDefaultProfilePreset(25, dai.VideoEncoderProperties.Profile.H264_MAIN)

    # Create Output Stream Node for RGB Camera
    rgbEncOut = pipeline.create(dai.node.XLinkOut)
    rgbEncOut.setStreamName('rgb')

    # Link Color Camera nodes
    camRgb.video.link(videoRgbEnc.input)
    videoRgbEnc.bitstream.link(rgbEncOut.input)

    # Create Left & Right Mono Camera Nodes for Stereo Depth
    monoLeft = pipeline.create(dai.node.MonoCamera)
    monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoLeft.setCamera('left')

    monoRight = pipeline.create(dai.node.MonoCamera)
    monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoRight.setCamera('right')

    # Create Depth Node to produce the depth map
    depth = pipeline.create(dai.node.StereoDepth)
    depth.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
    depth.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7)
    depth.setLeftRightCheck(True)
    depth.setExtendedDisparity(True)
    # NOTE: Subpixel disparity is of UINT16 format, which is unsupported by VideoEncoder
    depth.setSubpixel(False)

    # Link output of Mono Camera Nodes to input of Depth Node
    monoLeft.out.link(depth.left)
    monoRight.out.link(depth.right)

    # Colormap
    colormap = pipeline.create(dai.node.ImageManip)
    colormap.initialConfig.setColormap(dai.Colormap.TURBO, depth.initialConfig.getMaxDisparity())
    colormap.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)

    videoDepthEnc = pipeline.create(dai.node.VideoEncoder)
    # Depth resolution/FPS will be the same as mono resolution/FPS
    videoDepthEnc.setDefaultProfilePreset(monoLeft.getFps(), dai.VideoEncoderProperties.Profile.H264_HIGH)

    # Link
    depth.disparity.link(colormap.inputImage)
    colormap.out.link(videoDepthEnc.input)

    xout = pipeline.create(dai.node.XLinkOut)
    xout.setStreamName('depth')
    videoDepthEnc.bitstream.link(xout.input)

    return pipeline
