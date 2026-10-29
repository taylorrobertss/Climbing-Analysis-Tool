from observations import compare


def test_compare_reports_expected_changes():
    prev = {
        "gie": 1.0,
        "norm_jerk": 2.0,
        "stop_frac": 0.45,
        "straight_arm_frac": 0.40,
        "duration_s": 20.0,
    }
    curr = {
        "gie": 0.8,
        "norm_jerk": 1.5,
        "stop_frac": 0.30,
        "straight_arm_frac": 0.55,
        "duration_s": 18.0,
    }

    notes = compare(prev, curr)

    assert len(notes) == 5
    assert any("Path entropy" in note for note in notes)
    assert any("Jerk" in note for note in notes)
    assert any("Time stationary" in note for note in notes)
