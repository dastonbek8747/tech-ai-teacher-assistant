import pickle
import time
import cv2
import face_recognition
from cvzone.FaceDetectionModule import FaceDetector
import face_recognition

face_detector = FaceDetector()


def face_detection_tool():
    """
    A function that checks whether a human face is present in the camera view
    """
    kamera = cv2.VideoCapture(0)
    try:
        if not kamera.isOpened():
            return {"message": "Kamera ochilmadi"}
        else:
            ret, frame = kamera.read()
            if not ret:
                return {"message": "Kameradan kadr olishda xatolik !"}
            else:
                frame, face = face_detector.findFaces(img=frame)
                if len(face) > 0:
                    return {"message": "Kamerada yuz aniqlandi !", "yuzlar_soni": len(face),
                            "yuzlar_kordinatalari": face}
                else:
                    return {"message": "Kamerada yuz aniqlanmadi !"}
    except Exception as e:
        return {"message": "Dasturda xatolik", "EROR": e}
    finally:
        kamera.release()


# def register_user_face_id()


VISION_TOOLS = [face_detection_tool]
