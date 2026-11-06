import json
import os
import subprocess
import sys

import pytest

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SERVER_DIR)

from layout import InputError, PlacementError, describe, generate_layout  # noqa: E402
from layout.catalog import FURNITURE_TYPES, PRESETS  # noqa: E402
from layout.model import Opening, Piece, Placement, Room, footprint, overlap_area  # noqa: E402
from layout.request import parse_request  # noqa: E402
from layout.scoring import Scorer  # noqa: E402

DOOR = {"wall": "bottom", "offset": 1, "width": 3}


def make_request(**overrides):
    request = {
        "preset": "default",
        "room": {"width": 16, "length": 14, "doors": [DOOR], "windows": [{"wall": "top", "offset": 5, "width": 5}]},
        "furniture": [{"type": "bed", "count": 1}, {"type": "desk", "count": 1},
                      {"type": "tv", "count": 1}, {"type": "wardrobe", "count": 1}],
        "seed": 7,
    }
    request.update(overrides)
    return request


def rects(layout):
    return [
        (f["x"] - f["footprint"]["width"] / 2, f["y"] - f["footprint"]["length"] / 2,
         f["x"] + f["footprint"]["width"] / 2, f["y"] + f["footprint"]["length"] / 2)
        for f in layout["furniture"]
    ]


# --- request validation -----------------------------------------------------------------------------------

@pytest.mark.parametrize("change", [
    {"preset": "nope"},
    {"room": None},
    {"room": {"width": 3, "length": 14, "doors": [DOOR]}},
    {"room": {"width": 16, "length": "abc", "doors": [DOOR]}},
    {"room": {"width": 16, "length": 14, "doors": []}},
    {"room": {"width": 16, "length": 14, "doors": [{"wall": "ceiling", "offset": 1, "width": 3}]}},
    {"room": {"width": 16, "length": 14, "doors": [{"wall": "bottom", "offset": 14, "width": 3}]}},
    {"furniture": []},
    {"furniture": [{"type": "bed", "count": 0}]},
    {"furniture": [{"type": "piano", "count": 1}]},
    {"furniture": [{"type": "bed", "count": 1.5}]},
    {"furniture": [{"type": "bed", "count": -1}]},
    {"furniture": [{"type": "bed", "count": 1, "width": 0}]},
    {"furniture": [{"type": "bed", "count": 1}, {"type": "bed", "count": 1}]},
    {"furniture": [{"type": "bed", "count": 6}, {"type": "sofa", "count": 6}]},
    {"notes": "x" * 501},
    {"seed": "abc"},
    {"seed": True},
])
def test_rejects_invalid_requests(change):
    with pytest.raises(InputError):
        parse_request(make_request(**change))


def test_rejects_non_object():
    with pytest.raises(InputError):
        parse_request([])


def test_parses_defaults_and_custom_sizes():
    room, pieces, preset, notes, seed, preferences = parse_request(make_request(
        furniture=[{"type": "bed", "count": 2, "width": 4.5, "depth": ""}, {"type": "desk", "count": "1"}],
        notes="  hello ",
    ))
    assert (room.width, room.length) == (16, 14)
    assert [p.label for p in pieces] == ["Bed 1", "Bed 2", "Desk"]
    assert pieces[0].width == 4.5 and pieces[0].depth == FURNITURE_TYPES["bed"]["depth"]
    assert preset == "default" and notes == "hello" and seed == 7
    assert preferences is None


# --- generated layouts ------------------------------------------------------------------------------------

@pytest.mark.parametrize("preset", list(PRESETS))
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_layouts_satisfy_hard_constraints(preset, seed):
    layout = generate_layout(make_request(preset=preset, seed=seed))
    room = Room(16, 14, [Opening("door", **DOOR)])
    door_zone = room.opening_zone(room.doors[0], DOOR["width"])
    boxes = rects(layout)

    assert len(boxes) == 4
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        assert x0 >= -1e-6 and y0 >= -1e-6 and x1 <= 16 + 1e-6 and y1 <= 14 + 1e-6
        assert overlap_area(boxes[i], door_zone) < 1e-6
        for other in boxes[i + 1:]:
            assert overlap_area(boxes[i], other) < 1e-6


def test_layout_in_a_comfortable_room_has_no_warnings():
    layout = generate_layout(make_request())
    assert layout["warnings"] == []
    assert layout["metrics"]["unreachable"] == []
    # Furniture that belongs against a wall ends up there
    for f in layout["furniture"]:
        x0, y0, x1, y1 = rects({"furniture": [f]})[0]
        assert min(x0, y0, 16 - x1, 14 - y1) < 0.1, f


def test_same_seed_gives_same_layout():
    assert generate_layout(make_request(seed=42)) == generate_layout(make_request(seed=42))


def test_seed_is_reported_when_not_given():
    layout = generate_layout(make_request(seed=None))
    assert isinstance(layout["seed"], int)
    assert generate_layout(make_request(seed=layout["seed"]))["furniture"] == layout["furniture"]


def test_child_safe_keeps_a_play_area():
    layout = generate_layout(make_request(preset="child_safe"))
    assert layout["metrics"]["openSpace"]["radius"] >= PRESETS["child_safe"]["min_play_radius"]


def test_shared_preset_spreads_beds_and_groups_desks():
    request = make_request(
        preset="shared",
        room={"width": 24, "length": 20, "doors": [DOOR]},
        furniture=[{"type": "bed", "count": 4}, {"type": "desk", "count": 4}],
    )
    shared = generate_layout(request)
    terms = shared["metrics"]["terms"]
    assert -terms["privacy"] >= 6  # nearest two beds at least 6 ft apart (centre to centre)
    assert terms["desk_group"] < 10  # desks on average under 10 ft apart


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_tight_room_returns_a_valid_layout_with_warnings(seed):
    # Fits, but not with 36 in walkways and 5 ft turning space: expect warnings, not an error
    layout = generate_layout(make_request(preset="accessible", seed=seed, room={"width": 10, "length": 11, "doors": [DOOR]}))
    assert layout["warnings"]
    boxes = rects(layout)
    for i, box in enumerate(boxes):
        for other in boxes[i + 1:]:
            assert overlap_area(box, other) < 1e-6


def test_furniture_that_cannot_fit_raises():
    with pytest.raises(PlacementError):
        generate_layout(make_request(
            room={"width": 10, "length": 10, "doors": [DOOR]},
            furniture=[{"type": "sofa", "count": 1, "width": 15, "depth": 3}],
        ))


# --- scoring ----------------------------------------------------------------------------------------------

def room_with_bed_across(width):
    """A bed laid across the room against the left wall, facing the gap beside it; a desk sits behind the bed."""
    room = Room(width, 20, [Opening("door", "bottom", 2.5, 3)])
    pieces = [Piece("bed-1", "bed", "Bed", 5, 6.5), Piece("desk-1", "desk", "Desk", 4, 2)]
    placements = [Placement(3.25, 10, 90), Placement(width / 2, 19, 180)]
    return room, pieces, placements


def test_scorer_flags_pieces_behind_a_narrow_gap():
    # 8 ft room: an 18 in gap beside the bed, too narrow for a 30 in walkway
    room, pieces, placements = room_with_bed_across(8)
    result = Scorer(room, pieces, "default").evaluate(placements)
    assert not result.hard_violation
    assert set(result.unreachable) == {"bed-1", "desk-1"}

    # 10 ft room: a 42 in gap is wide enough
    room, pieces, placements = room_with_bed_across(10)
    assert Scorer(room, pieces, "default").evaluate(placements).unreachable == []


def test_scorer_flags_overlap_and_door_blocking():
    room = Room(12, 12, [Opening("door", "bottom", 1, 3)])
    pieces = [Piece("a", "desk", "A", 4, 2), Piece("b", "desk", "B", 4, 2)]
    overlapping = Scorer(room, pieces, "default").evaluate([Placement(6, 6, 0), Placement(7, 6, 0)])
    assert overlapping.terms["overlap"] == pytest.approx(6.0)
    blocking = Scorer(room, pieces, "default").evaluate([Placement(2.5, 1, 0), Placement(9, 9, 0)])
    assert blocking.terms["door"] > 0 and blocking.hard_violation


def test_accessible_preset_needs_more_room_in_front():
    room = Room(12, 12, [Opening("door", "bottom", 1, 3)])
    pieces = [Piece("bed-1", "bed", "Bed", 5, 6.5), Piece("wardrobe-1", "wardrobe", "Wardrobe", 4, 2)]
    # The wardrobe faces the bed's foot from 4 ft away
    placements = [Placement(6, 8.75, 180), Placement(6, 1, 0)]
    assert overlap_area(footprint(pieces[0], placements[0]), footprint(pieces[1], placements[1])) == 0
    assert Scorer(room, pieces, "default").evaluate(placements).cramped == []
    assert set(Scorer(room, pieces, "accessible").evaluate(placements).cramped) == {"bed-1", "wardrobe-1"}


# --- command line -----------------------------------------------------------------------------------------

def run_cli(args, payload=None):
    proc = subprocess.run(
        [sys.executable, os.path.join(SERVER_DIR, "placement_generation.py"), *args],
        input="" if payload is None else json.dumps(payload),
        capture_output=True, text=True, timeout=120,
    )
    return proc.returncode, json.loads(proc.stdout.strip().splitlines()[-1])


def test_cli_describe_matches_catalog():
    code, options = run_cli(["--describe"])
    assert code == 0
    assert options == json.loads(json.dumps(describe()))
    assert set(options["presets"]) == set(PRESETS)


def test_cli_generates_layout():
    code, layout = run_cli([], make_request())
    assert code == 0
    assert {f["type"] for f in layout["furniture"]} == {"bed", "desk", "tv", "wardrobe"}


@pytest.mark.parametrize("payload, expected_code", [
    (make_request(furniture=[]), 2),
    (make_request(room={"width": 10, "length": 10, "doors": [DOOR]},
                  furniture=[{"type": "sofa", "count": 1, "width": 15, "depth": 3}]), 3),
])
def test_cli_reports_errors(payload, expected_code):
    code, result = run_cli([], payload)
    assert code == expected_code
    assert result["error"]
