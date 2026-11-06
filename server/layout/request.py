"""Validate a layout request and turn it into model objects."""
import math

from .catalog import FURNITURE_TYPES, LIMITS, PRESETS, DEFAULT_PRESET, WALLS
from .model import Opening, Piece, Room


class InputError(ValueError):
    pass


def _number(value, name, low, high):
    if isinstance(value, bool) or value in ("", None):
        raise InputError(f"{name} is required")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise InputError(f"{name} must be a number")
    if not math.isfinite(number) or not low <= number <= high:
        raise InputError(f"{name} must be between {low:g} and {high:g}")
    return number


def _count(value, name):
    if value in ("", None):
        return 0
    if isinstance(value, bool):
        raise InputError(f"{name} must be a whole number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise InputError(f"{name} must be a whole number")
    if not number.is_integer():
        raise InputError(f"{name} must be a whole number")
    if not 0 <= number <= LIMITS["max_per_type"]:
        raise InputError(f"{name} must be between 0 and {LIMITS['max_per_type']}")
    return int(number)


def _openings(items, kind, room_width, room_length, max_count):
    if items is None:
        return []
    if not isinstance(items, list):
        raise InputError(f"{kind}s must be a list")
    if len(items) > max_count:
        raise InputError(f"At most {max_count} {kind}s are supported")

    openings = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise InputError(f"{kind.capitalize()} {i} must be an object")
        wall = item.get("wall")
        if wall not in WALLS:
            raise InputError(f"{kind.capitalize()} {i}: wall must be one of {', '.join(WALLS)}")
        wall_length = room_width if wall in ("bottom", "top") else room_length
        width = _number(item.get("width"), f"{kind.capitalize()} {i} width", LIMITS["opening_min"], LIMITS["opening_max"])
        offset = _number(item.get("offset"), f"{kind.capitalize()} {i} offset", 0, LIMITS["room_max"])
        if offset + width > wall_length + 1e-9:
            raise InputError(f"{kind.capitalize()} {i} does not fit on the {wall} wall ({wall_length:g} ft long)")
        openings.append(Opening(kind, wall, offset, width))
    return openings


def parse_request(request):
    """Return (room, pieces, preset_name, notes, seed) or raise InputError."""
    if not isinstance(request, dict):
        raise InputError("Request must be a JSON object")

    preset = request.get("preset") or DEFAULT_PRESET
    if preset not in PRESETS:
        raise InputError(f"Unknown preset '{preset}'")

    room_data = request.get("room")
    if not isinstance(room_data, dict):
        raise InputError("room is required")
    width = _number(room_data.get("width"), "Room width", LIMITS["room_min"], LIMITS["room_max"])
    length = _number(room_data.get("length"), "Room length", LIMITS["room_min"], LIMITS["room_max"])
    doors = _openings(room_data.get("doors"), "door", width, length, LIMITS["max_doors"])
    windows = _openings(room_data.get("windows"), "window", width, length, LIMITS["max_windows"])
    if not doors:
        raise InputError("Add at least one door")
    room = Room(width, length, doors, windows)

    furniture = request.get("furniture")
    if not isinstance(furniture, list):
        raise InputError("furniture must be a list")
    pieces = []
    seen = set()
    for item in furniture:
        if not isinstance(item, dict) or item.get("type") not in FURNITURE_TYPES:
            raise InputError(f"Unknown furniture type '{item.get('type') if isinstance(item, dict) else item}'")
        kind = item["type"]
        if kind in seen:
            raise InputError(f"'{kind}' is listed more than once")
        seen.add(kind)
        spec = FURNITURE_TYPES[kind]
        count = _count(item.get("count"), f"{spec['label']} count")
        if count == 0:
            continue
        piece_width = spec["width"] if item.get("width") in ("", None) else _number(
            item["width"], f"{spec['label']} width", LIMITS["furniture_min"], LIMITS["furniture_max"])
        piece_depth = spec["depth"] if item.get("depth") in ("", None) else _number(
            item["depth"], f"{spec['label']} depth", LIMITS["furniture_min"], LIMITS["furniture_max"])
        for n in range(count):
            label = spec["label"] if count == 1 else f"{spec['label']} {n + 1}"
            pieces.append(Piece(f"{kind}-{n + 1}", kind, label, piece_width, piece_depth))

    if not pieces:
        raise InputError("Add at least one piece of furniture")
    if len(pieces) > LIMITS["max_total"]:
        raise InputError(f"At most {LIMITS['max_total']} pieces of furniture are supported")
    if sum(p.width * p.depth for p in pieces) > 0.6 * room.width * room.length:
        raise InputError("That much furniture cannot fit in this room; make the room bigger or remove some pieces")

    notes = request.get("notes") or ""
    if not isinstance(notes, str):
        raise InputError("notes must be text")
    if len(notes) > LIMITS["notes_max"]:
        raise InputError(f"notes must be at most {LIMITS['notes_max']} characters")

    seed = request.get("seed")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise InputError("seed must be an integer")

    return room, pieces, preset, notes.strip(), seed
