from hermes_slack_ext.core.state import WizardState


def test_state_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    st = WizardState(path)
    st.mark_done("detect")
    st.set("hermes_version", "0.15.1")
    st.save()

    reloaded = WizardState(path)
    reloaded.load()
    assert reloaded.is_done("detect")
    assert not reloaded.is_done("board")
    assert reloaded.get("hermes_version") == "0.15.1"


def test_load_missing_file_is_empty(tmp_path):
    st = WizardState(tmp_path / "absent.json")
    st.load()
    assert st.completed == []
