"""Validate a layout request and turn it into model objects."""
import math

from . import preferences as prefs
from .catalog import AUTO_PRESET, FURNITURE_TYPES, LIMITS, PRESETS, DEFAULT_PRESET, WALLS
from .model import ROTATIONS, Opening, Piece, Placement, Room


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
    """Return (room, pieces, preset_name, notes, seed, preferences) or raise InputError.

    ``preset_name`` may be AUTO_PRESET (let the copilot choose). ``preferences`` is None when the request has none,
    so the copilot should derive them from the notes, or a validated list (possibly empty)."""
    if not isinstance(request, dict):
        raise InputError("Request must be a JSON object")

    preset = request.get("preset") or DEFAULT_PRESET
    if preset not in PRESETS and preset != AUTO_PRESET:
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

    preferences = request.get("preferences")
    if preferences is not None:
        try:
            preferences, _ = prefs.normalize(preferences, pieces)
        except prefs.PreferenceError as e:
            raise InputError(str(e))

    return room, pieces, preset, notes.strip(), seed, preferences


def _text(value, name, limit):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{name} is required")
    if len(value) > limit:
        raise InputError(f"{name} must be at most {limit} characters")
    return value.strip()


def _placements(layout):
    """Placements by piece id from a layout's furniture list ({id, x, y, rotation} items)."""
    if not isinstance(layout, dict):
        raise InputError("layout must be an object")
    furniture = layout.get("furniture") or []
    if not isinstance(furniture, list) or len(furniture) > LIMITS["max_total"]:
        raise InputError(f"layout furniture must be a list of at most {LIMITS['max_total']} pieces")
    placements = {}
    for item in furniture:
        try:
            x, y, rotation = float(item["x"]), float(item["y"]), int(item["rotation"])
        except (KeyError, TypeError, ValueError):
            raise InputError("layout furniture needs x, y and rotation")
        if not (math.isfinite(x) and math.isfinite(y)) or max(abs(x), abs(y)) > 2 * LIMITS["room_max"]:
            raise InputError("layout furniture positions must be inside the room")
        if rotation not in ROTATIONS:
            raise InputError("rotation must be 0, 90, 180 or 270")
        placements[str(item.get("id"))] = Placement(x, y, rotation)
    return placements


def parse_evaluation(payload):
    """Validate an evaluate request: a layout arranged by hand. Returns (request, placements by piece id)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("request"), dict):
        raise InputError("request is required")
    return payload["request"], _placements(payload.get("layout"))


def parse_refinement(payload):
    """Validate a refine request: the layout to change, the user's message and the chat so far.

    Returns (request, initial placements by piece id, message, history)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("request"), dict):
        raise InputError("request is required")
    message = _text(payload.get("message"), "message", LIMITS["notes_max"])
    placements = _placements(payload.get("layout") or {})

    history = payload.get("history") or []
    if not isinstance(history, list) or len(history) > 20:
        raise InputError("history must be a list of at most 20 messages")
    turns = []
    for i, turn in enumerate(history):
        role = "user" if i % 2 == 0 else "assistant"
        if not isinstance(turn, dict) or turn.get("role") != role:
            raise InputError("history must alternate user and assistant messages, starting with the user")
        turns.append({"role": role, "text": _text(turn.get("text"), "history text", 2000)})
    if len(turns) % 2:
        raise InputError("history must end with an assistant message")

    return payload["request"], placements, message, turns
