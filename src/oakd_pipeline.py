import depthai as dai

from camera_streams import SupportedConfig

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


DEFAULT_FPS = 15


def build_processing_pipeline(supported_config: SupportedConfig):
    # Create pipeline
    pipeline = dai.Pipeline()


    if supported_config.rgb:
        # Create Color Camera Node
        camRgb = pipeline.create(dai.node.ColorCamera)
        camRgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
        camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        camRgb.setFps(DEFAULT_FPS)

        # Create Video Encoder Node
        videoRgbEnc = pipeline.create(dai.node.VideoEncoder)
        videoRgbEnc.setDefaultProfilePreset(camRgb.getFps(), dai.VideoEncoderProperties.Profile.H264_MAIN)

        # Create Output Stream Node for RGB Camera
        rgbEncOut = pipeline.create(dai.node.XLinkOut)
        rgbEncOut.setStreamName('rgb')

        # Link Color Camera nodes
        camRgb.video.link(videoRgbEnc.input)
        videoRgbEnc.bitstream.link(rgbEncOut.input)


    if supported_config.mono_left:
        # Create Left Mono Camera Node
        monoLeft = pipeline.create(dai.node.MonoCamera)
        monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B)
        monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoLeft.setCamera('left')
        monoLeft.setFps(DEFAULT_FPS)

        # Create Video Encoder Node
        videoMonoLeftEnc = pipeline.create(dai.node.VideoEncoder)
        videoMonoLeftEnc.setDefaultProfilePreset(monoLeft.getFps(), dai.VideoEncoderProperties.Profile.H264_MAIN)

        # Create Output Stream Node for RGB Camera
        monoLeftEncOut = pipeline.create(dai.node.XLinkOut)
        monoLeftEncOut.setStreamName('mono_left')

        # Link Mono Left Camera nodes
        monoLeft.out.link(videoMonoLeftEnc.input)
        videoMonoLeftEnc.bitstream.link(monoLeftEncOut.input)


    if supported_config.mono_right:
        # Create Right Mono Camera Node
        monoRight = pipeline.create(dai.node.MonoCamera)
        monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C)
        monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoRight.setCamera('right')
        monoRight.setFps(DEFAULT_FPS)

        # Create Video Encoder Node
        videoMonoRightEnc = pipeline.create(dai.node.VideoEncoder)
        videoMonoRightEnc.setDefaultProfilePreset(monoRight.getFps(), dai.VideoEncoderProperties.Profile.H264_MAIN)

        # Create Output Stream Node for RGB Camera
        monoRightEncOut = pipeline.create(dai.node.XLinkOut)
        monoRightEncOut.setStreamName('mono_right')

        # Link Mono Right Camera nodes
        monoRight.out.link(videoMonoRightEnc.input)
        videoMonoRightEnc.bitstream.link(monoRightEncOut.input)


    if supported_config.depth:
        # Create Depth Node to produce the depth map from both mono cameras
        depth = pipeline.create(dai.node.StereoDepth)
        depth.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
        depth.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7)
        depth.setLeftRightCheck(True)
        depth.setExtendedDisparity(True)
        # NOTE: Subpixel disparity is of UINT16 format, which is unsupported by VideoEncoder
        depth.setSubpixel(False)

        # Link output of Mono Camera Nodes to input of Depth Node
        monoLeft.out.link(depth.left) # type: ignore
        monoRight.out.link(depth.right) # type: ignore

        # Colormap
        colormap = pipeline.create(dai.node.ImageManip)
        colormap.initialConfig.setColormap(dai.Colormap.TURBO, depth.initialConfig.getMaxDisparity())
        colormap.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)

        videoDepthEnc = pipeline.create(dai.node.VideoEncoder)
        # Depth resolution/FPS will be the same as mono resolution/FPS
        videoDepthEnc.setDefaultProfilePreset(monoLeft.getFps(), dai.VideoEncoderProperties.Profile.H264_MAIN) # type: ignore

        # Link
        depth.disparity.link(colormap.inputImage)
        colormap.out.link(videoDepthEnc.input)

        xout = pipeline.create(dai.node.XLinkOut)
        xout.setStreamName('depth')
        videoDepthEnc.bitstream.link(xout.input)

    return pipeline
