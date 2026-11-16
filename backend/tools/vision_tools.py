"""Vision tools.

OpenCV / face_recognition are imported lazily inside the tool so that the rest
of the application (and the test suite) can run without a camera or these heavy
native dependencies installed.
"""


def face_detection_tool():
    """Check whether a human face is present in the camera view."""
    try:
        import cv2
        from cvzone.FaceDetectionModule import FaceDetector
    except ImportError as exc:
        return {"message": "Vision dependencies are not installed", "error": str(exc)}

    face_detector = FaceDetector()
    camera = cv2.VideoCapture(0)
    try:
        if not camera.isOpened():
            return {"message": "Camera could not be opened"}
        ret, frame = camera.read()
        if not ret:
            return {"message": "Could not read a frame from the camera"}
        frame, faces = face_detector.findFaces(img=frame)
        if len(faces) > 0:
            return {
                "message": "Face detected in camera view",
                "faces_count": len(faces),
                "faces_coordinates": faces,
            }
        return {"message": "No face detected in camera view"}
    except Exception as exc:
        return {"message": "Vision tool error", "error": str(exc)}
    finally:
        camera.release()


VISION_TOOLS = [face_detection_tool]
