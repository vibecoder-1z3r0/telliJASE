from tellijase.psg import ShadowState


def test_shadow_state_updates_and_clamps():
    state = ShadowState()
    state.update(R0=260, R8=-1)

    snapshot = state.snapshot()
    assert snapshot["R0"] == 255
    assert snapshot["R8"] == 0


def test_shadow_state_rejects_unknown_register():
    state = ShadowState()
    try:
        state.update(R99=1)
    except KeyError as exc:
        assert "Unknown register" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected KeyError")
