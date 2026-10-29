import numpy as np
from scipy.signal import savgol_filter
from scipy.spatial import ConvexHull

# MediaPipe landmark indices
NOSE, LS, RS, LE, RE, LW, RW, LH, RH, LK, RK, LA, RA = 0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28
LIMBS = {"L hand": LW, "R hand": RW, "L foot": LA, "R foot": RA}

# ---------- preprocessing ----------
def clean(xy, vis, fps, vmin=0.5):
    """Mask low-confidence points, interpolate gaps, smooth."""
    xy = xy.copy()
    xy[vis < vmin] = np.nan
    t = np.arange(len(xy))
    for j in range(xy.shape[1]):
        for c in range(2):
            y = xy[:, j, c]
            ok = ~np.isnan(y)
            if ok.sum() > 2:
                xy[:, j, c] = np.interp(t, t[ok], y[ok])
    win = max(int(fps * 0.25) // 2 * 2 + 1, 5)
    return savgol_filter(xy, win, 3, axis=0)

def normalise(xy):
    """Scale to torso lengths (TL); flip y so up is positive."""
    ms = (xy[:, LS] + xy[:, RS]) / 2
    mh = (xy[:, LH] + xy[:, RH]) / 2
    tl = np.nanmedian(np.linalg.norm(ms - mh, axis=1))
    p = xy / tl
    p[..., 1] *= -1
    return p, tl

def deriv(x, fps, order):
    win = max(int(fps * 0.3) // 2 * 2 + 1, 7)
    return savgol_filter(x, win, 3, deriv=order, delta=1 / fps, axis=0)

def angle(a, b, c):
    v1, v2 = a - b, c - b
    cos = (v1 * v2).sum(-1) / (np.linalg.norm(v1, axis=-1) * np.linalg.norm(v2, axis=-1) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))

def runs(mask):
    d = np.diff(np.r_[0, mask.astype(int), 0])
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))  # [start, end)

# ---------- centre of mass (Dempster-style segment weights, simplified) ----------
def com(p):
    mid = lambda a, b: (p[:, a] + p[:, b]) / 2
    trunk = (p[:, LS] + p[:, RS] + p[:, LH] + p[:, RH]) / 4
    segs = [(trunk, .497), (p[:, NOSE], .081)]
    for sh, el, wr, hp, kn, an in [(LS, LE, LW, LH, LK, LA), (RS, RE, RW, RH, RK, RA)]:
        segs += [(mid(sh, el), .028), (mid(el, wr), .022),
                 (mid(hp, kn), .100), (mid(kn, an), .061)]
    return sum(w * s for s, w in segs)

# ---------- main ----------
def compute(xy_raw, vis, fps, v_move=0.6, v_com_still=0.12, min_stop_s=1.0):
    p, tl = normalise(clean(xy_raw, vis, fps))
    T = len(p)
    dur = T / fps
    c = com(p)

    v = deriv(c, fps, 1)
    speed = np.linalg.norm(v, axis=1)
    step = np.linalg.norm(np.diff(c, axis=0), axis=1)
    L = float(step.sum())
    vertical_gain = float(c[-1, 1] - c[0, 1])

    # Geometric index of entropy (Cordier et al.): log(2L / hull perimeter). 0 for a straight line.
    try:
        gie = float(np.log(2 * L / ConvexHull(c).area))
    except Exception:
        gie = float("nan")

    # Normalised dimensionless jerk (fluency; cf. Seifert et al. 2014)
    j = deriv(c, fps, 3)
    nj = float(np.sqrt(0.5 * (np.linalg.norm(j, axis=1) ** 2).sum() / fps * dur ** 5 / (L ** 2 + 1e-9)))

    # Limb events
    limb_speed, events = {}, {}
    for name, idx in LIMBS.items():
        s = np.linalg.norm(deriv(p[:, idx], fps, 1), axis=1)
        limb_speed[name] = s
        ev = []
        for a, b in runs(s > v_move):
            if (b - a) / fps < 0.1:
                continue
            disp = float(np.linalg.norm(p[b - 1, idx] - p[a, idx]))
            ev.append(dict(start=a / fps, end=b / fps, disp=disp,
                           kind="move" if disp >= 0.4 else "adjust"))
        events[name] = ev

    n_hand_moves = sum(e["kind"] == "move" for k in ("L hand", "R hand") for e in events[k])
    n_foot_moves = sum(e["kind"] == "move" for k in ("L foot", "R foot") for e in events[k])
    n_foot_adj = sum(e["kind"] == "adjust" for k in ("L foot", "R foot") for e in events[k])

    # Arms: elbow angle while the hand is probably loaded (still, above shoulder)
    elbow = {"L": angle(p[:, LS], p[:, LE], p[:, LW]), "R": angle(p[:, RS], p[:, RE], p[:, RW])}
    loaded = {"L": (p[:, LW, 1] > p[:, LS, 1] + 0.1) & (limb_speed["L hand"] < v_move),
              "R": (p[:, RW, 1] > p[:, RS, 1] + 0.1) & (limb_speed["R hand"] < v_move)}
    n_loaded = sum(m.sum() for m in loaded.values())
    n_straight = sum(((elbow[k] >= 150) & loaded[k]).sum() for k in "LR")
    straight_frac = float(n_straight / n_loaded) if n_loaded else float("nan")

    # Stops (centre of mass nearly stationary ≥ min_stop_s)
    stops = []
    for a, b in runs(speed < v_com_still):
        if (b - a) / fps < min_stop_s:
            continue
        angs = np.concatenate([elbow[k][a:b][loaded[k][a:b]] for k in "LR"])
        stops.append(dict(start=a / fps, end=b / fps,
                          mean_elbow=float(angs.mean()) if len(angs) else float("nan")))
    stop_time = sum(s["end"] - s["start"] for s in stops)

    # Stationary-limb count (proxy for number of contacts)
    still = sum((limb_speed[k] < v_move).astype(int) for k in LIMBS)
    low_contact_frac = float((still <= 2).mean())

    metrics = dict(
        duration_s=dur, path_length_TL=L, vertical_gain_TL=vertical_gain,
        vertical_efficiency=vertical_gain / L if L else float("nan"),
        gie=gie, norm_jerk=nj,
        hand_moves=n_hand_moves, foot_moves=n_foot_moves, foot_adjustments=n_foot_adj,
        foot_adjust_per_foot_move=n_foot_adj / max(n_foot_moves, 1),
        straight_arm_frac=straight_frac,
        stop_time_s=stop_time, stop_frac=stop_time / dur, stops=stops,
        low_contact_frac=low_contact_frac,
        data_quality=float((vis[:, [LS, RS, LH, RH, LW, RW, LA, RA]] > 0.5).mean()),
    )
    series = dict(t=np.arange(T) / fps, com=c, speed=speed, elbow=elbow, limb_speed=limb_speed, events=events)
    return metrics, series