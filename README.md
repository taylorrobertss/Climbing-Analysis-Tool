# Climbing Beta Analyser: Sources and Evidence


## 1. Climbing-movement metrics

### Path entropy (GIE) in `metrics.py`
- Cordier, Mendes France, Pailhous and Bolon (1994). *Entropy as a global variable of the learning process.* Human Movement Science. **Recall: Medium.**
- Cordier and colleagues (1990s). Work on entropy, degrees of freedom and free climbing, based on trajectory analysis. **Recall: Medium-low.** Search for it.
- **Used for:** `log(2L / hull perimeter)`, where `L` is the path length. Lower values mean a more direct path.
- **Caveat:** the original work was on specific measurement set-ups. This tool applies it to a 2D, torso-normalised video estimate, so the numbers are **not comparable** with published values.

### Fluency / jerk in `metrics.py`
- Seifert, Orth, Boulanger, Dovgalecs, Herault and Davids (2014). *Climbing skill and complexity of climbing wall design: assessment of jerk as a novel indicator of performance fluency.* Journal of Applied Biomechanics. **Recall: Medium.** I believe the title is close, but check it.
- Hogan and Sternad (2009). *Sensitivity of smoothness measures to movement duration, amplitude, and arrests.* Journal of Motor Behavior. **Recall: Medium-high.** This is the basis for a dimensionless jerk measure.
- Balasubramanian, Melendez-Calderon, Roby-Brami and Burdet (2015). *On the analysis of movement smoothness.* Journal of NeuroEngineering and Rehabilitation. **Recall: Medium.**
- **Caveat:** the tool's normalisation (`nj` in `metrics.py`) is my own implementation of a dimensionless jerk. It has not been checked against these papers' formulas or against published values.

### Centre-of-mass trajectories
- Sibella, Frosio, Schena and Borghese (2007). *3D analysis of the body center of mass in rock climbing.* Human Movement Science. **Recall: Medium-high.**
- Zampagni, Brigadoi, Schena, Tosi and Ivanenko (2011). *Idiosyncratic control of the center of mass in expert climbers.* Scandinavian Journal of Medicine and Science in Sports. **Recall: Medium-high.**
- **Used as:** background for why the centre-of-mass path is worth tracking. Neither paper provides the thresholds used here.

### Immobility, exploration and route-finding (stationary-time rules)
- Seifert, Cordier, Orth, Courtine and Croft (2017). *Role of route previewing strategies on climbing fluency and exploratory movements.* PLoS ONE. **Recall: Medium.**
- Sanchez, Lambert, Jones and Llewellyn (2012). *Efficacy of pre-ascent climbing route visual inspection in indoor sport climbing.* Scandinavian Journal of Medicine and Science in Sports. **Recall: Medium.**
- Orth, Davids and Seifert (2016 or later). Reviews on coordination, exploration and skill in climbing. **Recall: Low-medium.**
- Boschker and Bakker, and colleagues (around 2002). Work on climbers perceiving opportunities on walls. **Recall: Low.** The exact paper is uncertain.
- **Caveat:** these papers discuss immobility and exploration in general. I have **not** confirmed they support the specific claim in `observations.py` that "time stationary tends to fall with familiarity and skill", nor the 30% threshold. That threshold is a placeholder.

### Forearm load, bent arms and pump
- Ferguson and Brown (1997?). Forearm blood flow and blood pressure in rock climbers during isometric exercise. **Recall: Low.**
- Fryer and colleagues (2015-2018). Forearm oxygenation and hemodynamic differences between climbers. **Recall: Low-medium.**
- Philippe and colleagues (2012). Finger-flexor performance and forearm oxygenation in elite climbers. **Recall: Low-medium.**
- **Caveat:** this is the weakest part of the evidence. The "bent arms cost more" idea is physiologically plausible, and it is also a widely held coaching belief. I have **not** identified a study that shows that bent-arm hanging in particular causes a fall, or that sets 150 or 130 degrees as a cut-off.

### Determinants of climbing success
- Saul, Steinmetz, Lehmann and Schilling (2019). *Determinants for success in climbing: a systematic review.* Journal of Exercise Science and Fitness. **Recall: Medium.**
- **Used as:** a place to find other primary studies, not as direct support for any rule.

### Body equilibrium and hip position
- Quaine and Martin (1999). *A biomechanical study of equilibrium in sport rock climbing.* Gait and Posture. **Recall: Medium.**
- The hip-pull model discussed during development (`pull / bodyweight = ...`) is **standard statics that I derived**, not a published climbing model. It ignores friction and treats hands and feet as two lumped contacts. Treat it as a comparison index, not a force measurement. `hips.py` is not part of the current project files.

---

## 2. Tool rules and their evidence status

| Rule / feature | Where | What supports it | Honest status | Suggested tag |
|---|---|---|---|---|
| Tracking-quality warning | `observations.py` | Common sense: interpolated data is unreliable | No citation needed | convention |
| Mostly bent-arm hanging | `observations.py` | Physiological reasoning plus coaching belief | Plausible, unverified | indirect |
| Pauses on bent arms | `observations.py` | Same as above | Plausible, unverified | indirect |
| High proportion stationary | `observations.py` | Immobility literature (Section 3) | Currently tagged `research`. **Not confirmed.** | indirect until checked |
| Frequent foot readjustments | `observations.py` | Exploration literature (Orth, Seifert, et al.) | Plausible, unverified | indirect |
| Few stationary limbs | `observations.py` | "Three points of contact" coaching idea | Coaching convention | convention |
| Move flags (arm reach, hips off foot, hand before foot, several limbs) | `moves.py` | Coaching practice | No study cited | convention |
| Failure-cause hypotheses | `diagnosis.py` (if you have it; it was not in the uploaded zip) | My own framework | Not validated | convention |
| Hip closeness and pull index | `hips.py` (if you have it; it was not in the uploaded zip) | Basic statics | Reasoning only | mechanics (model-based) |

**One concrete action:** the "High proportion of time stationary" rule is tagged `research` in `observations.py`. Change it to `indirect` until you have confirmed the source.

---

## 3. Parameters with no source

These are placeholders chosen by me. They are **not** published thresholds:

- Elbow angles of **150 degrees** (straight) and **130 degrees** (bent)
- Limb speed of **0.6 torso lengths per second** (counts as "moving")
- Centre-of-mass speed of **0.12 torso lengths per second** (counts as "stationary")
- Minimum pause of **1 s**
- Hand move threshold of **0.4 torso lengths**
- 30% stationary, 20 s with no rest, 85% reach, 0.15 TL "body moved first", 1.5 TL/s dynamic
- Torso length of **50 cm** (used only for centimetre conversions in `hips.py`, if you use it)

Calibrate them against your own footage and against clips labelled by a coach you trust.

---

## 4. Limits that apply to every result

- All measurements come from **2D video**. Elbow angles, hip distance and reach all suffer from foreshortening when limbs point toward the camera.
- There is **no hold detection**, so "loaded hand" and "planted foot" are guesses based on stillness and height.
- The tool does not know the route's grade, hold type, wall angle or your intent. A dyno and a lost foot can look alike. A deliberate rest and freezing can look alike.
- Output is **not medical or injury advice**. Be conservative with any finger-loading or training suggestion.

---

## 5. Verification checklist

1. Search Google Scholar, PubMed or the journal sites for each entry in Sections 2 and 3. Record the correct title, year, DOI and what the paper actually concluded.
2. Check the three claims that drive the most output first: the bent-arm rule, the immobility rule and the GIE interpretation.
3. If you can't find support for a rule, set its tag to `convention` and remove any wording that implies research.
4. Add the DOI next to each source in this file. Replace the blank "Verified?" cells with the date and your initials.
5. Re-check the dimensionless-jerk formula in `metrics.py` against Hogan and Sternad (2009) or Balasubramanian et al. (2015).

