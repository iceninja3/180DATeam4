"""Display a hand's live roll while its fingers point at the camera.

Angle convention (in the displayed camera image):

* pointer/index finger above the pinky: 0 degrees
* clockwise rotation: positive
* counterclockwise rotation: negative

MediaPipe's 3-D world landmarks are used to check that the four fingers are
straight and aimed toward the camera.  This is still a monocular estimate, so
the pointing threshold can be adjusted from the command line when needed.
"""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path
from typing import Sequence

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision


DEFAULT_MODEL_PATH = Path(__file__).resolve().with_name("hand_landmarker.task")

WRIST = 0
INDEX_MCP = 5
MIDDLE_MCP = 9
RING_MCP = 13
PINKY_MCP = 17

FINGER_CHAINS = (
    (5, 6, 7, 8),
    (9, 10, 11, 12),
    (13, 14, 15, 16),
    (17, 18, 19, 20),
)

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)


class CircularSmoother:
    """Exponential smoothing that behaves correctly around +/-180 degrees."""

    def __init__(self, alpha: float) -> None:
        self.alpha = alpha
        self._x: float | None = None
        self._y: float | None = None

    def update(self, angle_degrees: float) -> float:
        angle_radians = math.radians(angle_degrees)
        x = math.cos(angle_radians)
        y = math.sin(angle_radians)
        if self._x is None or self._y is None:
            self._x, self._y = x, y
        else:
            self._x = (1.0 - self.alpha) * self._x + self.alpha * x
            self._y = (1.0 - self.alpha) * self._y + self.alpha * y
        return math.degrees(math.atan2(self._y, self._x))

    def reset(self) -> None:
        self._x = None
        self._y = None


def _xyz(landmark) -> np.ndarray:
    return np.array((landmark.x, landmark.y, landmark.z), dtype=np.float64)


def _joint_angle(a: np.ndarray, joint: np.ndarray, c: np.ndarray) -> float:
    """Return the 3-D angle A-joint-C in degrees."""
    first = a - joint
    second = c - joint
    denominator = np.linalg.norm(first) * np.linalg.norm(second)
    if denominator < 1e-9:
        return 0.0
    cosine = float(np.clip(np.dot(first, second) / denominator, -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def roll_angle_degrees(landmarks: Sequence, frame_width: int, frame_height: int) -> float:
    """Return signed roll in displayed-image coordinates.

    The vector from the pinky knuckle to the pointer/index knuckle defines the
    roll axis.  atan2(dx, -dy) makes image-up 0 and clockwise positive. Pixel
    scaling is applied because MediaPipe x/y coordinates are normalized
    independently by image width and height.
    """
    dx = (landmarks[INDEX_MCP].x - landmarks[PINKY_MCP].x) * frame_width
    dy = (landmarks[INDEX_MCP].y - landmarks[PINKY_MCP].y) * frame_height
    return math.degrees(math.atan2(dx, -dy))


def finger_pose_metrics(landmarks: Sequence) -> tuple[float, float]:
    """Return (camera-pointing error, minimum straightness), in degrees.

    MediaPipe uses decreasing z for motion toward the camera, so the desired
    finger direction is (0, 0, -1).  All four non-thumb fingers contribute to
    the direction estimate.  Straightness is the smallest PIP/DIP joint angle,
    which prevents a curled fist from being accepted as camera-pointing.
    """
    directions = []
    joint_angles = []

    for mcp_id, pip_id, dip_id, tip_id in FINGER_CHAINS:
        mcp = _xyz(landmarks[mcp_id])
        pip = _xyz(landmarks[pip_id])
        dip = _xyz(landmarks[dip_id])
        tip = _xyz(landmarks[tip_id])

        direction = tip - mcp
        magnitude = np.linalg.norm(direction)
        if magnitude > 1e-9:
            directions.append(direction / magnitude)

        joint_angles.append(_joint_angle(mcp, pip, dip))
        joint_angles.append(_joint_angle(pip, dip, tip))

    if not directions:
        return 180.0, 0.0

    mean_direction = np.mean(directions, axis=0)
    mean_magnitude = np.linalg.norm(mean_direction)
    if mean_magnitude < 1e-9:
        return 180.0, min(joint_angles, default=0.0)

    mean_direction /= mean_magnitude
    # Dotting with camera-forward (0, 0, -1) is equivalent to -z.
    pointing_cosine = float(np.clip(-mean_direction[2], -1.0, 1.0))
    pointing_error = math.degrees(math.acos(pointing_cosine))
    return pointing_error, min(joint_angles, default=0.0)


def _pixel(landmark, width: int, height: int) -> tuple[int, int]:
    return int(landmark.x * width), int(landmark.y * height)


def draw_hand(frame: np.ndarray, landmarks: Sequence) -> None:
    """Draw the hand skeleton and the pinky-to-pointer roll axis."""
    height, width = frame.shape[:2]
    for start, end in HAND_CONNECTIONS:
        cv2.line(
            frame,
            _pixel(landmarks[start], width, height),
            _pixel(landmarks[end], width, height),
            (190, 190, 190),
            2,
            cv2.LINE_AA,
        )

    for index, landmark in enumerate(landmarks):
        color = (255, 255, 255)
        if index in FINGER_CHAINS[0]:
            color = (0, 255, 255)
        elif index == PINKY_MCP:
            color = (255, 80, 255)
        cv2.circle(frame, _pixel(landmark, width, height), 4, color, -1, cv2.LINE_AA)

    pinky_point = _pixel(landmarks[PINKY_MCP], width, height)
    pointer_point = _pixel(landmarks[INDEX_MCP], width, height)
    cv2.arrowedLine(
        frame,
        pinky_point,
        pointer_point,
        (0, 255, 255),
        4,
        cv2.LINE_AA,
        tipLength=0.18,
    )
    cv2.putText(
        frame,
        "POINTER",
        (pointer_point[0] + 8, pointer_point[1] - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 255),
        1,
        cv2.LINE_AA,
    )


def _draw_text(
    frame: np.ndarray,
    text: str,
    y: int,
    color: tuple[int, int, int],
    scale: float = 0.72,
) -> None:
    cv2.putText(
        frame,
        text,
        (18, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        2,
        cv2.LINE_AA,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show live hand roll while checking that fingers point at the camera."
    )
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index (default: 0)")
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Path to hand_landmarker.task",
    )
    parser.add_argument(
        "--max-pointing-angle",
        type=float,
        default=35.0,
        help="Largest accepted finger-to-camera error in degrees (default: 35)",
    )
    parser.add_argument(
        "--min-straightness",
        type=float,
        default=135.0,
        help="Smallest accepted finger joint angle in degrees (default: 135)",
    )
    parser.add_argument(
        "--smoothing",
        type=float,
        default=0.25,
        help="Roll smoothing from 0 (slow) to 1 (none); default: 0.25",
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="Do not mirror the camera image",
    )
    args = parser.parse_args()

    if not 0.0 < args.smoothing <= 1.0:
        parser.error("--smoothing must be greater than 0 and at most 1")
    if not 0.0 <= args.max_pointing_angle <= 180.0:
        parser.error("--max-pointing-angle must be between 0 and 180")
    if not 0.0 <= args.min_straightness <= 180.0:
        parser.error("--min-straightness must be between 0 and 180")
    return args


def main() -> None:
    args = parse_args()
    model_path = args.model.expanduser().resolve()
    if not model_path.is_file():
        raise SystemExit(
            f"MediaPipe model not found: {model_path}\n"
            "Place hand_landmarker.task beside this script or pass --model PATH."
        )

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    capture = cv2.VideoCapture(args.camera)
    if not capture.isOpened():
        raise SystemExit(f"Could not open camera {args.camera}.")

    smoother = CircularSmoother(args.smoothing)
    previous_timestamp_ms = -1
    window_name = "Hand Orientation"

    try:
        with vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame = capture.read()
                if not ok:
                    print("Camera frame could not be read.")
                    break

                if not args.no_mirror:
                    frame = cv2.flip(frame, 1)

                height, width = frame.shape[:2]
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

                timestamp_ms = time.monotonic_ns() // 1_000_000
                timestamp_ms = max(timestamp_ms, previous_timestamp_ms + 1)
                previous_timestamp_ms = timestamp_ms
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                # Solid background keeps the measurements readable on any scene.
                cv2.rectangle(frame, (0, 0), (width, 148), (25, 25, 25), -1)

                if result.hand_landmarks:
                    image_landmarks = result.hand_landmarks[0]
                    pose_landmarks = (
                        result.hand_world_landmarks[0]
                        if result.hand_world_landmarks
                        else image_landmarks
                    )

                    raw_roll = roll_angle_degrees(image_landmarks, width, height)
                    roll = smoother.update(raw_roll)
                    pointing_error, straightness = finger_pose_metrics(pose_landmarks)
                    points_at_camera = pointing_error <= args.max_pointing_angle
                    fingers_straight = straightness >= args.min_straightness
                    pose_ok = points_at_camera and fingers_straight

                    draw_hand(frame, image_landmarks)

                    reading_color = (80, 255, 80) if pose_ok else (0, 215, 255)
                    _draw_text(frame, f"ROLL: {roll:+.0f} deg   (CW + / CCW -)", 32, reading_color, 0.82)
                    _draw_text(
                        frame,
                        f"Finger direction error: {pointing_error:.0f} deg / {args.max_pointing_angle:.0f} max",
                        65,
                        (225, 225, 225),
                        0.62,
                    )
                    _draw_text(
                        frame,
                        f"Minimum finger straightness: {straightness:.0f} deg / {args.min_straightness:.0f} min",
                        94,
                        (225, 225, 225),
                        0.62,
                    )

                    if pose_ok:
                        status = "POSE OK"
                        status_color = (80, 255, 80)
                    elif not fingers_straight:
                        status = "STRAIGHTEN ALL FOUR FINGERS"
                        status_color = (0, 165, 255)
                    else:
                        status = "POINT FINGERS DIRECTLY AT CAMERA"
                        status_color = (0, 80, 255)
                    _draw_text(frame, status, 128, status_color, 0.72)
                else:
                    smoother.reset()
                    _draw_text(frame, "NO HAND DETECTED", 42, (0, 80, 255), 0.85)
                    _draw_text(frame, "Hold one straight hand in front of the camera", 82, (230, 230, 230), 0.65)

                cv2.putText(
                    frame,
                    "Press Q or Esc to quit",
                    (18, height - 18),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (230, 230, 230),
                    1,
                    cv2.LINE_AA,
                )
                cv2.imshow(window_name, frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
