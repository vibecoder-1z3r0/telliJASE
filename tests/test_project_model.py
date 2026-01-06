import pytest

from tellijase.storage import Project, JamSession


def test_project_touch_updates_modified():
    project = Project()
    old_modified = project.meta.modified
    project.touch()
    assert project.meta.modified >= old_modified


def test_jam_session_register_validation():
    jam = JamSession(id="1", name="Test", registers={"R0": 1})
    assert jam.registers["R0"] == 1

    with pytest.raises(ValueError):
        JamSession(id="2", name="Bad", registers={"RX": 1})


def test_project_round_trip():
    project = Project()
    project.jam_sessions.append(JamSession(id="1", name="Lead", registers={"R0": 10}))
    data = project.to_dict()

    rebuilt = Project.from_dict(data)
    assert rebuilt.jam_sessions[0].registers["R0"] == 10
