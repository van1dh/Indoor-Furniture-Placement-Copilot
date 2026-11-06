"""Furniture layout engine: validate a request, search for a layout and describe the result."""
import random

from .catalog import FURNITURE_TYPES, PRESETS, describe
from .model import FACING, footprint_size, front_point
from .optimizer import Optimizer, PlacementError
from .request import InputError, parse_request

__all__ = ["InputError", "PlacementError", "describe", "generate_layout"]


def _warnings(room, pieces, preset_name, evaluation, scorer):
    preset = PRESETS[preset_name]
    labels = {p.id: p.label for p in pieces}
    walkway_in = round(preset["agent_radius"] * 2 * 12)
    warnings = []
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
    if evaluation.terms["window"] > 0.1:
        warnings.append("A tall piece of furniture partly blocks a window.")
    return warnings


def generate_layout(request):
    """Return a JSON-ready layout for a request, or raise InputError / PlacementError."""
    room, pieces, preset_name, notes, seed = parse_request(request)
    if seed is None:
        seed = random.randrange(2 ** 31)

    optimizer = Optimizer(room, pieces, preset_name, random.Random(seed))
    placements, evaluation = optimizer.run()
    scorer = optimizer.scorer

    furniture = []
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

    return {
        "room": room.to_dict(),
        "furniture": furniture,
        "preset": preset_name,
        "notes": notes,
        "seed": seed,
        "metrics": {
            "openSpace": {
                "x": round(evaluation.open_center[0], 3),
                "y": round(evaluation.open_center[1], 3),
                "radius": round(evaluation.open_radius, 3),
            },
            "walkwayWidth": PRESETS[preset_name]["agent_radius"] * 2,
            "unreachable": evaluation.unreachable,
            "cramped": evaluation.cramped,
            "score": round(evaluation.total, 2),
            "terms": {k: round(v, 3) for k, v in evaluation.terms.items() if scorer.weights[k]},
        },
        "warnings": _warnings(room, pieces, preset_name, evaluation, scorer),
    }

