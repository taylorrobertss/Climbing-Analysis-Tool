import os
import tempfile
import base64
import html
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib.pyplot as plt
import streamlit as st
import streamlit.components.v1 as components

from pose import extract_pose
from metrics import compute
from observations import observe, compare
from render import render_overlay

st.set_page_config(page_title="Climbing Beta Analyser", layout="wide")
st.title("Climbing Beta Analyser")


def analyse_video_bytes(video_bytes):
    """Process uploaded video bytes into pose and metric data."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tmp.write(video_bytes)
    tmp.close()

    xy, vis, fps, size = extract_pose(tmp.name)
    m, s = compute(xy, vis, fps)
    return {"src": tmp.name, "xy": xy, "vis": vis, "fps": fps, "m": m, "s": s}


def analyse_uploaded_file(file_obj, label="Tracking body…"):
    """Process one uploaded video and show its tracking progress."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tmp.write(file_obj.getvalue())
    tmp.close()

    bar = st.progress(0.0, label)
    xy, vis, fps, size = extract_pose(tmp.name, bar.progress)
    bar.empty()

    m, s = compute(xy, vis, fps)
    return {"src": tmp.name, "xy": xy, "vis": vis, "fps": fps, "m": m, "s": s}


def show_synced_video_pair(reference_path, comparison_path, reference_name, comparison_name, max_height):
        """Display two videos with synchronized playback controls."""
        with open(reference_path, "rb") as video_file:
                reference_data = base64.b64encode(video_file.read()).decode("ascii")
        with open(comparison_path, "rb") as video_file:
                comparison_data = base64.b64encode(video_file.read()).decode("ascii")

        player_html = """
        <style>
            body { margin: 0; font-family: sans-serif; }
            .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
            h3 { margin: 0 0 8px; font-size: 15px; overflow-wrap: anywhere; }
            video { display: block; width: 100%; aspect-ratio: 16 / 9;
                            max-height: MAX_HEIGHTpx; background: #111; object-fit: contain; }
        </style>
        <div class="pair">
            <section><h3>REFERENCE_LABEL</h3>
                <video id="reference" controls playsinline preload="metadata">
                    <source src="data:video/mp4;base64,REFERENCE_DATA" type="video/mp4">
                </video>
            </section>
            <section><h3>COMPARISON_LABEL</h3>
                <video id="comparison" controls playsinline preload="metadata">
                    <source src="data:video/mp4;base64,COMPARISON_DATA" type="video/mp4">
                </video>
            </section>
        </div>
        <script>
            const videos = [document.getElementById("reference"), document.getElementById("comparison")];
            let syncing = false;
            videos.forEach((video, index) => {
                const other = videos[1 - index];
                video.addEventListener("play", () => {
                    if (syncing) return;
                    syncing = true;
                    other.currentTime = video.currentTime;
                    other.play().catch(() => {});
                    setTimeout(() => { syncing = false; }, 0);
                });
                video.addEventListener("pause", () => {
                    if (syncing) return;
                    syncing = true;
                    other.pause();
                    setTimeout(() => { syncing = false; }, 0);
                });
                video.addEventListener("seeked", () => {
                    if (syncing || Math.abs(other.currentTime - video.currentTime) < 0.05) return;
                    syncing = true;
                    other.currentTime = video.currentTime;
                    setTimeout(() => { syncing = false; }, 0);
                });
                video.addEventListener("ratechange", () => {
                    other.playbackRate = video.playbackRate;
                });
                video.addEventListener("timeupdate", () => {
                    if (!syncing && Math.abs(other.currentTime - video.currentTime) > 0.3) {
                        syncing = true;
                        other.currentTime = video.currentTime;
                        setTimeout(() => { syncing = false; }, 0);
                    }
                });
            });
        </script>
        """
        player_html = (
                player_html.replace("MAX_HEIGHT", str(max_height))
                .replace("REFERENCE_LABEL", html.escape(reference_name))
                .replace("COMPARISON_LABEL", html.escape(comparison_name))
                .replace("REFERENCE_DATA", reference_data)
                .replace("COMPARISON_DATA", comparison_data)
        )
        components.html(player_html, height=max_height + 65, scrolling=False)


# ---------- Sidebar ----------
st.sidebar.header("Overlay options")
show_trail = st.sidebar.checkbox("CoM trail", True)
show_angles = st.sidebar.checkbox("Elbow angles", True)
show_flags = st.sidebar.checkbox("Flags (stationary / bent-arm / low confidence)", True)

st.sidebar.header("Video size")
res = st.sidebar.selectbox("Overlay resolution", ["480p", "720p", "1080p"], index=1)
max_h = {"480p": 480, "720p": 720, "1080p": 1080}[res]
disp_h = st.sidebar.slider("Player max height (px)", 300, 900, 500, 50)

st.sidebar.header("Compare attempts")
ref_file = st.sidebar.file_uploader("Reference attempt", type=["mp4", "mov", "m4v"], key="compare_ref")
new_file = st.sidebar.file_uploader("Comparison attempt", type=["mp4", "mov", "m4v"], key="compare_new")

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

if ref_file and new_file:
    S = st.session_state
    compare_key = ((ref_file.name, ref_file.size), (new_file.name, new_file.size))

    if S.get("compare_key") != compare_key:
        progress = st.progress(0.0, "Analyzing both attempts in parallel…")
        results = {}
        jobs = {
            "compare_reference": ref_file.getvalue(),
            "compare_current": new_file.getvalue(),
        }
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(analyse_video_bytes, video_bytes): key
                    for key, video_bytes in jobs.items()
                }
                for completed, future in enumerate(as_completed(futures), start=1):
                    results[futures[future]] = future.result()
                    progress.progress(completed / 2, "Analyzed one attempt…" if completed == 1 else "Both attempts analyzed")
        finally:
            progress.empty()

        S.update(results, compare_key=compare_key)

    ref_m = S["compare_reference"]["m"]
    new_m = S["compare_current"]["m"]

    st.subheader("Attempt comparison")
    rows = []
    for key, label, better in [
        ("duration_s", "Duration", None),
        ("stop_frac", "Time stationary", "lower"),
        ("straight_arm_frac", "Straight-arm fraction", "higher"),
        ("gie", "Path entropy (GIE)", "lower"),
        ("norm_jerk", "Jerk / smoothness", "lower"),
    ]:
        a = ref_m.get(key)
        b = new_m.get(key)
        if a is None or b is None:
            continue
        delta = b - a
        rows.append(
            {
                "Metric": label,
                "Reference": f"{a:.3f}" if isinstance(a, float) else a,
                "Comparison": f"{b:.3f}" if isinstance(b, float) else b,
                "Delta": f"{delta:+.3f}",
                "Better": better,
            }
        )

    if rows:
        st.dataframe(rows, use_container_width=True)
        st.write("### Comparison notes")
        for note in compare(ref_m, new_m):
            st.write(f"- {note}")
    else:
        st.info("No comparable metrics were available for these two attempts.")

    compare_render_key = (compare_key, show_trail, show_angles, show_flags, max_h)
    if S.get("compare_render_key") != compare_render_key:
        progress = st.progress(0.0, "Rendering comparison overlays…")
        rendered = {}
        attempts = [
            ("compare_reference", "reference_overlay"),
            ("compare_current", "comparison_overlay"),
        ]
        for index, (attempt_key, output_key) in enumerate(attempts):
            attempt = S[attempt_key]
            out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
            render_overlay(
                attempt["src"], out, attempt["xy"], attempt["vis"], attempt["fps"],
                attempt["m"], attempt["s"], show_trail=show_trail,
                show_angles=show_angles, show_flags=show_flags, max_h=max_h,
                progress_cb=lambda value, index=index: progress.progress(
                    (index + value) / 2, "Rendering reference overlay…"
                    if index == 0 else "Rendering comparison overlay…"
                ),
            )
            rendered[output_key] = out
        progress.empty()

        old_outputs = (S.get("reference_overlay"), S.get("comparison_overlay"))
        S.update(rendered, compare_render_key=compare_render_key)
        for old_output in old_outputs:
            if old_output and os.path.exists(old_output):
                try:
                    os.remove(old_output)
                except OSError:
                    pass

    st.subheader("Synchronized overlay videos")
    show_synced_video_pair(
        S["reference_overlay"], S["comparison_overlay"],
        ref_file.name, new_file.name, disp_h,
    )

if f:
    S = st.session_state
    key = (f.name, f.size)

    # 1. Track + analyse (only once per uploaded file)
    if S.get("key") != key:
        for k in ("key", "src", "xy", "vis", "fps", "m", "s", "opts", "out"):
            S.pop(k, None)

        analysis = analyse_uploaded_file(f, "Tracking body…")
        S.update(key=key, src=analysis["src"], xy=analysis["xy"], vis=analysis["vis"], fps=analysis["fps"], m=analysis["m"], s=analysis["s"])

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