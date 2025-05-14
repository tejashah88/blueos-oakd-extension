#!/usr/bin/env python3

import os
import pprint
import time
import threading
import traceback

import depthai as dai
import requests

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib, GstRtsp # type: ignore

from oakd_pipeline import build_processing_pipeline
from camera_streams import SupportedConfig, CameraStream, AllCameraStreams
from gstreamer_pipelines import RECEIVE_VIDEO_DATA_PIPELINE, UPLOAD_VIDEO_DATA_PIPELINE


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
        stream_id = url.abspath.split('/')[-1]

        if stream_id in AllCameraStreams:
            socket_path = AllCameraStreams.get(stream_id).socket_path
            return Gst.parse_launch(RECEIVE_VIDEO_DATA_PIPELINE.format(socket_path))


    def do_configure(self, rtsp_media):
        self.appsrc = rtsp_media.get_element().get_child_by_name('source')
        # Docs: https://lazka.github.io/pgi-docs/GstRtsp-1.0/flags.html#GstRtsp.RTSPProfile
        self.set_profiles(GstRtsp.RTSPProfile.AVPF)


class CameraStreamChecker:
    MCM_ENDPOINT = 'http://127.0.0.1:6020/streams'


    def __init__(self, supported_config: SupportedConfig):
        self.supported_config = supported_config


    def has_oak_stream(self, current_streams, name):
        for stream in current_streams:
            if stream['video_and_stream']['name'] == name:
                return True
        return False


    def add_mcm_stream(self, name, endpoint):
        new_stream = {
            'name': name,
            'source': 'Redirect',
            'stream_information': {
                'endpoints': [
                    f'rtsp://127.0.0.1:8554/{endpoint}'
                ],
                'configuration': {
                    'type': 'redirect'
                },
                'extended_configuration': {
                    'thermal': False,
                    'disable_mavlink': True
                }
            }
        }

        print(f'Adding stream "{name}" as "{endpoint}"...')
        stream_add_response = requests.post(self.MCM_ENDPOINT, json=new_stream)
        pprint.pprint(stream_add_response.text)


    def check_streams(self):
        while True:
            current_streams = requests.get(self.MCM_ENDPOINT).json()
            for cam_stream in AllCameraStreams.all_streams():
                try:
                    stream_is_supported = self.supported_config.check(cam_stream.id)
                    stream_is_ready = self.has_oak_stream(current_streams, cam_stream.name)

                    if stream_is_supported and not stream_is_ready:
                        self.add_mcm_stream(cam_stream.name, cam_stream.endpoint)
                except Exception as ex:
                    print(ex)

            # Wait 3 seconds before checking again
            time.sleep(3)


class RTSPServer(GstRtspServer.RTSPServer):
    def __init__(self, supported_config: SupportedConfig, **properties):
        super(RTSPServer, self).__init__(**properties)

        if supported_config.rgb:          self.rgb_rtsp = RtspSystem()
        elif supported_config.mono_left:  self.mono_left_rtsp = RtspSystem()
        elif supported_config.mono_right: self.mono_right_rtsp = RtspSystem()
        elif supported_config.depth:      self.depth_rtsp = RtspSystem()

        self.app_pipeline = {}
        self.appsrc = {}
        Gst.init(None)

        if supported_config.rgb:          self.setup_rtsp_stream(AllCameraStreams.rgb, self.rgb_rtsp)
        elif supported_config.mono_left:  self.setup_rtsp_stream(AllCameraStreams.mono_left, self.mono_left_rtsp)
        elif supported_config.mono_right: self.setup_rtsp_stream(AllCameraStreams.mono_right, self.mono_right_rtsp)
        elif supported_config.depth:      self.setup_rtsp_stream(AllCameraStreams.depth, self.depth_rtsp)

        self.attach(None)

        # MCM thread
        self.camera_stream_checker = CameraStreamChecker(supported_config)
        self.mcm_thread = threading.Thread(target=self.camera_stream_checker.check_streams)
        self.mcm_thread.start()
        GLib.timeout_add_seconds(2, self.timeout)


    def setup_rtsp_stream(self, stream_info: CameraStream, rtsp_system):
        rtsp_system.set_shared(True)
        rtsp_system.start()

        self.get_mount_points().add_factory(f"/{stream_info.endpoint}", rtsp_system)
        self.app_pipeline[stream_info.endpoint] = self.start_app_pipeline(stream_info.socket_path)
        self.appsrc[stream_info.endpoint] = self.app_pipeline[stream_info.endpoint].get_child_by_name('source')


    def timeout(self):
        pool = self.get_session_pool()
        pool.cleanup()
        return True


    def send_data(self, kind, data):
        retval = self.appsrc[kind].emit('push-buffer', Gst.Buffer.new_wrapped(data))
        if retval != Gst.FlowReturn.OK:
            print("Warning: Buffer may be full?")


    def start_app_pipeline(self, file):
        launch_str = UPLOAD_VIDEO_DATA_PIPELINE.format(file)
        print(f'Launch string for upload video data pipeline: {launch_str}')

        pipeline = Gst.parse_launch(launch_str)
        pipeline.set_state(Gst.State.PLAYING)
        return pipeline



def remove_existing_sockets():
    # Clear any existing sockets before creating new ones
    for stream in AllCameraStreams.all_streams():
        if os.path.exists(stream.socket_path):
            os.remove(stream.socket_path)



def detect_cameras(device_info):
    supported_config = {}

    with dai.Device(device_info) as device:
        available_cameras = device.getConnectedCameras()

        supported_config = SupportedConfig(
            rgb = dai.CameraBoardSocket.CAM_A in available_cameras,
            mono_left = dai.CameraBoardSocket.CAM_B in available_cameras,
            mono_right = dai.CameraBoardSocket.CAM_C in available_cameras,
        )

    return supported_config


while True:
    print('\n')

    # Step 0: Cleanup potentially existing sockets
    remove_existing_sockets()

    # Step 1: Find connected devices
    print('1) Looking for DepthAI devices...')
    camera_devices = dai.Device.getAllAvailableDevices()
    if len(camera_devices) == 0:
        print('No DepthAI devices found! Restarting loop...')
        time.sleep(1)
        continue

    device_info = camera_devices[0]
    print(f'Detected device: {device_info.name}')

    # Step 2: Recognize cameras on device
    print('2) Recognizing cameras...')
    supported_config = detect_cameras(device_info)

    if not supported_config.rgb and not supported_config.mono_left and not supported_config.mono_right:
        print('Unable to find any cameras on device! Restarting loop...')
        time.sleep(1)
        continue
    else:
        print('Supported Configuration:')
        print(f' - RGB: {supported_config.rgb}')
        print(f' - Mono (left): {supported_config.mono_left}')
        print(f' - Mono (right): {supported_config.mono_right}')
        print(f' - Depth: {supported_config.depth}')

    # Step 3: Build pipeline based on found cameras
    print('3) Building pipeline...')
    try:
        vision_pipeline = build_processing_pipeline(supported_config)
    except Exception as ex:
        print(f'Unable to build pipeline: {ex}')
        traceback.print_exception(ex)
        print('Restarting loop...')
        continue

    # Step 4: Start RTSP Server
    print('4) Starting RTSP Server...')
    rtsp_server = RTSPServer(supported_config)

    # Step 5: Starting vision data loop
    print('5) Starting vision data loop...')
    try:
        print('5a) Connecting to device...')
        with dai.Device(vision_pipeline) as device:
            # Output queue(s) will be used to get the encoded data from the output defined above
            outputQueueNames = device.getOutputQueueNames()

            print('5b) Preparing output queues...')
            OUTPUT_QUEUES = {
                queueName: device.getOutputQueue(
                    name=queueName,
                    maxSize=30, # type: ignore
                    blocking=True, # type: ignore
                ) for queueName in outputQueueNames if AllCameraStreams.is_supported(queueName)
            }

            print("RTSP stream available at rtsp://<server-ip>:8554/preview")
            print('Starting streaming of video data...')

            while True:
                for queue_id, outputQueue in OUTPUT_QUEUES.items():
                    if supported_config.check(queue_id) and outputQueue.has():
                        frame_data = outputQueue.get().getData()
                        rtsp_server.send_data(queue_id, frame_data)
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
