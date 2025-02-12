#!/usr/bin/env python3

import os
import time
import threading


import depthai as dai

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib, GstRtsp

from register_stream import check_streams
from video_pipeline import build_pipeline

socket_rgb_path = "/tmp/socketrgb"
socket_depth_path = "/tmp/socketdepth"

receive_pipeline = "shmsrc is-live=true socket-path={} do-timestamp=true ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! h264parse config-interval=1 ! queue leaky=upstream ! rtph264pay name=pay0 pt=96"
app_pipeline = "appsrc name=source do-timestamp=true is-live=true format=time ! h264parse ! queue leaky=downstream ! rtph264pay config-interval=1 pt=96 ! shmsink wait-for-connection=false sync=true socket-path={}"


class RtspSystem(GstRtspServer.RTSPMediaFactory):
    def __init__(self, **properties):
        super(RtspSystem, self).__init__(**properties)

    def start(self):
        t = threading.Thread(target=self._thread_rtsp)
        t.start()

    def _thread_rtsp(self):
        loop = GLib.MainLoop()
        loop.run()


    def do_create_element(self, url):
        name = url.abspath.split('/')[-1]
        if name == 'rgb':
            return Gst.parse_launch(receive_pipeline.format(socket_rgb_path))
        elif name == 'depth':
            return Gst.parse_launch(receive_pipeline.format(socket_depth_path))
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

        for rtsp in [(self.rgb_rtsp, 'rgb', socket_rgb_path), (self.depth_rtsp, 'depth', socket_depth_path)]:
            rtsp, name, socket = rtsp
            rtsp.set_shared(True)
            rtsp.start()
            self.get_mount_points().add_factory(f"/{name}", rtsp)
            self.app_pipeline[name] = self.start_app_pipeline(socket)
            self.appsrc[name] = self.app_pipeline[name].get_child_by_name('source')
        self.attach(None)

        # MCM thread
        t2 = threading.Thread(target=check_streams)
        t2.start()
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
        launch_str = app_pipeline.format(file)
        print(launch_str)
        pipeline = Gst.parse_launch(launch_str)
        pipeline.set_state(Gst.State.PLAYING)
        print("playing")
        return pipeline


# Clear any existing sockets before creating new ones
for socket in [socket_rgb_path, socket_depth_path]:
    if os.path.exists(socket):
        os.remove(socket)


pipeline = build_pipeline()

# Start the RTSP server
server = RTSPServer()

while True:
    try:
        with dai.Device(pipeline) as device:
            print('Connected to device!')

            # Output queue will be used to get the encoded data from the output defined above
            rgb = device.getOutputQueue(name='rgb', maxSize=30, blocking=True)
            depth = device.getOutputQueue(name='depth', maxSize=30, blocking=True)

            print("RTSP stream available at rtsp://<server-ip>:8554/preview")
            print("Press Ctrl+C to stop encoding...")


            print('Starting streaming of video data...')
            while True:
                rgbData = rgb.get().getData()
                depthData = depth.get().getData()

                server.send_data('rgb', rgbData)
                server.send_data('depth', depthData)
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

        print('Restarting stream after 5 seconds...')
        time.sleep(5)
