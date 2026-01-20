"""
view_rgb.py
========================

Phase: 1 – Basic RGB Visualization

Description:
------------
This script connects to an OAK-D / OAK-D Pro camera and displays
the RGB camera stream in a window using OpenCV.

Scope (what this script DOES):
------------------------------
- Initialize a minimal DepthAI pipeline
- Capture RGB frames from the OAK camera
- Display the frames on screen in real time

Out of scope (what this script DOES NOT do):
-------------------------------------------
- Save images
- Record video
- Stream video over network
- Use depth, IR or AI
- Interact with Raspberry Pi, GCS or MAVLink

This script is intentionally minimal and serves as the foundation
for later phases of the project.
"""

import depthai as dai
import cv2


def main():
    """
    Main execution function.
    Creates the pipeline, starts the device and displays RGB frames.
    """

    # ----------------------------
    # Create DepthAI pipeline
    # ----------------------------
    pipeline = dai.Pipeline()

    # RGB camera node
    cam_rgb = pipeline.create(dai.node.ColorCamera)
    cam_rgb.setPreviewSize(640, 480)
    cam_rgb.setInterleaved(False)
    cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)

    # Output link
    xout_rgb = pipeline.create(dai.node.XLinkOut)
    xout_rgb.setStreamName("rgb")

    cam_rgb.preview.link(xout_rgb.input)

    # ----------------------------
    # Start the device
    # ----------------------------
    with dai.Device(pipeline) as device:
        rgb_queue = device.getOutputQueue(
            name="rgb",
            maxSize=4,
            blocking=False
        )

        print("OAK-D RGB stream started. Press 'q' to quit.")

        # ----------------------------
        # Main loop
        # ----------------------------
        while True:
            in_rgb = rgb_queue.get()
            frame = in_rgb.getCvFrame()

            cv2.imshow("OAK-D RGB", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
