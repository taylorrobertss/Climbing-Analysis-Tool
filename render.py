import cv2
import numpy as np
import imageio_ffmpeg
from metrics import clean, com, LIMBS, LS, RS, LE, RE, LW, RW, LH, RH, LK, RK, LA, RA

# (joint a, joint b, side)  side: 0 = centre, 1 = left, 2 = right
BONES = [(LS, RS, 0), (LH, RH, 0), (LS, LH, 1), (RS, RH, 2),
         (LS, LE, 1), (LE, LW, 1), (RS, RE, 2), (RE, RW, 2),
         (LH, LK, 1), (LK, LA, 1), (RH, RK, 2), (RK, RA, 2)]
SIDE_COL = {0: (220, 220, 220), 1: (255, 170, 60), 2: (60, 200, 255)}  # BGR
GREEN, RED, YELLOW, WHITE = (80, 220, 80), (60, 60, 240), (0, 220, 255), (255, 255, 255)


def _pt(p):
    return None if np.isnan(p).any() else (int(p[0]), int(p[1]))


def _label(img, text, org, scale, color=WHITE, bg=(0, 0, 0)):
    font = cv2.FONT_HERSHEY_SIMPLEX
    th = max(1, int(round(scale * 2)))
    (w, h), base = cv2.getTextSize(text, font, scale, th)
    x, y = org
    cv2.rectangle(img, (x - 3, y - h - 4), (x + w + 3, y + base), bg, -1)
    cv2.putText(img, text, (x, y), font, scale, color, th, cv2.LINE_AA)
    return h + base + 8


def render_overlay(src, out, xy_raw, vis, fps, metrics, series, v_move=0.6,
                   show_trail=True, show_angles=True, show_flags=True, max_h=720,
                   progress_cb=None):
    xy = clean(xy_raw, vis, fps)          # same smoothed data the metrics used
    c_px = com(xy)                        # CoM in pixels (weights sum to 1, so linear)
    T = len(xy)

    # Per-frame flags from the stop analysis
    in_stop = np.zeros(T, bool)
    bent_stop = np.zeros(T, bool)
    for s in metrics["stops"]:
        a, b = int(round(s["start"] * fps)), int(round(s["end"] * fps))
        in_stop[a:b] = True
        if s["mean_elbow"] == s["mean_elbow"] and s["mean_elbow"] < 130:
            bent_stop[a:b] = True
    key_vis = vis[:, [LS, RS, LH, RH, LW, RW, LA, RA]].mean(axis=1)

    cap = cv2.VideoCapture(src)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    sc = max(H / 720, 0.6)                # scale drawing to resolution
    trail_n = int(2 * fps)

 # Output size (even numbers required by H.264)
    k = min(1.0, max_h / H) if max_h else 1.0
    ow, oh = int(W * k) // 2 * 2, int(H * k) // 2 * 2

    writer = imageio_ffmpeg.write_frames(
        out, (ow, oh), fps=fps, pix_fmt_in="bgr24", pix_fmt_out="yuv420p",
        codec="libx264", macro_block_size=2,
        output_params=["-crf", "26", "-preset", "veryfast", "-movflags", "+faststart"])
    writer.send(None)

    for i in range(T):
        ok, frame = cap.read()
        if not ok:
            break

        # Bones
        for a, b, side in BONES:
            pa, pb = _pt(xy[i, a]), _pt(xy[i, b])
            if pa and pb:
                cv2.line(frame, pa, pb, SIDE_COL[side], max(2, int(3 * sc)), cv2.LINE_AA)

        # Joints
        for j in (LS, RS, LE, RE, LH, RH, LK, RK):
            p = _pt(xy[i, j])
            if p:
                cv2.circle(frame, p, max(3, int(4 * sc)), WHITE, -1, cv2.LINE_AA)

        # Limb end points: green = still, red = moving
        for name, idx in LIMBS.items():
            p = _pt(xy[i, idx])
            if p:
                moving = series["limb_speed"][name][i] > v_move
                cv2.circle(frame, p, int(9 * sc), RED if moving else GREEN, -1, cv2.LINE_AA)
                cv2.circle(frame, p, int(9 * sc), (0, 0, 0), 1, cv2.LINE_AA)

        # Elbow angles
        if show_angles:
            for side, j in (("L", LE), ("R", RE)):
                p = _pt(xy[i, j])
                if p:
                    ang = series["elbow"][side][i]
                    col = GREEN if ang >= 150 else RED if ang < 130 else YELLOW
                    _label(frame, f"{ang:.0f}", (p[0] + int(8 * sc), p[1] - int(8 * sc)),
                           0.5 * sc, col)

        # CoM trail + dot
        if show_trail:
            s0 = max(0, i - trail_n)
            for k in range(s0 + 1, i + 1):
                pa, pb = _pt(c_px[k - 1]), _pt(c_px[k])
                if pa and pb:
                    f = (k - s0) / max(i - s0, 1)
                    col = (int(255 * f), int(120 * f), int(255 * f))
                    cv2.line(frame, pa, pb, col, max(2, int(3 * sc)), cv2.LINE_AA)
        p = _pt(c_px[i])
        if p:
            cv2.circle(frame, p, int(11 * sc), (255, 0, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, p, int(11 * sc), WHITE, 2, cv2.LINE_AA)

        # HUD
        y = int(28 * sc)
        y += _label(frame, f"t = {i / fps:5.2f}s   CoM {series['speed'][i]:.2f} TL/s",
                    (10, y), 0.6 * sc)
        if show_flags:
            if key_vis[i] < 0.5:
                y += _label(frame, "LOW TRACKING CONFIDENCE", (10, y), 0.6 * sc, WHITE, (0, 0, 160))
            if bent_stop[i]:
                y += _label(frame, "PAUSE ON BENT ARMS", (10, y), 0.6 * sc, WHITE, (0, 0, 200))
            elif in_stop[i]:
                y += _label(frame, "STATIONARY", (10, y), 0.6 * sc, (0, 0, 0), (0, 200, 255))
        if (ow, oh) != (W, H):
            frame = cv2.resize(frame, (ow, oh), interpolation=cv2.INTER_AREA) 
        writer.send(frame.tobytes())
        if progress_cb and i % 10 == 0:
            progress_cb(i / T)

    writer.close()
    cap.release()
    return out