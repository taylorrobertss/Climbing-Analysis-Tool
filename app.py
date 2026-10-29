import os
import tempfile

import matplotlib.pyplot as plt
import streamlit as st

from pose import extract_pose
from metrics import compute
from observations import observe
from render import render_overlay

st.set_page_config(page_title="Climbing Beta Analyser", layout="wide")
st.title("Climbing Beta Analyser")

# ---------- Sidebar ----------
st.sidebar.header("Overlay options")
show_trail = st.sidebar.checkbox("CoM trail", True)
show_angles = st.sidebar.checkbox("Elbow angles", True)
show_flags = st.sidebar.checkbox("Flags (stationary / bent-arm / low confidence)", True)

st.sidebar.header("Video size")
res = st.sidebar.selectbox("Overlay resolution", ["480p", "720p", "1080p"], index=1)
max_h = {"480p": 480, "720p": 720, "1080p": 1080}[res]
disp_h = st.sidebar.slider("Player max height (px)", 300, 900, 500, 50)

# Limit how large the player appears on screen (no re-render needed)
st.markdown(
    f"""<style>
    video {{ max-height: {disp_h}px; width: auto !important; max-width: 100%;
             display: block; margin: 0 auto; }}
    </style>""",
    unsafe_allow_html=True,
)

# ---------- Upload ----------
f = st.file_uploader("Upload climb video", type=["mp4", "mov", "m4v"])

if f:
    S = st.session_state
    key = (f.name, f.size)

    # 1. Track + analyse (only once per uploaded file)
    if S.get("key") != key:
        for k in ("key", "src", "xy", "vis", "fps", "m", "s", "opts", "out"):
            S.pop(k, None)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tmp.write(f.getvalue())
        tmp.close()

        bar = st.progress(0.0, "Tracking body…")
        xy, vis, fps, size = extract_pose(tmp.name, bar.progress)
        bar.empty()

        m, s = compute(xy, vis, fps)
        S.update(key=key, src=tmp.name, xy=xy, vis=vis, fps=fps, m=m, s=s)

    m, s = S["m"], S["s"]

    # 2. Render overlay (re-runs only if an overlay option or resolution changes)
    opts = (show_trail, show_angles, show_flags, max_h)
    if S.get("opts") != opts:
        old = S.get("out")
        out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        bar = st.progress(0.0, "Rendering overlay…")
        render_overlay(
            S["src"], out, S["xy"], S["vis"], S["fps"], m, s,
            show_trail=show_trail, show_angles=show_angles,
            show_flags=show_flags, max_h=max_h,
            progress_cb=bar.progress,
        )
        bar.empty()
        S["opts"], S["out"] = opts, out
        if old and os.path.exists(old):
            try:
                os.remove(old)
            except OSError:
                pass

    # 3. Layout: video on the left, summary on the right
    left, right = st.columns([2, 3])

    with left:
        st.subheader("Overlay")
        with open(S["out"], "rb") as fh:
            data = fh.read()
        st.video(data)
        st.download_button("Download overlay video", data, "beta_overlay.mp4", "video/mp4")
        st.caption(
            "🟢 limb still · 🔴 limb moving · 🟣 centre of mass · "
            "elbow angle: green ≥150°, yellow 130–150°, red <130°"
        )

    with right:
        c1, c2, c3 = st.columns(3)
        c1.metric("Duration", f"{m['duration_s']:.1f}s")
        c2.metric("Hand / foot moves", f"{m['hand_moves']} / {m['foot_moves']}")
        c3.metric("Stationary", f"{m['stop_frac']:.0%}")

        fig, ax = plt.subplots(1, 2, figsize=(8, 3.5))
        ax[0].plot(s["com"][:, 0], s["com"][:, 1])
        ax[0].set_title("CoM path (TL)")
        ax[0].set_aspect("equal")
        ax[1].plot(s["t"], s["speed"])
        ax[1].set_title("CoM speed (TL/s)")
        ax[1].set_xlabel("s")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # 4. Observations
    st.subheader("Observations")
    observations = observe(m)
    if not observations:
        st.info("No rules triggered for this attempt.")
    for o in observations:
        with st.expander(f"{o.title}  ·  evidence: {o.evidence}  ·  confidence: {o.confidence}"):
            st.write("**Measured:**", o.finding)
            st.write("**Why it matters:**", o.why)
            st.write("**Try:**", o.suggestion)
            if o.times:
                st.caption("Time ranges (s): " + ", ".join(f"{a:.1f}–{b:.1f}" for a, b in o.times))

    with st.expander("All metrics"):
        st.json({k: v for k, v in m.items() if k != "stops"})