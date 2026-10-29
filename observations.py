from dataclasses import dataclass, field
import math

@dataclass
class Observation:
    title: str
    finding: str
    why: str
    suggestion: str
    evidence: str       # "research" | "indirect" | "convention"
    confidence: str     # "low" | "medium" | "high" (measurement reliability, not truth of the advice)
    times: list = field(default_factory=list)

def observe(m):
    obs = []
    ok = lambda x: x is not None and not (isinstance(x, float) and math.isnan(x))

    if m["data_quality"] < 0.7:
        obs.append(Observation(
            "Tracking quality is low",
            f"Only {m['data_quality']:.0%} of key joints were confidently tracked.",
            "Metrics from heavily interpolated data are unreliable.",
            "Re-film: fixed camera, full body in frame, side lighting, contrasting clothing.",
            "convention", "high"))

    if ok(m["straight_arm_frac"]) and m["straight_arm_frac"] < 0.5:
        obs.append(Observation(
            "Mostly bent-arm hanging",
            f"Elbows were ≥150° in only {m['straight_arm_frac']:.0%} of loaded-hand frames.",
            "Sustained bent-arm isometric holds raise muscle load and restrict forearm blood flow, "
            "contributing to pump. Straight-arm hanging is a common energy-saving strategy.",
            "Between moves, relax the elbows and hang from the skeleton. Drill 'straight-arm' traverses.",
            "indirect", "medium"))

    bent_stops = [s for s in m["stops"] if ok(s["mean_elbow"]) and s["mean_elbow"] < 130]
    if bent_stops:
        obs.append(Observation(
            "Pauses on bent arms",
            f"{len(bent_stops)} pause(s) ≥1 s with elbows <130° "
            f"({sum(s['end'] - s['start'] for s in bent_stops):.1f} s total).",
            "Stopping while strongly flexed is energetically costly. Longer immobility is also "
            "associated with route-finding hesitation in the literature.",
            "Find a position to drop the hips or straighten the arms before deciding on the next move. "
            "Pre-read sequences to cut decision time.",
            "indirect", "medium", [(s["start"], s["end"]) for s in bent_stops]))

    if m["stop_frac"] > 0.3:
        obs.append(Observation(
            "High proportion of time stationary",
            f"{m['stop_frac']:.0%} of the attempt was spent nearly motionless.",
            "Immobility time is used as a marker of hesitation / route-finding in climbing research and "
            "tends to fall with route familiarity and skill.",
            "If these are deliberate rests, fine. Otherwise rehearse the sequence before pulling on.",
            "research", "medium", [(s["start"], s["end"]) for s in m["stops"]]))

    if m["foot_adjust_per_foot_move"] > 1.0 and m["foot_moves"] >= 3:
        obs.append(Observation(
            "Frequent foot readjustments",
            f"{m['foot_adjustments']} small foot movements vs {m['foot_moves']} full foot moves.",
            "Repeated small foot corrections can signal imprecise placement or exploratory foot "
            "behaviour, which typically decreases as route knowledge improves.",
            "Look at the foot until it is placed and weighted. Practise silent-feet drills.",
            "indirect", "low"))

    if m["low_contact_frac"] > 0.35:
        obs.append(Observation(
            "Many frames with ≤2 limbs stationary",
            f"{m['low_contact_frac']:.0%} of the time, two or more limbs were moving at once.",
            "Moving several limbs together is intrinsically less stable on steep terrain, but is normal for "
            "dynamic moves. 'Three points of contact' is coaching convention, not a rule from controlled studies.",
            "Check whether this was intentional (dynos, flagging, cut-loose) or reactive.",
            "convention", "low"))
    return obs

def compare(prev, curr, tol=0.10):
    """Attempt-to-attempt changes are usually more meaningful than absolute thresholds."""
    notes = []
    for key, label, better in [("gie", "Path entropy (GIE)", "lower"),
                               ("norm_jerk", "Jerk (smoothness)", "lower"),
                               ("stop_frac", "Time stationary", "lower"),
                               ("straight_arm_frac", "Straight-arm fraction", "higher"),
                               ("duration_s", "Duration", None)]:
        a, b = prev[key], curr[key]
        if a and b and abs(b - a) / abs(a) > tol:
            d = "↑" if b > a else "↓"
            good = "" if better is None else (" ✅" if (b < a) == (better == "lower") else " ⚠️")
            notes.append(f"{label}: {a:.2f} → {b:.2f} {d}{good}")
    return notes