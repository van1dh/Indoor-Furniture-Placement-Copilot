"""Furniture types and layout presets.

All lengths are in feet. A piece's ``width`` runs along its front side and ``depth`` runs front to back.
"""

FURNITURE_TYPES = {
    "bed": {
        "label": "Bed",
        "width": 5.0,
        "depth": 6.5,
        "front_clearance": 2.5,
        "against_wall": True,
        "tall": False,
        "hazard": False,
    },
    "desk": {
        "label": "Desk",
        "width": 4.0,
        "depth": 2.0,
        "front_clearance": 3.0,
        "against_wall": True,
        "tall": False,
        "hazard": True,  # hard corners at a toddler's head height
    },
    "tv": {
        "label": "TV stand",
        "width": 4.0,
        "depth": 1.5,
        "front_clearance": 2.0,
        "against_wall": True,
        "tall": False,
        "hazard": True,  # fragile, can tip over
    },
    "wardrobe": {
        "label": "Wardrobe",
        "width": 4.0,
        "depth": 2.0,
        "front_clearance": 3.0,
        "against_wall": True,
        "tall": True,  # blocks windows, tip-over risk
        "hazard": True,
    },
    "sofa": {
        "label": "Sofa",
        "width": 7.0,
        "depth": 3.0,
        "front_clearance": 2.5,
        "against_wall": False,
        "tall": False,
        "hazard": False,
    },
}

PRESETS = {
    "default": {
        "label": "Balanced",
        "description": "Furniture against the walls, clear walkways and as much open floor as possible.",
        "agent_radius": 1.25,  # 30 in walkway
        "min_front_clearance": 0.0,
        "weights": {"wall": 4, "open_space": 2, "window": 10, "viewing": 3},
    },
    "child_safe": {
        "label": "Child-safe",
        "description": "A large open play area, with fragile, sharp and tall furniture against the walls and away from it.",
        "agent_radius": 1.25,
        "min_front_clearance": 0.0,
        "min_play_radius": 3.0,
        "weights": {"wall": 10, "open_space": 12, "window": 10, "viewing": 2, "hazard": 8, "play_area": 40},
    },
    "accessible": {
        "label": "Wheelchair accessible",
        "description": "36 in walkways and a 5 ft turning space in front of every piece of furniture.",
        "agent_radius": 1.5,  # 36 in walkway
        "min_front_clearance": 5.0,  # 60 in turning circle
        "weights": {"wall": 4, "open_space": 2, "window": 10, "viewing": 2, "clearance": 300},
    },
    "shared": {
        "label": "Shared studio",
        "description": "Beds spread apart for privacy, desks grouped for working together and open space to meet.",
        "agent_radius": 1.25,
        "min_front_clearance": 0.0,
        "weights": {"wall": 4, "open_space": 4, "window": 10, "viewing": 2, "privacy": 4, "desk_group": 3},
    },
}

DEFAULT_PRESET = "default"
AUTO_PRESET = "auto"  # let the copilot pick a preset from the notes

# Weights shared by every preset; a preset's own weights override these.
BASE_WEIGHTS = {
    "overlap": 1000,
    "out_of_room": 1000,
    "door": 1000,
    "clearance": 150,
    "unreachable": 300,
    "wall": 4,
    "open_space": 2,
    "window": 10,
    "viewing": 3,
    "hazard": 0,
    "play_area": 0,
    "privacy": 0,
    "desk_group": 0,
    "preferences": 1,  # preferences carry their own strength weights
    "anchor": 1.5,  # staying close to the previous layout when refining it
}

LIMITS = {
    "room_min": 8.0,
    "room_max": 60.0,
    "furniture_min": 1.0,
    "furniture_max": 15.0,
    "max_per_type": 6,
    "max_total": 16,
    "opening_min": 2.0,
    "opening_max": 12.0,
    "max_doors": 3,
    "max_windows": 6,
    "notes_max": 500,
}

WALLS = ("bottom", "right", "top", "left")


def describe():
    """Options the frontend needs to build its form."""
    return {
        "furniture": {
            name: {"label": spec["label"], "width": spec["width"], "depth": spec["depth"]}
            for name, spec in FURNITURE_TYPES.items()
        },
        "presets": {
            name: {"label": preset["label"], "description": preset["description"]}
            for name, preset in PRESETS.items()
        },
        "defaultPreset": AUTO_PRESET,
        "autoPreset": {"label": "Let the copilot decide", "description": "The copilot picks a goal from your notes."},
        "walls": list(WALLS),
        "limits": LIMITS,
        "defaults": {
            "room": {
                "width": 16.0,
                "length": 14.0,
                "doors": [{"wall": "bottom", "offset": 1.0, "width": 3.0}],
                "windows": [{"wall": "top", "offset": 5.0, "width": 5.0}],
            },
            "furniture": {"bed": 1, "desk": 1, "tv": 1, "wardrobe": 1, "sofa": 0},
        },
    }
