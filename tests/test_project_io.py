from pathlib import Path

from tellijase.storage import JamSession, load_project, new_project, save_project


def test_save_and_load_round_trip(tmp_path):
    project = new_project("Test Jam")
    project.jam_sessions.append(JamSession(id="jam-1", name="Session 1", registers={"R0": 10}))

    dest = tmp_path / "song"
    saved_path = save_project(project, dest)
    assert saved_path.suffix == ".tellijase"
    assert saved_path.exists()

    loaded = load_project(saved_path)
    assert loaded.meta.name == "Test Jam"
    assert loaded.jam_sessions[0].registers["R0"] == 10
