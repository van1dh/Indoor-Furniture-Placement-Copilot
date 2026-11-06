"""HTTP API tests (the copilot is offline, see conftest.py)."""
import pytest
from fastapi.testclient import TestClient

from app import app

REQUEST = {
    "preset": "default",
    "room": {
        "width": 16,
        "length": 14,
        "doors": [{"wall": "bottom", "offset": 1, "width": 3}],
        "windows": [{"wall": "top", "offset": 5, "width": 5}],
    },
    "furniture": [{"type": "bed", "count": 1}, {"type": "desk", "count": 1}],
    "notes": "api test",
    "seed": 3,
}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def layout(client):
    res = client.post("/api/generate", json=REQUEST)
    assert res.status_code == 200
    return res.json()


def placements(layout):
    return [{k: f[k] for k in ("id", "x", "y", "rotation")} for f in layout["furniture"]]


def test_serves_the_form_options(client):
    res = client.get("/api/options")
    assert res.status_code == 200
    options = res.json()
    assert options["furniture"]["bed"]["width"] > 0
    assert sorted(options["presets"]) == ["accessible", "child_safe", "default", "shared"]
    assert options["defaults"]["room"]["doors"]


def test_generates_a_layout(layout):
    assert [f["type"] for f in layout["furniture"]] == ["bed", "desk"]
    assert layout["room"]["width"] == 16
    assert layout["seed"] == 3
    assert layout["notes"] == "api test"
    assert isinstance(layout["warnings"], list)
    assert layout["copilot"]["online"] is False
    assert layout["copilot"]["explanation"]
    assert layout["flow"]["dailyDistance"] > 0
    assert layout["metrics"]["valid"] is True
    assert layout["request"]["seed"] == 3


def test_applies_preferences_and_refines_a_layout(client):
    preferences = [{"kind": "near", "piece": "bed", "target": "window", "strength": "high"}]
    layout = client.post("/api/generate", json={**REQUEST, "preferences": preferences}).json()
    assert layout["preferences"][0]["met"] is True

    res = client.post("/api/refine", json={
        "request": layout["request"], "layout": layout, "message": "move the desk", "history": []})
    assert res.status_code == 200
    body = res.json()
    assert body["furniture"] == layout["furniture"]  # offline: nothing to change
    assert body["copilot"]["reply"]


def test_evaluates_a_layout_arranged_by_hand(client, layout):
    res = client.post("/api/evaluate", json={"request": layout["request"], "layout": {"furniture": placements(layout)}})
    assert res.status_code == 200
    same = res.json()
    assert same["furniture"] == layout["furniture"]
    assert same["metrics"]["score"] == layout["metrics"]["score"]

    # Drop the desk on top of the bed
    moved = placements(layout)
    moved[1].update(x=moved[0]["x"], y=moved[0]["y"])
    body = client.post("/api/evaluate", json={"request": layout["request"], "layout": {"furniture": moved}}).json()
    assert body["metrics"]["valid"] is False
    assert "Bed overlaps Desk." in body["warnings"]
    assert body["furniture"][1]["x"] == moved[1]["x"]


def test_rejects_an_incomplete_evaluate_request(client, layout):
    for body in [
        {"layout": {"furniture": placements(layout)}},
        {"request": layout["request"], "layout": {"furniture": placements(layout)[:1]}},
        {"request": layout["request"], "layout": {"furniture": [{**placements(layout)[0], "rotation": 45}]}},
        {"request": layout["request"], "layout": "nope"},
    ]:
        res = client.post("/api/evaluate", json=body)
        assert res.status_code == 400, body
        assert res.json()["error"]


def test_rejects_an_invalid_refine_request(client):
    res = client.post("/api/refine", json={"request": REQUEST, "message": ""})
    assert res.status_code == 400


def test_ignores_fields_outside_the_request_schema(client):
    res = client.post("/api/generate", json={**REQUEST, "extra": "x" * 100})
    assert res.status_code == 200
    assert "extra" not in res.json()["request"]


@pytest.mark.parametrize("body", [
    {},
    {**REQUEST, "furniture": []},
    {**REQUEST, "preset": "nope"},
    {**REQUEST, "room": {**REQUEST["room"], "width": -1}},
    {**REQUEST, "furniture": [{"type": "sofa", "count": 1, "width": 15, "depth": 3}],
     "room": {**REQUEST["room"], "width": 10, "length": 10}},
])
def test_rejects_invalid_input_with_400_and_a_message(client, body):
    res = client.post("/api/generate", json=body)
    assert res.status_code == 400
    assert res.json()["error"]


def test_rejects_bodies_that_are_not_json_objects(client):
    assert client.post("/api/generate", content=b"not json").status_code == 400
    assert client.post("/api/generate", json=[1, 2]).status_code == 400
    assert client.post("/api/generate", content=b"{" + b" " * 200_000 + b"}").status_code == 413


def test_allows_the_dev_frontend_origin(client):
    res = client.get("/api/options", headers={"Origin": "http://localhost:3000"})
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"
