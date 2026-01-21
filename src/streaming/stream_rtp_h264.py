"""
Phase 4 — RTP Streaming (H.264) using OAK internal encoder + GStreamer RTP payloader.

What it does:
- Uses OAK-D / OAK-D Pro internal H.264 encoder (DepthAI VideoEncoder)
- Launches a GStreamer pipeline that takes H.264 bytestream from stdin (fdsrc)
  -> h264parse -> rtph264pay -> udpsink (RTP over UDP)
- Sends RTP stream to a PC (QGroundControl or any RTP receiver)

Why this approach:
- Most CPU-efficient on Raspberry Pi (encoding happens on the OAK device)
- GStreamer only packetizes (RTP) and sends

Requirements on Raspberry Pi:
- depthai, opencv-python (optional preview)
- GStreamer: gstreamer1.0-tools + plugins including h264parse, rtph264pay

Test receiver on PC (GStreamer):
gst-launch-1.0 -v udpsrc port=5004 caps="application/x-rtp,media=video,encoding-name=H264,payload=96" ! rtph264depay ! avdec_h264 ! videoconvert ! autovideosink sync=false
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

import depthai as dai


def project_root() -> Path:
    # .../src/streaming/stream_rtp_h264.py -> repo root is 3 levels up
    return Path(__file__).resolve().parents[2]


def build_pipeline(width: int, height: int, fps: int, bitrate_kbps: int) -> dai.Pipeline:
    pipeline = dai.Pipeline()

    cam = pipeline.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam.setVideoSize(width, height)
    cam.setFps(fps)
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)

    # Hardware H.264 encoder on device
    enc = pipeline.create(dai.node.VideoEncoder)
    enc.setDefaultProfilePreset(
        fps,
        dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    enc.setBitrateKbps(bitrate_kbps)
    # Send SPS/PPS periodically so receivers can join mid-stream
    enc.setKeyframeFrequency(fps)  # ~1 keyframe/sec

    cam.video.link(enc.input)

    xout = pipeline.create(dai.node.XLinkOut)
    xout.setStreamName("h264")
    enc.bitstream.link(xout.input)

    return pipeline


def launch_gstreamer_rtp(host: str, port: int, payload_type: int) -> subprocess.Popen:
    """
    GStreamer pipeline:
      fdsrc fd=0 -> h264parse -> rtph264pay -> udpsink host=... port=...
    Reads raw H264 bytestream from stdin (fd=0).
    """
    gst_cmd = [
        "gst-launch-1.0",
        "-q",
        "fdsrc", "fd=0",
        "!", "h264parse", "config-interval=1",
        "!", "rtph264pay", f"pt={payload_type}",
        "!", "udpsink", f"host={host}", f"port={port}", "sync=false", "async=false",
    ]

    # stdin=PIPE so we can write H264 bytes into it
    return subprocess.Popen(
        gst_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,  # keep for debugging if it fails
        bufsize=0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="OAK H.264 RTP streaming via GStreamer")
    parser.add_argument("--host", required=True, help="Destination PC IP (receiver) (e.g. 192.168.1.50)")
    parser.add_argument("--port", type=int, default=5004, help="UDP port for RTP stream (default: 5004)")
    parser.add_argument("--width", type=int, default=1280, help="Video width (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Video height (default: 720)")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second (default: 30)")
    parser.add_argument("--bitrate-kbps", type=int, default=4000, help="H.264 bitrate kbps (default: 4000)")
    parser.add_argument("--payload-type", type=int, default=96, help="RTP payload type (default: 96)")
    args = parser.parse_args()

    # Safety: make sure gst-launch exists
    if not shutil_which("gst-launch-1.0"):
        print("ERROR: gst-launch-1.0 not found. Install GStreamer on the Raspberry Pi.", file=sys.stderr)
        return 2

    pipeline = build_pipeline(args.width, args.height, args.fps, args.bitrate_kbps)

    gst = launch_gstreamer_rtp(args.host, args.port, args.payload_type)
    if gst.stdin is None:
        print("ERROR: Failed to open GStreamer stdin.", file=sys.stderr)
        return 3

    # Graceful shutdown
    stop = {"flag": False}

    def handle_sigint(_sig, _frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    try:
        with dai.Device(pipeline) as device:
            q = device.getOutputQueue(name="h264", maxSize=30, blocking=True)
            print(f"[OK] Streaming RTP H.264 to {args.host}:{args.port}  ({args.width}x{args.height}@{args.fps}, {args.bitrate_kbps} kbps)")
            print("[INFO] Ctrl+C to stop.")

            while not stop["flag"]:
                pkt = q.get()
                data = pkt.getData()
                # Write raw H.264 bytes into GStreamer pipeline
                try:
                    gst.stdin.write(data)
                except BrokenPipeError:
                    err = (gst.stderr.read().decode(errors="ignore") if gst.stderr else "")
                    print("ERROR: GStreamer pipeline terminated (BrokenPipe).", file=sys.stderr)
                    if err:
                        print("GStreamer stderr:\n" + err, file=sys.stderr)
                    return 4

    finally:
        try:
            if gst.stdin:
                gst.stdin.close()
        except Exception:
            pass
        try:
            gst.terminate()
        except Exception:
            pass

    print("[OK] Stopped.")
    return 0


def shutil_which(cmd: str) -> str | None:
    # tiny local replacement to avoid importing shutil if you prefer minimal imports
    paths = os.environ.get("PATH", "").split(os.pathsep)
    for p in paths:
        full = Path(p) / cmd
        if full.exists() and os.access(full, os.X_OK):
            return str(full)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
