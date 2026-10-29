import cv2
import numpy as np
import mediapipe as mp

try:
    _mp_pose = mp.solutions.pose
except AttributeError:
    # Some MediaPipe distributions expose solutions under mediapipe.python.
    from mediapipe.python.solutions import pose as _mp_pose

def extract_pose(path, progress_cb=None):
    """Returns xy (T,33,2) in pixels, vis (T,33), fps, (W,H)."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    pose = _mp_pose.Pose(
        model_complexity=2, smooth_landmarks=True,
        min_detection_confidence=0.5, min_tracking_confidence=0.5)

    xy = np.full((n, 33, 2), np.nan)
    vis = np.zeros((n, 33))
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok or i >= n:
            break
        res = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if res.pose_landmarks:
            for j, lm in enumerate(res.pose_landmarks.landmark):
                xy[i, j] = (lm.x * W, lm.y * H)
                vis[i, j] = lm.visibility
        i += 1
        if progress_cb and i % 10 == 0:
            progress_cb(i / n)
    cap.release()
    pose.close()
    return xy[:i], vis[:i], fps, (W, H)