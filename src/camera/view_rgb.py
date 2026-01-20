import depthai as dai
import cv2
import os
from datetime import datetime

def main():
    """
    Main execution function.
    Creates the pipeline, starts the device and displays RGB frames.
    Also captures images when the 'c' key is pressed and records video when 'r' is pressed.
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

        print("OAK-D RGB stream started. Press 'q' to quit, 'c' to capture image, 'r' to record video.")

        # Initialize video writer (for recording video)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')  # Codec for .avi format
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Ensure the 'data/videos' directory exists
        if not os.path.exists('data/videos'):
            os.makedirs('data/videos')

        video_filename = f"data/videos/{timestamp}_video.avi"  # Video filename with timestamp
        out = None  # Start with no video writer

        # ----------------------------
        # Main loop
        # ----------------------------
        while True:
            in_rgb = rgb_queue.get()
            frame = in_rgb.getCvFrame()

            cv2.imshow("OAK-D RGB", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break
            if key == ord('c'):  # Press 'c' to capture image
                capture_image(frame)
            if key == ord('r'):  # Press 'r' to start/stop recording video
                if out is None:  # If not recording, start recording
                    out = cv2.VideoWriter(video_filename, fourcc, 30.0, (640, 480))
                    print(f"Recording started: {video_filename}")
                else:  # If recording, stop recording
                    out.release()
                    print(f"Video saved as {video_filename}")
                    out = None  # Reset video writer

            # If recording, write the current frame to the video file
            if out is not None:
                out.write(frame)

        # Release the video writer object when done
        if out is not None:
            out.release()

    cv2.destroyAllWindows()


def capture_image(frame):
    """
    Function to capture and save an image with a timestamp.
    """
    # Create the images directory if it doesn't exist
    if not os.path.exists('data/images'):
        os.makedirs('data/images')

    # Generate a filename based on the current timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"data/images/{timestamp}.jpg"

    # Save the frame as an image
    cv2.imwrite(filename, frame)
    print(f"Image captured and saved as {filename}")


if __name__ == "__main__":
    main()
