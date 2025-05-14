from dataclasses import dataclass


@dataclass
class SupportedConfig:
    rgb: bool
    mono_left: bool
    mono_right: bool


    @property
    def depth(self) -> bool:
        return self.mono_left and self.mono_right


    def check(self, key) -> bool:
        return getattr(self, key)


@dataclass
class CameraStream:
    id: str
    name: str
    endpoint: str
    socket_path: str


@dataclass
class AllCameraStreams:
    rgb = CameraStream(
        id = 'rgb',
        name = 'Oak-D RGB',
        endpoint = 'rgb',
        socket_path = '/tmp/socketrgb',
    )

    mono_left = CameraStream(
        id = 'mono_left',
        name = 'Oak-D Mono Left',
        endpoint = 'mono_left',
        socket_path = '/tmp/socketmonoleft',
    )

    mono_right = CameraStream(
        id = 'mono_right',
        name = 'Oak-D Mono Right',
        endpoint = 'mono_right',
        socket_path = '/tmp/socketmonoright',
    )

    depth = CameraStream(
        id = 'depth',
        name = 'Oak-D Stereo Disparity',
        endpoint = 'depth',
        socket_path = '/tmp/socketdepth',
    )


    @staticmethod
    def is_supported(stream_id: str) -> bool:
        return hasattr(AllCameraStreams, stream_id)


    @staticmethod
    def get(stream_id: str) -> CameraStream:
        return getattr(AllCameraStreams, stream_id)


    @staticmethod
    def all_streams() -> list[CameraStream]:
        return [
            AllCameraStreams.rgb,
            AllCameraStreams.mono_left,
            AllCameraStreams.mono_right,
            AllCameraStreams.depth,
        ]
