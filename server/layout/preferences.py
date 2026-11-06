"""User preferences such as "bed near the window" or "desk away from the door".

A preference is a dict:
    {"kind": "near" | "away" | "against_wall", "piece": <furniture type>, "target": <target>,
     "strength": "low" | "medium" | "high", "reason": <optional text>}
Targets: "window", "door", "center", "wall:bottom" / "wall:right" / "wall:top" / "wall:left", or a furniture type.
``against_wall`` only takes a wall target. Every piece of the given type is held to the preference.
"""
from .catalog import FURNITURE_TYPES, WALLS
from .model import WALL_FACING_ROTATION, footprint, rect_point_distance

KINDS = ("near", "away", "against_wall")
STRENGTHS = {"low": 2.0, "medium": 5.0, "high": 12.0}
TARGETS = ("window", "door", "center") + tuple(f"wall:{w}" for w in WALLS) + tuple(FURNITURE_TYPES)
MAX_PREFERENCES = 12
NEAR_ENOUGH = 1.5  # feet: "near" counts as met within this gap
AWAY_DISTANCE = 6.0  # feet: "away" counts as met beyond this gap


class PreferenceError(ValueError):
    pass


def normalize(items, pieces):
    """Validate preferences; return (valid preferences, notes about dropped ones)."""
    if items is None:
        return [], []
    if not isinstance(items, list):
        raise PreferenceError("preferences must be a list")
    if len(items) > MAX_PREFERENCES:
        raise PreferenceError(f"At most {MAX_PREFERENCES} preferences are supported")

    present = {p.type for p in pieces}
    valid, dropped = [], []
    for item in items:
        if not isinstance(item, dict):
            raise PreferenceError("Each preference must be an object")
        kind, piece, target = item.get("kind"), item.get("piece"), item.get("target")
        strength = item.get("strength") or "medium"
        if kind not in KINDS or target not in TARGETS or strength not in STRENGTHS or piece not in FURNITURE_TYPES:
            raise PreferenceError(f"Invalid preference: {item}")
        if kind == "against_wall" and not target.startswith("wall:"):
            raise PreferenceError("against_wall preferences need a wall target")
        reason = item.get("reason") or ""
        if not isinstance(reason, str):
            raise PreferenceError("A preference's reason must be text")
        pref = {"kind": kind, "piece": piece, "target": target, "strength": strength, "reason": reason[:200]}
        if piece not in present:
            dropped.append(f"There is no {FURNITURE_TYPES[piece]['label'].lower()} in this room, so “{describe(pref)}” was skipped.")
        elif target in FURNITURE_TYPES and target not in present:
            dropped.append(f"There is no {FURNITURE_TYPES[target]['label'].lower()} in this room, so “{describe(pref)}” was skipped.")
        else:
            valid.append(pref)
    return valid, dropped


def describe(pref):
    piece = FURNITURE_TYPES[pref["piece"]]["label"]
    target = pref["target"]
    if target.startswith("wall:"):
        target_text = f"the {target[5:]} wall"
    elif target in FURNITURE_TYPES:
        target_text = f"the {FURNITURE_TYPES[target]['label'].lower()}"
    else:
        target_text = f"the {target}" if target != "center" else "the middle of the room"
    verb = {"near": "near", "away": "away from", "against_wall": "against"}[pref["kind"]]
    return f"{piece} {verb} {target_text}"


def _rect_distance(a, b):
    dx = max(a[0] - b[2], 0.0, b[0] - a[2])
    dy = max(a[1] - b[3], 0.0, b[1] - a[3])
    return (dx * dx + dy * dy) ** 0.5


def _wall_rect(room, wall):
    return {
        "bottom": (0.0, 0.0, room.width, 0.0),
        "top": (0.0, room.length, room.width, room.length),
        "left": (0.0, 0.0, 0.0, room.length),
        "right": (room.width, 0.0, room.width, room.length),
    }[wall]


def _segment_rect(room, opening):
    (x0, y0), (x1, y1) = room.opening_segment(opening)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _target_distance(room, pieces, placements, rects, index, target):
    """Gap between piece ``index`` and the nearest instance of ``target``, or None if there is none."""
    rect = rects[index]
    if target == "window":
        candidates = [_segment_rect(room, w) for w in room.windows]
    elif target == "door":
        candidates = [_segment_rect(room, d) for d in room.doors]
    elif target == "center":
        return rect_point_distance(rect, (room.width / 2, room.length / 2))
    elif target.startswith("wall:"):
        candidates = [_wall_rect(room, target[5:])]
    else:
        candidates = [rects[j] for j, p in enumerate(pieces) if p.type == target and j != index]
    if not candidates:
        return None
    return min(_rect_distance(rect, c) for c in candidates)


def evaluate(preferences, room, pieces, placements):
    """Return (weighted cost, [met? for each preference]); a preference with no possible target counts as unmet."""
    rects = [footprint(p, pl) for p, pl in zip(pieces, placements)]
    total, met = 0.0, []
    for pref in preferences:
        weight = STRENGTHS[pref["strength"]]
        all_met = True
        for i, piece in enumerate(pieces):
            if piece.type != pref["piece"]:
                continue
            gap = _target_distance(room, pieces, placements, rects, i, pref["target"])
            if gap is None:
                all_met = False
                continue
            if pref["kind"] == "near":
                cost = gap
                ok = gap <= NEAR_ENOUGH
            elif pref["kind"] == "away":
                cost = max(0.0, AWAY_DISTANCE - gap)
                ok = gap >= AWAY_DISTANCE
            else:
                facing_wall = WALL_FACING_ROTATION[pref["target"][5:]]
                cost = gap + (0.0 if placements[i].rotation == facing_wall else 2.0)
                ok = cost < 0.3
            total += weight * cost
            all_met = all_met and ok
        met.append(all_met)
    return total, met
