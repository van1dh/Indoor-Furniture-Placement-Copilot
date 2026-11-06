import json
import math
import os
import subprocess
import sys
from types import SimpleNamespace

import anthropic
import pytest

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SERVER_DIR)

from layout import Copilot, InputError, generate_layout, refine_layout  # noqa: E402
from layout import flow, preferences as prefs  # noqa: E402
from layout.copilot import MODEL, keyword_preset  # noqa: E402
from layout.model import Opening, Piece, Placement, Room  # noqa: E402
from layout.optimizer import Optimizer  # noqa: E402
from layout.scoring import Scorer  # noqa: E402

DOOR = {"wall": "bottom", "offset": 1, "width": 3}
WINDOW = {"wall": "top", "offset": 5, "width": 5}


def make_request(**overrides):
    request = {
        "preset": "default",
        "room": {"width": 16, "length": 14, "doors": [DOOR], "windows": [WINDOW]},
        "furniture": [{"type": "bed", "count": 1}, {"type": "desk", "count": 1},
                      {"type": "tv", "count": 1}, {"type": "wardrobe", "count": 1}],
        "seed": 7,
    }
    request.update(overrides)
    return request


class FakeMessages:
    """Stands in for client.beta.messages: replays canned answers and records each call."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        if answer == "REFUSAL":
            return SimpleNamespace(stop_reason="refusal", content=[])
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


def fake_copilot(*answers):
    messages = FakeMessages(answers)
    return Copilot(client=SimpleNamespace(beta=SimpleNamespace(messages=messages))), messages


def pref(kind, piece, target, strength="high"):
    return {"kind": kind, "piece": piece, "target": target, "strength": strength, "reason": "test"}


# --- preferences --------------------------------------------------------------------------------------------

def test_preference_costs():
    room = Room(12, 12, [Opening("door", "bottom", 1, 3)], [Opening("window", "top", 4, 4)])
    pieces = [Piece("bed-1", "bed", "Bed", 5, 6.5), Piece("desk-1", "desk", "Desk", 4, 2)]
    under_window = [Placement(6, 8.75, 180), Placement(9, 1, 0)]
    far_from_window = [Placement(6, 3.25, 0), Placement(9, 11, 180)]
    near = [pref("near", "bed", "window")]
    against = [pref("against_wall", "desk", "wall:bottom")]
    away = [pref("away", "desk", "door")]

    assert prefs.evaluate(near, room, pieces, under_window)[1] == [True]
    assert prefs.evaluate(near, room, pieces, far_from_window)[1] == [False]
    assert prefs.evaluate(near, room, pieces, far_from_window)[0] > prefs.evaluate(near, room, pieces, under_window)[0]
    assert prefs.evaluate(against, room, pieces, under_window)[1] == [True]
    assert prefs.evaluate(against, room, pieces, far_from_window)[1] == [False]
    assert prefs.evaluate(away, room, pieces, far_from_window)[1] == [True]


def test_normalize_validates_and_skips_missing_furniture():
    pieces = [Piece("bed-1", "bed", "Bed", 5, 6.5)]
    valid, dropped = prefs.normalize([pref("near", "bed", "window"), pref("near", "sofa", "window")], pieces)
    assert [p["piece"] for p in valid] == ["bed"]
    assert len(dropped) == 1 and "sofa" in dropped[0]
    for bad in [pref("against_wall", "bed", "window"), pref("near", "bed", "ceiling"), {"kind": "near"}, "x"]:
        with pytest.raises(prefs.PreferenceError):
            prefs.normalize([bad], pieces)


def test_request_preferences_shape_the_layout():
    layout = generate_layout(make_request(preferences=[pref("near", "bed", "window")]))
    assert layout["preferences"][0]["met"] is True
    assert layout["preferences"][0]["text"] == "Bed near the window"


@pytest.mark.parametrize("bad", [[pref("near", "bed", "ceiling")], "bed by the window"])
def test_invalid_request_preferences_are_rejected(bad):
    with pytest.raises(InputError):
        generate_layout(make_request(preferences=bad))


# --- traffic ------------------------------------------------------------------------------------------------

def test_traffic_follows_walkways():
    layout = generate_layout(make_request())
    traffic = layout["flow"]
    assert traffic["occupants"] == 1 and traffic["missedTrips"] == 0
    assert traffic["dailyDistance"] > 10
    assert traffic["maxCount"] >= 1
    boxes = [(f["x"] - f["footprint"]["width"] / 2, f["y"] - f["footprint"]["length"] / 2,
              f["x"] + f["footprint"]["width"] / 2, f["y"] + f["footprint"]["length"] / 2) for f in layout["furniture"]]
    for x, y, _ in traffic["cells"]:
        assert 0 <= x <= 16 and 0 <= y <= 14
        assert not any(b[0] < x < b[2] and b[1] < y < b[3] for b in boxes), "path goes through furniture"


def test_traffic_counts_trips_that_cannot_be_walked():
    room = Room(8, 20, [Opening("door", "bottom", 2.5, 3)])
    pieces = [Piece("bed-1", "bed", "Bed", 5, 6.5), Piece("desk-1", "desk", "Desk", 4, 2)]
    placements = [Placement(3.25, 10, 90), Placement(4, 19, 180)]
    traffic = flow.simulate(Scorer(room, pieces, "default"), placements)
    assert traffic["missedTrips"] > 0


# --- copilot ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, preset", [
    ("We have a toddler", "child_safe"),
    ("家里有个宝宝", "child_safe"),
    ("My dad uses a wheelchair", "accessible"),
    ("四个同学合租", "shared"),
    ("I like plants", None),
])
def test_keyword_presets(text, preset):
    assert keyword_preset(text) == preset


def test_generate_uses_claude_for_notes_and_explanation():
    copilot, messages = fake_copilot(
        {"preset": "child_safe",
         "preferences": [pref("near", "bed", "window"), pref("near", "sofa", "door"),
                         pref("against_wall", "desk", "window")],
         "reply": "Child-safe, with the bed by the window."},
        "The bed sits under the window and the play area is in the middle.",
    )
    layout = generate_layout(make_request(preset="auto", notes="Toddler at home; bed by the window please"), copilot)

    assert layout["preset"] == "child_safe"
    assert [p["text"] for p in layout["preferences"]] == ["Bed near the window"]  # sofa absent, bad wall target
    assert layout["preferences"][0]["met"]
    assert layout["copilot"] == {
        "online": True,
        "offlineReason": None,
        "reply": "Child-safe, with the bed by the window.",
        "explanation": "The bed sits under the window and the play area is in the middle.",
        "notices": ["There is no sofa in this room, so “Sofa near the door” was skipped."],
    }
    # The resolved request reproduces the layout without asking Claude again
    assert layout["request"]["preset"] == "child_safe"
    assert generate_layout(layout["request"], Copilot())["furniture"] == layout["furniture"]

    interpret, explain = messages.calls
    for call in (interpret, explain):
        assert call["model"] == MODEL
        assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
        assert call["output_config"]["effort"] == "low"
    assert interpret["output_config"]["format"]["type"] == "json_schema"
    assert "Toddler at home" in interpret["messages"][-1]["content"]
    assert "format" not in explain["output_config"]


def test_explicit_preset_is_kept_when_claude_suggests_another():
    copilot, _ = fake_copilot({"preset": "shared", "preferences": [], "reply": "ok"}, "Explained.")
    assert generate_layout(make_request(preset="accessible", notes="roommates"), copilot)["preset"] == "accessible"


def test_refusal_falls_back_to_keywords():
    copilot, messages = fake_copilot("REFUSAL", "Explained anyway.")
    layout = generate_layout(make_request(preset="auto", notes="We have a toddler"), copilot)
    assert layout["preset"] == "child_safe"
    assert "declined" in layout["copilot"]["notices"][0]
    assert layout["copilot"]["explanation"] == "Explained anyway."


def test_missing_credentials_switch_the_copilot_off():
    copilot, messages = fake_copilot(anthropic.AnthropicError("no credentials"))
    layout = generate_layout(make_request(preset="auto", notes="wheelchair user"), copilot)
    assert layout["preset"] == "accessible"
    assert layout["copilot"]["online"] is False
    assert layout["copilot"]["offlineReason"] == "no Claude API credentials are configured"
    assert layout["copilot"]["notices"] == []
    assert len(messages.calls) == 1  # no second call for the explanation
    assert layout["copilot"]["explanation"].startswith("This is a Wheelchair accessible layout")


def test_offline_copilot_explains_from_template():
    layout = generate_layout(make_request())
    copilot = layout["copilot"]
    assert copilot["online"] is False and copilot["reply"] is None
    assert "ft of walking" in copilot["explanation"]


# --- refine -------------------------------------------------------------------------------------------------

def test_refine_applies_new_preference_and_keeps_the_rest_in_place():
    first = generate_layout(make_request(seed=3))
    copilot, messages = fake_copilot(
        {"preset": None, "preferences": [pref("near", "desk", "window")], "reply": "Moved the desk to the window."},
        "Explained.",
    )
    history = [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "hello"}]
    refined = refine_layout(
        {"request": first["request"], "layout": first, "message": "desk by the window", "history": history}, copilot)

    assert refined["copilot"]["reply"] == "Moved the desk to the window."
    assert refined["preferences"][0]["met"]
    assert refined["request"]["preferences"][0]["piece"] == "desk"
    before = {f["id"]: f for f in first["furniture"]}
    moved = [math.hypot(f["x"] - before[f["id"]]["x"], f["y"] - before[f["id"]]["y"])
             for f in refined["furniture"] if f["type"] != "desk"]
    assert sum(d < 0.5 for d in moved) >= 2, moved  # most other pieces stay put

    call = messages.calls[0]
    assert [m["role"] for m in call["messages"]] == ["user", "assistant", "user"]
    assert "current_layout" in call["messages"][-1]["content"]


def test_refine_without_copilot_changes_nothing():
    first = generate_layout(make_request(seed=3))
    refined = refine_layout({"request": first["request"], "layout": first, "message": "move the bed", "history": []})
    assert refined["furniture"] == first["furniture"]
    assert refined["copilot"]["online"] is False


def test_warm_start_keeps_a_good_layout():
    first = generate_layout(make_request(seed=5))
    from layout.request import parse_request
    room, pieces, preset, _, seed, _ = parse_request(first["request"])
    initial = [Placement(f["x"], f["y"], f["rotation"]) for f in first["furniture"]]
    import random
    placements, _ = Optimizer(room, pieces, preset, random.Random(1), restarts=1, iterations=300,
                              initial=initial).run()
    assert all(math.hypot(a.x - b.x, a.y - b.y) < 0.5 for a, b in zip(placements, initial))


@pytest.mark.parametrize("payload", [
    {},
    {"request": make_request(), "message": ""},
    {"request": make_request(), "message": "x", "history": [{"role": "assistant", "text": "hi"}]},
    {"request": make_request(), "message": "x", "history": [{"role": "user", "text": "hi"}]},
    {"request": make_request(), "message": "x", "layout": {"furniture": [{"id": "bed-1", "x": 1, "y": 1, "rotation": 45}]}},
])
def test_refine_rejects_invalid_payloads(payload):
    with pytest.raises(InputError):
        refine_layout(payload)


def test_cli_refine():
    first = generate_layout(make_request())
    env = {**os.environ, "COPILOT_OFFLINE": "1"}
    proc = subprocess.run(
        [sys.executable, os.path.join(SERVER_DIR, "placement_generation.py"), "--refine"],
        input=json.dumps({"request": first["request"], "layout": first, "message": "hello", "history": []}),
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["furniture"] == first["furniture"]


def test_cli_reads_non_ascii_notes_as_utf8():
    env = {**os.environ, "COPILOT_OFFLINE": "1", "PYTHONIOENCODING": ""}
    proc = subprocess.run(
        [sys.executable, os.path.join(SERVER_DIR, "placement_generation.py")],
        input=json.dumps(make_request(preset="auto", notes="家里有个宝宝"), ensure_ascii=False).encode("utf-8"),
        capture_output=True, timeout=120, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    layout = json.loads(proc.stdout)
    assert layout["preset"] == "child_safe"
    assert layout["notes"] == "家里有个宝宝"
