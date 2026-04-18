"""Modulo de camara: captura y analisis de video en tiempo real."""
import asyncio
import base64
import cv2
import numpy as np
from typing import Optional, AsyncGenerator
from config import settings


class CameraManager:
    def __init__(self):
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_active = False
        self._frame: Optional[np.ndarray] = None

    def start(self, index: int = None) -> bool:
        if index is None:
            index = settings.CAMERA_INDEX
        self.cap = cv2.VideoCapture(index)
        if self.cap.isOpened():
            self.is_active = True
            return True
        return False

    def stop(self):
        if self.cap:
            self.cap.release()
        self.is_active = False
        self._frame = None

    def capture_frame(self) -> Optional[np.ndarray]:
        if not self.cap or not self.is_active:
            return None
        ret, frame = self.cap.read()
        if ret:
            self._frame = frame
            return frame
        return None

    def frame_to_base64(self, frame: Optional[np.ndarray] = None) -> Optional[str]:
        if frame is None:
            frame = self._frame
        if frame is None:
            return None
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buffer).decode("utf-8")

    def frame_to_jpeg_bytes(self, frame: Optional[np.ndarray] = None) -> Optional[bytes]:
        if frame is None:
            frame = self._frame
        if frame is None:
            return None
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buffer.tobytes()

    async def stream_frames(self) -> AsyncGenerator[bytes, None]:
        """Yield JPEG frames for MJPEG streaming."""
        while self.is_active:
            frame = self.capture_frame()
            if frame is not None:
                jpeg = self.frame_to_jpeg_bytes(frame)
                if jpeg:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                    )
            await asyncio.sleep(1 / 30)  # ~30 FPS


camera = CameraManager()
