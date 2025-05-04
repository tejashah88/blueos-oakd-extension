#!/usr/bin/env python3

import os
import time
import threading
import traceback


import depthai as dai

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib, GstRtsp

from register_stream import check_streams
from oakd_pipeline import build_processing_pipeline
from gstreamer_pipelines import RECEIVE_VIDEO_DATA_PIPELINE, UPLOAD_VIDEO_DATA_PIPELINE

SOCKET_RGB_PATH = "/tmp/socketrgb"
SOCKET_DEPTH_PATH = "/tmp/socketdepth"


class RtspSystem(GstRtspServer.RTSPMediaFactory):
    def __init__(self, **properties):
        super(RtspSystem, self).__init__(**properties)

    def start(self):
        self.system_thread = threading.Thread(target=self._thread_rtsp)
        self.system_thread.start()

    def _thread_rtsp(self):
        loop = GLib.MainLoop()
        loop.run()


    def do_create_element(self, url):
        name = url.abspath.split('/')[-1]
        if name == 'rgb':
            return Gst.parse_launch(RECEIVE_VIDEO_DATA_PIPELINE.format(SOCKET_RGB_PATH))
        elif name == 'depth':
            return Gst.parse_launch(RECEIVE_VIDEO_DATA_PIPELINE.format(SOCKET_DEPTH_PATH))
        else:
            pass

    def do_configure(self, rtsp_media):
        self.appsrc = rtsp_media.get_element().get_child_by_name('source')
        # Docs: https://lazka.github.io/pgi-docs/GstRtsp-1.0/flags.html#GstRtsp.RTSPProfile
        self.set_profiles(GstRtsp.RTSPProfile.AVPF)


class RTSPServer(GstRtspServer.RTSPServer):
    def __init__(self, **properties):
        super(RTSPServer, self).__init__(**properties)
        self.rgb_rtsp = RtspSystem()
        self.depth_rtsp = RtspSystem()
        self.app_pipeline = {}
        self.appsrc = {}
        Gst.init(None)

        for rtsp in [(self.rgb_rtsp, 'rgb', SOCKET_RGB_PATH), (self.depth_rtsp, 'depth', SOCKET_DEPTH_PATH)]:
            rtsp, name, socket = rtsp
            rtsp.set_shared(True)
            rtsp.start()
            self.get_mount_points().add_factory(f"/{name}", rtsp)
            self.app_pipeline[name] = self.start_app_pipeline(socket)
            self.appsrc[name] = self.app_pipeline[name].get_child_by_name('source')
        self.attach(None)

        # MCM thread
        self.mcm_thread = threading.Thread(target=check_streams)
        self.mcm_thread.start()
        GLib.timeout_add_seconds(2, self.timeout)

    def timeout(self):
        pool = self.get_session_pool()
        pool.cleanup()
        return True

    def send_data(self, kind, data):
        retval = self.appsrc[kind].emit('push-buffer', Gst.Buffer.new_wrapped(data))
        if retval != Gst.FlowReturn.OK:
            print("buffer full?")


    def start_app_pipeline(self, file):
        launch_str = UPLOAD_VIDEO_DATA_PIPELINE.format(file)
        print(launch_str)
        pipeline = Gst.parse_launch(launch_str)
        pipeline.set_state(Gst.State.PLAYING)
        return pipeline


# Clear any existing sockets before creating new ones
for socket in [SOCKET_RGB_PATH, SOCKET_DEPTH_PATH]:
    if os.path.exists(socket):
        os.remove(socket)


def detect_cameras(device_info):
    camera_config = {}

    with dai.Device(device_info) as device:
        available_cameras = device.getConnectedCameras()

        camera_config['rgb'] = dai.CameraBoardSocket.RGB in available_cameras
        camera_config['depth_left'] = dai.CameraBoardSocket.LEFT in available_cameras
        camera_config['depth_right'] = dai.CameraBoardSocket.RIGHT in available_cameras

    return camera_config


while True:
    print('\n')

    # Step 1: Find connected devices
    print('1) Looking for DepthAI devices...')
    camera_devices = dai.Device.getAllAvailableDevices()
    if not camera_devices:
        print('No DepthAI devices found! Restarting loop...')
        time.sleep(1)
        continue

    device_info = camera_devices[0]
    print(f'Detected device: {device_info.name}')

    # Step 2: Recognize cameras on device
    print('2) Recognizing cameras...')
    camera_config = detect_cameras(device_info)

    if not camera_config["rgb"] and not camera_config["depth_left"] and not camera_config["depth_right"]:
        print('Unable to find any cameras on device! Restarting loop...')
        time.sleep(1)
        continue
    else:
        print('Detected Cameras:')
        print(f' - RGB: {camera_config["rgb"]}')
        print(f' - Depth (left): {camera_config["depth_left"]}')
        print(f' - Depth (right): {camera_config["depth_right"]}')


    # Step 3: Build pipeline based on found cameras
    print('3) Building pipeline...')
    try:
        vision_pipeline = build_processing_pipeline(camera_config)
    except Exception as ex:
        print(f'Unable to build pipeline: {ex}')
        traceback.print_exception(ex)
        print('Restarting loop...')
        continue

    # Step 4: Start RTSP Server
    print('4) Starting RTSP Server...')
    rtsp_server = RTSPServer()

    # Step 5: Starting vision data loop
    print('5) Starting vision data loop...')
    try:
        print('5a) Connecting to device...')
        with dai.Device(vision_pipeline) as device:
            # Output queue(s) will be used to get the encoded data from the output defined above
            outputQueueNames = device.getOutputQueueNames()

            print('5b) Preparing output queues...')
            rgbQ = device.getOutputQueue(
                name='rgb',
                maxSize=30,
                blocking=True
            ) if 'rgb' in outputQueueNames else None

            depthQ = device.getOutputQueue(
                name='depth',
                maxSize=30,
                blocking=True
            ) if 'depth' in outputQueueNames else None

            print("RTSP stream available at rtsp://<server-ip>:8554/preview")
            print('Starting streaming of video data...')

            while True:
                if rgbQ is not None and rgbQ.has():
                    rgbData = rgbQ.get().getData()
                    rtsp_server.send_data('rgb', rgbData)

                if depthQ is not None and depthQ.has():
                    depthData = depthQ.get().getData()
                    rtsp_server.send_data('depth', depthData)
    except KeyboardInterrupt:
        # Keyboard interrupt (Ctrl + C) detected, ignore it
        pass
    except RuntimeError as ex:
        if 'No available devices' in str(ex):
            print('Unable to initialize OAK-D camera')
        elif 'Communication exception' in str(ex):
            print('Lost connection to camera')
        else:
            print(ex)

        print('Restarting loop after 5 seconds...')
        time.sleep(5)
