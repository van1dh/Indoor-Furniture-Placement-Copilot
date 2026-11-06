"""Room and furniture geometry.

Coordinates are in feet with the origin at the room's bottom-left corner, x to the right and y up.
A piece's rotation is the direction its front faces: 0 = +y, 90 = +x, 180 = -y, 270 = -x.
Rectangles are (x0, y0, x1, y1) tuples.
"""
from dataclasses import dataclass, field

ROTATIONS = (0, 90, 180, 270)
FACING = {0: (0.0, 1.0), 90: (1.0, 0.0), 180: (0.0, -1.0), 270: (-1.0, 0.0)}

# Inward normal of each wall, and the rotation a piece needs to have its back against that wall
WALL_NORMALS = {"bottom": (0.0, 1.0), "top": (0.0, -1.0), "left": (1.0, 0.0), "right": (-1.0, 0.0)}
WALL_FACING_ROTATION = {"bottom": 0, "top": 180, "left": 90, "right": 270}


@dataclass(frozen=True)
class Opening:
    kind: str  # "door" or "window"
    wall: str
    offset: float  # from the wall's start: the left end of bottom/top walls, the bottom end of left/right walls
    width: float


@dataclass
class Room:
    width: float
    length: float
    doors: list = field(default_factory=list)
    windows: list = field(default_factory=list)

    def opening_segment(self, opening):
        """End points of an opening on its wall."""
        a, b = opening.offset, opening.offset + opening.width
        if opening.wall == "bottom":
            return (a, 0.0), (b, 0.0)
        if opening.wall == "top":
            return (a, self.length), (b, self.length)
        if opening.wall == "left":
            return (0.0, a), (0.0, b)
        return (self.width, a), (self.width, b)

    def opening_zone(self, opening, depth):
        """Rectangle extending ``depth`` into the room from an opening."""
        (x0, y0), (x1, y1) = self.opening_segment(opening)
        nx, ny = WALL_NORMALS[opening.wall]
        xs = (x0, x1, x0 + nx * depth, x1 + nx * depth)
        ys = (y0, y1, y0 + ny * depth, y1 + ny * depth)
        return (min(xs), min(ys), max(xs), max(ys))

    def opening_point(self, opening, depth):
        """Point ``depth`` into the room from the middle of an opening."""
        (x0, y0), (x1, y1) = self.opening_segment(opening)
        nx, ny = WALL_NORMALS[opening.wall]
        return ((x0 + x1) / 2 + nx * depth, (y0 + y1) / 2 + ny * depth)

    def to_dict(self):
        return {
            "width": self.width,
            "length": self.length,
            "doors": [opening_dict(o) for o in self.doors],
            "windows": [opening_dict(o) for o in self.windows],
        }


def opening_dict(opening):
    return {"wall": opening.wall, "offset": opening.offset, "width": opening.width}


@dataclass(frozen=True)
class Piece:
    id: str
    type: str
    label: str
    width: float
    depth: float


@dataclass(frozen=True)
class Placement:
    x: float  # centre
    y: float
    rotation: int


def footprint_size(piece, rotation):
    return (piece.width, piece.depth) if rotation in (0, 180) else (piece.depth, piece.width)


def footprint(piece, placement):
    w, h = footprint_size(piece, placement.rotation)
    return (placement.x - w / 2, placement.y - h / 2, placement.x + w / 2, placement.y + h / 2)


def front_zone(piece, placement, depth):
    """Rectangle of floor in front of a piece, as wide as its front."""
    x0, y0, x1, y1 = footprint(piece, placement)
    return {
        0: (x0, y1, x1, y1 + depth),
        180: (x0, y0 - depth, x1, y0),
        90: (x1, y0, x1 + depth, y1),
        270: (x0 - depth, y0, x0, y1),
    }[placement.rotation]


def front_point(piece, placement, distance):
    """Point ``distance`` in front of the middle of a piece's front side."""
    dx, dy = FACING[placement.rotation]
    w, h = footprint_size(piece, placement.rotation)
    half = h / 2 if dx == 0 else w / 2
    return (placement.x + dx * (half + distance), placement.y + dy * (half + distance))


def back_wall_distance(piece, placement, room):
    """Gap between a piece's back and the wall behind it."""
    x0, y0, x1, y1 = footprint(piece, placement)
    return {
        0: y0,
        180: room.length - y1,
        90: x0,
        270: room.width - x1,
    }[placement.rotation]


def overlap_area(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def area(rect):
    return max(0.0, rect[2] - rect[0]) * max(0.0, rect[3] - rect[1])


def outside_area(rect, room):
    """Area of ``rect`` that lies outside the room."""
    return area(rect) - overlap_area(rect, (0.0, 0.0, room.width, room.length))


def rect_point_distance(rect, point):
    dx = max(rect[0] - point[0], 0.0, point[0] - rect[2])
    dy = max(rect[1] - point[1], 0.0, point[1] - rect[3])
    return (dx * dx + dy * dy) ** 0.5
