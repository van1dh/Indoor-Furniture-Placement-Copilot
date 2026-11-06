"""Generate a room layout image from furniture counts.

Reads a JSON request on stdin, e.g. {"bed": 1, "desk": 1, "tv": 1, "wardrobe": 1, "notes": "..."},
writes a PNG into the output directory and prints a single JSON line on stdout:
    {"image": "<file name>"}             on success (exit code 0)
    {"error": "<message>"}               on invalid input (exit code 2) or placement failure (exit code 3)
"""
import argparse
import json
import os
import random
import sys
import uuid

import matplotlib

matplotlib.use("Agg")  # headless: we only ever write files
import matplotlib.pyplot as plt  # noqa: E402

ROOM_WIDTH = 30
ROOM_HEIGHT = 40

# Furniture dimensions (width, height) in feet
FURNITURE_SIZES = {
    "bed": (6, 8),
    "desk": (4, 2),
    "tv": (4, 2),
    "wardrobe": (4, 2),
}

MAX_PER_TYPE = 4
MAX_NOTES_LENGTH = 500
MAX_ATTEMPTS = 200

# Orientation is the direction the furniture's front faces:
# 0 = +y (up), 90 = +x (right), 180 = -y (down), 270 = -x (left)
FACING_VECTORS = {0: (0, 1), 90: (1, 0), 180: (0, -1), 270: (-1, 0)}


class InputError(ValueError):
    pass


class PlacementError(RuntimeError):
    pass


class Furniture:
    def __init__(self, name, x, y, width, height, orientation):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.orientation = orientation
        self.interact_position = self.get_interact_position()

    def get_interact_position(self):
        dx, dy = FACING_VECTORS[self.orientation]
        return (self.x + dx * self.width / 2, self.y + dy * self.height / 2)

    def overlaps(self, x, y, width, height):
        return abs(self.x - x) < (self.width + width) / 2 and abs(self.y - y) < (self.height + height) / 2


def parse_request(request):
    if not isinstance(request, dict):
        raise InputError("Request must be a JSON object")

    counts = {}
    for name in FURNITURE_SIZES:
        value = request.get(name, 0)
        if value in ("", None):
            value = 0
        try:
            count = int(value)
        except (TypeError, ValueError):
            raise InputError(f"'{name}' must be a whole number")
        if isinstance(value, float) and not value.is_integer():
            raise InputError(f"'{name}' must be a whole number")
        if not 0 <= count <= MAX_PER_TYPE:
            raise InputError(f"'{name}' must be between 0 and {MAX_PER_TYPE}")
        counts[name] = count

    if sum(counts.values()) == 0:
        raise InputError("Add at least one piece of furniture")

    notes = request.get("notes") or ""
    if not isinstance(notes, str):
        raise InputError("'notes' must be text")
    if len(notes) > MAX_NOTES_LENGTH:
        raise InputError(f"'notes' must be at most {MAX_NOTES_LENGTH} characters")

    return counts, notes.strip()


def facing_away_from_nearest_wall(x, y):
    distances = {
        90: x,  # near left wall -> face right
        270: ROOM_WIDTH - x,  # near right wall -> face left
        0: y,  # near bottom wall -> face up
        180: ROOM_HEIGHT - y,  # near top wall -> face down
    }
    return min(distances, key=distances.get)


def generate_room_layout(furniture_counts, rng=random):
    furniture_list = []
    # One preferred slot at the middle of each wall, facing into the room
    wall_slots = [
        (0, ROOM_HEIGHT / 2, 90),
        (ROOM_WIDTH, ROOM_HEIGHT / 2, 270),
        (ROOM_WIDTH / 2, 0, 0),
        (ROOM_WIDTH / 2, ROOM_HEIGHT, 180),
    ]

    for name, count in furniture_counts.items():
        width, height = FURNITURE_SIZES[name]
        for _ in range(count):
            x, y, orientation = wall_slots[len(furniture_list) % len(wall_slots)]
            x = min(max(x, width / 2), ROOM_WIDTH - width / 2)
            y = min(max(y, height / 2), ROOM_HEIGHT - height / 2)

            attempts = 0
            while any(other.overlaps(x, y, width, height) for other in furniture_list):
                attempts += 1
                if attempts >= MAX_ATTEMPTS:
                    raise PlacementError(f"Could not fit every {name} in the room; try fewer pieces")
                x = rng.uniform(width / 2, ROOM_WIDTH - width / 2)
                y = rng.uniform(height / 2, ROOM_HEIGHT - height / 2)
                orientation = facing_away_from_nearest_wall(x, y)

            furniture_list.append(Furniture(name, x, y, width, height, orientation))

    return furniture_list


def plot_room_layout(furniture_list, notes, output_path):
    fig, ax = plt.subplots()
    ax.set_xlim(0, ROOM_WIDTH)
    ax.set_ylim(0, ROOM_HEIGHT)
    ax.set_aspect("equal")
    ax.set_title("Room Layout")
    ax.set_xlabel("Width (feet)")
    ax.set_ylabel("Height (feet)")

    ax.plot([0, ROOM_WIDTH, ROOM_WIDTH, 0, 0], [0, 0, ROOM_HEIGHT, ROOM_HEIGHT, 0], color="black")

    for furniture in furniture_list:
        x, y = furniture.x, furniture.y
        width, height = furniture.width, furniture.height
        rect = plt.Rectangle((x - width / 2, y - height / 2), width, height, edgecolor="blue", facecolor="lightblue")
        ax.add_patch(rect)
        ax.text(x, y, furniture.name, ha="center", va="center", fontsize=8, color="black")

        dx, dy = FACING_VECTORS[furniture.orientation]
        ax.arrow(x, y, dx * width / 4, dy * height / 4, head_width=0.5, head_length=0.5, fc="red", ec="red")

    if notes:
        ax.text(0.5, -0.15, f"Notes: {notes}", transform=ax.transAxes, ha="center", va="top", fontsize=10, color="gray", wrap=True)

    try:
        fig.savefig(output_path, bbox_inches="tight")
    finally:
        plt.close(fig)


def emit(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated"))
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    try:
        counts, notes = parse_request(json.load(sys.stdin))
    except json.JSONDecodeError:
        emit({"error": "Request body is not valid JSON"})
        return 2
    except InputError as e:
        emit({"error": str(e)})
        return 2

    try:
        furniture_list = generate_room_layout(counts, random.Random(args.seed))
    except PlacementError as e:
        emit({"error": str(e)})
        return 3

    os.makedirs(args.output_dir, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}.png"
    plot_room_layout(furniture_list, notes, os.path.join(args.output_dir, file_name))
    emit({"image": file_name})
    return 0


if __name__ == "__main__":
    sys.exit(main())
