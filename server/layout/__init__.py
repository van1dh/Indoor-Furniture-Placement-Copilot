"""Furniture layout engine: validate a request, search for a layout and describe the result."""
import random

from . import flow
from . import preferences as prefs
from .catalog import AUTO_PRESET, DEFAULT_PRESET, FURNITURE_TYPES, PRESETS, describe
from .copilot import Copilot, template_explanation
from .model import FACING, back_wall_distance, footprint, footprint_size, front_point, outside_area, overlap_area
from .optimizer import Optimizer, PlacementError
from .request import InputError, parse_evaluation, parse_refinement, parse_request
from .scoring import Scorer

__all__ = [
    "Copilot", "InputError", "PlacementError", "describe", "evaluate_layout", "generate_layout", "refine_layout"]

WALL_BY_ROTATION = {0: "bottom", 180: "top", 90: "left", 270: "right"}  # the wall behind a piece


def _hard_warnings(room, pieces, placements, scorer):
    """Overlaps and blocked doors; only layouts arranged by hand can have them."""
    rects = [footprint(p, pl) for p, pl in zip(pieces, placements)]
    warnings = []
    for i, a in enumerate(rects):
        if outside_area(a, room) > 0.01:
            warnings.append(f"{pieces[i].label} sticks out of the room.")
        for j in range(i + 1, len(rects)):
            if overlap_area(a, rects[j]) > 0.01:
                warnings.append(f"{pieces[i].label} overlaps {pieces[j].label}.")
        if any(overlap_area(a, zone) > 0.01 for zone in scorer.door_zones):
            warnings.append(f"{pieces[i].label} blocks a door from opening.")
    return warnings


def _warnings(room, pieces, placements, preset_name, evaluation, scorer, traffic):
    preset = PRESETS[preset_name]
    labels = {p.id: p.label for p in pieces}
    walkway_in = round(preset["agent_radius"] * 2 * 12)
    warnings = _hard_warnings(room, pieces, placements, scorer) if evaluation.hard_violation else []
    for piece_id in evaluation.unreachable:
        warnings.append(f"{labels[piece_id]} cannot be reached from a door with a {walkway_in} in walkway.")
    for piece_id in evaluation.cramped:
        i = next(i for i, p in enumerate(pieces) if p.id == piece_id)
        warnings.append(f"{labels[piece_id]} has less than {scorer.front_depths[i]:g} ft of free floor in front of it.")
    min_play = preset.get("min_play_radius")
    if min_play and evaluation.open_radius < min_play:
        warnings.append(
            f"The largest open play area is {evaluation.open_radius * 2:.1f} ft across; "
            f"{min_play * 2:g} ft is recommended.")
    if min_play and traffic["playAreaDistance"] >= 3:
        warnings.append(f"Daily walking routes cross the play area (about {traffic['playAreaDistance']:g} ft a day).")
    if evaluation.terms["window"] > 0.1:
        warnings.append("A tall piece of furniture partly blocks a window.")
    return warnings


def _layout(request, room, pieces, preset_name, notes, seed, preferences, placements, evaluation, scorer,
            copilot, reply, notices, explain=True):
    furniture = []
    summary_pieces = []
    for piece, placement in zip(pieces, placements):
        w, h = footprint_size(piece, placement.rotation)
        fx, fy = front_point(piece, placement, 0)
        furniture.append({
            "id": piece.id,
            "type": piece.type,
            "label": piece.label,
            "x": round(placement.x, 3),
            "y": round(placement.y, 3),
            "width": piece.width,
            "depth": piece.depth,
            "rotation": placement.rotation,
            "footprint": {"width": w, "length": h},
            "front": {"x": round(fx, 3), "y": round(fy, 3), "direction": list(FACING[placement.rotation])},
            "tall": FURNITURE_TYPES[piece.type]["tall"],
        })
        against = back_wall_distance(piece, placement, room) < 0.1
        summary_pieces.append({
            "label": piece.label,
            "center_ft": [round(placement.x, 1), round(placement.y, 1)],
            "wall": WALL_BY_ROTATION[placement.rotation] if against else None,
            "faces": {0: "up", 90: "right", 180: "down", 270: "left"}[placement.rotation],
        })

    traffic = flow.simulate(scorer, placements, (evaluation.open_center, evaluation.open_radius))
    warnings = _warnings(room, pieces, placements, preset_name, evaluation, scorer, traffic)
    preference_status = [
        {**p, "met": met, "text": prefs.describe(p)} for p, met in zip(preferences, evaluation.preferences_met)]
    metrics = {
        "openSpace": {
            "x": round(evaluation.open_center[0], 3),
            "y": round(evaluation.open_center[1], 3),
            "radius": round(evaluation.open_radius, 3),
        },
        "walkwayWidth": PRESETS[preset_name]["agent_radius"] * 2,
        "unreachable": evaluation.unreachable,
        "cramped": evaluation.cramped,
        "score": round(evaluation.total, 2),
        "valid": not evaluation.hard_violation,  # no overlaps, nothing outside the room or in a door's way
        "terms": {k: round(v, 3) for k, v in evaluation.terms.items() if scorer.weights[k] and v},
    }

    summary = {
        "room": f"{room.width:g} x {room.length:g} ft room",
        "preset": PRESETS[preset_name]["label"],
        "notes": notes,
        "doors": [f"{d.width:g} ft on the {d.wall} wall" for d in room.doors],
        "windows": [f"{w.width:g} ft on the {w.wall} wall" for w in room.windows],
        "furniture": summary_pieces,
        "preferences": [{"text": p["text"], "met": p["met"]} for p in preference_status],
        "metrics": {
            "openAreaFeet": round(evaluation.open_radius * 2, 1),
            "walkwayInches": round(metrics["walkwayWidth"] * 12),
            "dailyWalkFeet": traffic["dailyDistance"],
        },
        "warnings": warnings,
    }

    # What to send back to regenerate or refine this layout without asking the copilot again
    resolved = {k: v for k, v in request.items() if k not in ("preset", "preferences", "seed")}
    resolved.update({"preset": preset_name, "preferences": [dict(p) for p in preferences], "seed": seed})
    return {
        "room": room.to_dict(),
        "furniture": furniture,
        "preset": preset_name,
        "notes": notes,
        "seed": seed,
        "metrics": metrics,
        "warnings": warnings,
        "preferences": preference_status,
        "flow": traffic,
        "copilot": {
            "explanation": copilot.explain(summary) if explain else template_explanation(summary),
            "online": copilot.online,
            "offlineReason": copilot.offline_reason,
            "provider": copilot.provider.name if copilot.provider else None,
            "model": copilot.model,
            "reply": reply,
            "notices": notices,
        },
        "request": resolved,
    }


def generate_layout(request, copilot=None):
    """Return a JSON-ready layout for a request, or raise InputError / PlacementError."""
    copilot = copilot or Copilot()
    room, pieces, preset_name, notes, seed, preferences = parse_request(request)
    if seed is None:
        seed = random.randrange(2 ** 31)

    reply, notices = None, []
    if preferences is None:
        preferences = []
        if notes:
            current = DEFAULT_PRESET if preset_name == AUTO_PRESET else preset_name
            interpretation = copilot.interpret(notes, room, pieces, current, [])
            preferences, reply, notices = interpretation.preferences, interpretation.reply, interpretation.notices
            if preset_name == AUTO_PRESET:
                preset_name = interpretation.preset or DEFAULT_PRESET
    if preset_name == AUTO_PRESET:
        preset_name = DEFAULT_PRESET

    optimizer = Optimizer(room, pieces, preset_name, random.Random(seed), preferences=preferences)
    placements, evaluation = optimizer.run()
    return _layout(request, room, pieces, preset_name, notes, seed, preferences, placements, evaluation,
                   optimizer.scorer, copilot, reply, notices)


def refine_layout(payload, copilot=None):
    """Change an existing layout according to a chat message, moving as little else as possible."""
    copilot = copilot or Copilot()
    request, initial_by_id, message, history = parse_refinement(payload)
    room, pieces, preset_name, notes, seed, preferences = parse_request(request)
    if preset_name == AUTO_PRESET:
        preset_name = DEFAULT_PRESET
    if seed is None:
        seed = random.randrange(2 ** 31)
    initial = [initial_by_id.get(p.id) for p in pieces]
    layout = [
        {"piece": p.label, "center_ft": [round(pl.x, 1), round(pl.y, 1)], "rotation": pl.rotation}
        for p, pl in zip(pieces, initial) if pl is not None
    ]

    interpretation = copilot.interpret(message, room, pieces, preset_name, preferences or [], history, layout)
    preset_name = interpretation.preset or preset_name
    preferences = interpretation.preferences

    optimizer = Optimizer(room, pieces, preset_name, random.Random(seed), restarts=2, iterations=900,
                          preferences=preferences, initial=initial if any(initial) else None)
    placements, evaluation = optimizer.run()
    return _layout(request, room, pieces, preset_name, notes, seed, preferences, placements, evaluation,
                   optimizer.scorer, copilot, interpretation.reply, interpretation.notices)


def evaluate_layout(payload, copilot=None):
    """Score a layout arranged by hand without moving anything (and without asking Claude, since this runs on
    every drag)."""
    copilot = copilot or Copilot()
    request, placements_by_id = parse_evaluation(payload)
    room, pieces, preset_name, notes, seed, preferences = parse_request(request)
    if preset_name == AUTO_PRESET:
        preset_name = DEFAULT_PRESET
    missing = [p.label for p in pieces if p.id not in placements_by_id]
    if missing:
        raise InputError(f"layout does not place {', '.join(missing)}")
    placements = [placements_by_id[p.id] for p in pieces]
    preferences = preferences or []
    scorer = Scorer(room, pieces, preset_name, preferences)
    evaluation = scorer.evaluate(placements)
    return _layout(request, room, pieces, preset_name, notes, seed, preferences, placements, evaluation, scorer,
                   copilot, None, [], explain=False)
