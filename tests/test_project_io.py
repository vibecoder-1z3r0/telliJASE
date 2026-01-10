from pathlib import Path

from tellijase.models import PSGState
from tellijase.storage import (
    JamSession,
    Song,
    TrackEvent,
    load_project,
    new_project,
    save_project,
)


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


def test_jam_session_from_psg_state(tmp_path):
    """Test JAM session save using PSGState.to_registers() - simulates actual UI flow."""
    project = new_project("Test PSG State")

    # Create a PSG state with envelope settings
    psg_state = PSGState()
    psg_state.channel_a.frequency = 440
    psg_state.channel_a.volume = 12
    psg_state.channel_a.tone_enabled = True
    psg_state.envelope_period = 1000  # This creates R13 and R14
    psg_state.envelope_shape = 10  # This creates R15

    # Convert to registers (this is what main.py does when saving)
    registers = psg_state.to_registers()

    # Create session with these registers
    session = JamSession(id="jam-psg", name="PSG Session", registers=registers)
    project.jam_sessions.append(session)

    # Save and load
    dest = tmp_path / "psg_session"
    saved_path = save_project(project, dest)
    loaded = load_project(saved_path)

    # Verify session loaded correctly
    loaded_session = loaded.jam_sessions[0]
    assert loaded_session.id == "jam-psg"

    # Verify envelope registers (R13, R14, R15) are present
    assert "R13" in loaded_session.registers
    assert "R14" in loaded_session.registers
    assert "R15" in loaded_session.registers

    # Verify envelope values
    assert loaded_session.registers["R13"] == 1000 & 0xFF  # Low byte
    assert loaded_session.registers["R14"] == (1000 >> 8) & 0xFF  # High byte
    assert loaded_session.registers["R15"] == 10

    # Verify round-trip by loading back into PSGState
    restored_state = PSGState.from_registers(loaded_session.registers)
    assert restored_state.envelope_period == 1000
    assert restored_state.envelope_shape == 10


def test_jam_session_with_all_registers(tmp_path):
    """Test JAM session save/load with all PSG registers including envelope."""
    project = new_project("Test All Registers")

    # Create a session with all 16 PSG registers (R0-R15)
    registers = {
        "R0": 100,  # Channel A period low
        "R1": 2,  # Channel A period high
        "R2": 150,  # Channel B period low
        "R3": 1,  # Channel B period high
        "R4": 200,  # Channel C period low
        "R5": 3,  # Channel C period high
        "R6": 5,  # Noise period
        "R7": 0x3F,  # Mixer control
        "R8": 10,  # Channel A volume
        "R9": 12,  # Channel B volume
        "R10": 15,  # Channel C volume
        "R11": 0,  # Envelope period low
        "R12": 0,  # Envelope period high
        "R13": 100,  # Envelope period low (new format)
        "R14": 5,  # Envelope period high (new format)
        "R15": 8,  # Envelope shape
    }

    session = JamSession(id="jam-full", name="Full Session", registers=registers)
    project.jam_sessions.append(session)

    # Save and load
    dest = tmp_path / "full_session"
    saved_path = save_project(project, dest)
    loaded = load_project(saved_path)

    # Verify all registers round-trip correctly
    loaded_session = loaded.jam_sessions[0]
    assert loaded_session.id == "jam-full"
    assert loaded_session.name == "Full Session"

    # Check all 16 registers
    for reg in ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15"]:
        assert loaded_session.registers[reg] == registers[reg], f"Register {reg} mismatch"


def test_save_and_load_song_with_tracks(tmp_path):
    """Test saving and loading songs with track events."""
    project = new_project("Test Song Project")

    # Create a song with track events on multiple channels
    song = Song(id="song-1", name="Test Song", bpm=120, loop=True)

    # Channel A: Two events
    song.tracks["A"] = [
        TrackEvent(frame=0, duration=10, period=100, volume=15, noise=False),
        TrackEvent(frame=30, duration=5, period=200, volume=10, noise=False),
    ]

    # Channel B: One event
    song.tracks["B"] = [
        TrackEvent(frame=15, duration=20, period=150, volume=12, noise=False),
    ]

    # Noise channel: One event
    song.tracks["N"] = [
        TrackEvent(frame=0, duration=60, noise_period=5, volume=8, noise=True),
    ]

    project.songs.append(song)

    # Save and load
    dest = tmp_path / "test_song"
    saved_path = save_project(project, dest)
    loaded = load_project(saved_path)

    # Verify song properties
    assert len(loaded.songs) == 1
    loaded_song = loaded.songs[0]
    assert loaded_song.id == "song-1"
    assert loaded_song.name == "Test Song"
    assert loaded_song.bpm == 120
    assert loaded_song.loop is True

    # Verify Channel A events
    assert "A" in loaded_song.tracks
    assert len(loaded_song.tracks["A"]) == 2

    evt_a0 = loaded_song.tracks["A"][0]
    assert evt_a0.frame == 0
    assert evt_a0.duration == 10
    assert evt_a0.period == 100
    assert evt_a0.volume == 15
    assert evt_a0.noise is False

    evt_a1 = loaded_song.tracks["A"][1]
    assert evt_a1.frame == 30
    assert evt_a1.duration == 5
    assert evt_a1.period == 200
    assert evt_a1.volume == 10

    # Verify Channel B event
    assert "B" in loaded_song.tracks
    assert len(loaded_song.tracks["B"]) == 1

    evt_b0 = loaded_song.tracks["B"][0]
    assert evt_b0.frame == 15
    assert evt_b0.duration == 20
    assert evt_b0.period == 150
    assert evt_b0.volume == 12

    # Verify Noise channel event
    assert "N" in loaded_song.tracks
    assert len(loaded_song.tracks["N"]) == 1

    evt_n0 = loaded_song.tracks["N"][0]
    assert evt_n0.frame == 0
    assert evt_n0.duration == 60
    assert evt_n0.noise_period == 5
    assert evt_n0.volume == 8
    assert evt_n0.noise is True


def test_multiple_songs_in_project(tmp_path):
    """Test saving and loading a project with multiple songs."""
    project = new_project("Multi-Song Project")

    # Song 1
    song1 = Song(id="song-1", name="First Song", bpm=140)
    song1.tracks["A"] = [
        TrackEvent(frame=0, period=100, volume=15),
    ]
    project.songs.append(song1)

    # Song 2
    song2 = Song(id="song-2", name="Second Song", bpm=90, loop=True)
    song2.tracks["B"] = [
        TrackEvent(frame=0, period=200, volume=10),
        TrackEvent(frame=20, period=150, volume=12),
    ]
    project.songs.append(song2)

    # Save and load
    dest = tmp_path / "multi_song"
    saved_path = save_project(project, dest)
    loaded = load_project(saved_path)

    # Verify both songs
    assert len(loaded.songs) == 2

    assert loaded.songs[0].name == "First Song"
    assert loaded.songs[0].bpm == 140
    assert len(loaded.songs[0].tracks["A"]) == 1

    assert loaded.songs[1].name == "Second Song"
    assert loaded.songs[1].bpm == 90
    assert loaded.songs[1].loop is True
    assert len(loaded.songs[1].tracks["B"]) == 2


def test_track_event_all_fields(tmp_path):
    """Test TrackEvent with all optional fields populated."""
    project = new_project("Full Event Test")

    song = Song(id="song-1", name="Full Event Song")
    song.tracks["C"] = [
        TrackEvent(
            frame=10,
            duration=15,
            period=250,
            volume=14,
            noise_period=3,
            envelope_id="env-1",
            instrument_id="inst-1",
            noise=True,
        ),
    ]
    project.songs.append(song)

    # Save and load
    dest = tmp_path / "full_event"
    saved_path = save_project(project, dest)
    loaded = load_project(saved_path)

    # Verify all fields
    evt = loaded.songs[0].tracks["C"][0]
    assert evt.frame == 10
    assert evt.duration == 15
    assert evt.period == 250
    assert evt.volume == 14
    assert evt.noise_period == 3
    assert evt.envelope_id == "env-1"
    assert evt.instrument_id == "inst-1"
    assert evt.noise is True
