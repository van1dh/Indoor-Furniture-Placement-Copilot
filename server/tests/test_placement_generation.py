import json
import os
import random
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import placement_generation as pg  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "placement_generation.py")


def run_script(request, tmp_path):
    proc = subprocess.run(
        [sys.executable, SCRIPT, "--output-dir", str(tmp_path), "--seed", "0"],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("seed", range(20))
def test_layout_has_no_overlaps_and_stays_in_room(seed):
    counts = {"bed": 2, "desk": 2, "tv": 1, "wardrobe": 2}
    layout = pg.generate_room_layout(counts, random.Random(seed))

    assert len(layout) == sum(counts.values())
    for i, a in enumerate(layout):
        assert a.width / 2 <= a.x <= pg.ROOM_WIDTH - a.width / 2
        assert a.height / 2 <= a.y <= pg.ROOM_HEIGHT - a.height / 2
        for b in layout[i + 1:]:
            assert not a.overlaps(b.x, b.y, b.width, b.height), f"{a.name} overlaps {b.name}"


def test_wall_furniture_faces_into_room():
    layout = pg.generate_room_layout({"bed": 0, "desk": 1, "tv": 1, "wardrobe": 2}, random.Random(0))
    for f in layout:
        ix, iy = f.interact_position
        # The interaction point must be on the room side of the furniture, not against a wall
        assert 0 < ix < pg.ROOM_WIDTH and 0 < iy < pg.ROOM_HEIGHT


def test_too_much_furniture_raises_instead_of_overlapping(monkeypatch):
    monkeypatch.setitem(pg.FURNITURE_SIZES, "bed", (20, 30))
    with pytest.raises(pg.PlacementError):
        pg.generate_room_layout({"bed": 2}, random.Random(0))


@pytest.mark.parametrize(
    "request_body",
    [
        {},
        {"bed": 0, "desk": 0, "tv": 0, "wardrobe": 0},
        {"bed": -1},
        {"bed": 5},
        {"bed": 1.5},
        {"bed": "abc"},
        {"bed": 1, "notes": "x" * (pg.MAX_NOTES_LENGTH + 1)},
        [],
    ],
)
def test_parse_request_rejects_invalid_input(request_body):
    with pytest.raises(pg.InputError):
        pg.parse_request(request_body)


def test_parse_request_treats_blank_as_zero():
    counts, notes = pg.parse_request({"bed": "1", "desk": "", "tv": None, "notes": "  hi "})
    assert counts == {"bed": 1, "desk": 0, "tv": 0, "wardrobe": 0}
    assert notes == "hi"


def test_script_writes_png_and_reports_file_name(tmp_path):
    code, result = run_script({"bed": 1, "desk": 1, "tv": 1, "wardrobe": 1, "notes": "test"}, tmp_path)
    assert code == 0
    image = tmp_path / result["image"]
    assert image.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_script_reports_invalid_input(tmp_path):
    code, result = run_script({"bed": ""}, tmp_path)
    assert code == 2
    assert "at least one" in result["error"]
    assert list(tmp_path.iterdir()) == []
