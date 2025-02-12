"""
Explanation (paraphrased from ChatGPT as of 02/12/2025):
1. `shmsrc is-live=true socket-path={} do-timestamp=true`
    - `shmsrc`: A shared memory source that reads data from a shared memory segment (produced by `shmsink`).
    - `is-live=true`: Indicates that the source is live (e.g., real-time video stream).
    - `socket-path={}`: Specifies the UNIX socket path from which shared memory data is read. `{}` is likely a placeholder.
    - `do-timestamp=true`: Assigns timestamps to incoming buffers to maintain synchronization.
2. `application/x-rtp,media=video,clock-rate=90000,encoding-name=H264`
    - Caps (`application/x-rtp`): Defines the expected input format.
    - `media=video`: Specifies that the data is video.
    - `clock-rate=90000`: Sets the RTP clock rate to 90 kHz, which is standard for video streams.
    - `encoding-name=H264`: Specifies that the data is H.264-encoded video.
3. `rtph264depay`
    - `rtph264depay`: Extracts raw H.264 video frames from RTP packets (depacketization).
4. `h264parse config-interval=1`
    - `h264parse`: Parses the raw H.264 stream to ensure proper format for further processing.
    - `config-interval=1`: Ensures that the SPS/PPS (Sequence Parameter Set/Picture Parameter Set) is inserted every second.
5. `queue leaky=upstream`
    - `queue`: Buffers data to help with asynchronous flow.
    - `leaky=upstream`: If the queue is full, it will drop the newest buffers (rather than blocking) to prevent latency buildup in real-time streaming.
6. `rtph264pay name=pay0 pt=96`
    - `rtph264pay`: Repackages the H.264 stream into RTP packets for further streaming.
    - `name=pay0`: Assigns the name `pay0` to the RTP payloader, making it easier to reference.
    - `pt=96`: Specifies the RTP payload type (PT). PT 96 is commonly used for H.264 in RTP streams.
"""
RECEIVE_VIDEO_DATA_PIPELINE = "\
shmsrc is-live=true socket-path={} do-timestamp=true ! \
application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! \
rtph264depay ! \
h264parse config-interval=1 ! \
queue leaky=upstream ! \
rtph264pay name=pay0 pt=96"


"""
Explanation (paraphrased from ChatGPT as of 02/12/2025):
1. `appsrc name=source do-timestamp=true is-live=true format=time`
    - `appsrc`: Create a pipeline that allows applications to push data into manually
    - `name=source`: Names the pipeline for programatic access
    - `do-timestamp=true`: Ensure that timestamps are added to buffers if not present
    - `is-live=true`: Flags the source as live. Internally, it only pushes data into buffers when in PLAYING state
    - `format=time`: Specifies that timestamps should be in absolute time format
2. `h264parse`
    - `h264parse`: Specifies that any incoming data should be parsed as H.264 video data
3. `queue leaky=downstream`
    - `queue`: Creates a buffering element to store video frames for async data flow
    - `leaky=downstream`: If the queue is full, drop older buffer frames instead of blocking the pipeline
4. `rtph264pay config-interval=1 pt=96`
    - `rtph264pay`: Converts raw H.264 video into RTP packets for network streaming.
    - `config-interval=1`: Ensures that the SPS/PPS (Sequence Parameter Set/Picture Parameter Set) is sent every second, for telling clients how to handle the incoming video data
    - `pt=96`: Specifies the payload type (PT) for RTP. PT 96 is typically used for dynamic RTP payloads, although unsure about why specifically 96
5. `shmsink wait-for-connection=false sync=true socket-path={}`
    - `shmsink`: A video data "sink" element defined using shared memory. This allows writing the data to a client like Cockpit
    - `wait-for-connection=false`: Start producing data even if no consumer (i.e. Cockpit) is connected
    - `sync=true`: Synchronize video data frames based on timestamps, ensuring real-time playback
    - `socket-path={}`: Specifies the UNIX socket path used for shared memory communication, either "rgb" or "depth"
"""
UPLOAD_VIDEO_DATA_PIPELINE = "\
appsrc name=source do-timestamp=true is-live=true format=time ! \
h264parse ! \
queue leaky=downstream ! \
rtph264pay config-interval=1 pt=96 ! \
shmsink wait-for-connection=false sync=true socket-path={}"
