"""Cost function for a layout: lower is better.

Hard constraints (overlap, outside the room, blocking a door's swing) carry very large weights so the optimizer
can still move through slightly invalid states; ``Evaluation.hard_violation`` says whether any remain.
Walkway checks run on a grid: a person (or wheelchair) is a disc of ``agent_radius`` that must fit between
furniture and walls on its way from a door to the front of each piece.
"""
import math
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from . import preferences as prefs
from .catalog import BASE_WEIGHTS, FURNITURE_TYPES, PRESETS
from .model import (
    FACING,
    area,
    back_wall_distance,
    footprint,
    front_point,
    front_zone,
    outside_area,
    overlap_area,
    rect_point_distance,
)

GRID_RESOLUTION = 0.5  # feet per grid cell
WINDOW_ZONE_DEPTH = 1.5
IDEAL_VIEWING_DISTANCE = 8.0
HAZARD_MARGIN = 3.0
HARD_TERMS = ("overlap", "out_of_room", "door")
# A typical day for one occupant: stops at the front of their furniture and at the door
ROUTINE = ("bed", "wardrobe", "door", "desk", "sofa", "wardrobe", "bed")


@dataclass
class Evaluation:
    total: float
    terms: dict  # unweighted value of each cost term
    unreachable: list = field(default_factory=list)  # piece ids
    cramped: list = field(default_factory=list)  # piece ids without enough room in front
    open_radius: float = 0.0
    open_center: tuple = (0.0, 0.0)
    preferences_met: list = field(default_factory=list)  # one bool per preference

    @property
    def hard_violation(self):
        return any(self.terms[t] > 1e-6 for t in HARD_TERMS)


class Scorer:
    def __init__(self, room, pieces, preset_name, preferences=(), anchors=None):
        """``anchors`` maps piece ids to placements the layout should stay close to (for small edits)."""
        self.room = room
        self.pieces = pieces
        self.preset = PRESETS[preset_name]
        self.weights = {**BASE_WEIGHTS, **self.preset["weights"]}
        self.radius = self.preset["agent_radius"]
        self.specs = [FURNITURE_TYPES[p.type] for p in pieces]
        self.front_depths = [max(s["front_clearance"], self.preset["min_front_clearance"]) for s in self.specs]
        self.door_zones = [room.opening_zone(d, d.width) for d in room.doors]
        self.window_zones = [room.opening_zone(w, WINDOW_ZONE_DEPTH) for w in room.windows]
        self.preferences = list(preferences)
        self.anchors = [anchors.get(p.id) for p in pieces] if anchors else None
        self._build_base_grid()

    # --- grid helpers -------------------------------------------------------------------------------------

    def _build_base_grid(self):
        res = GRID_RESOLUTION
        self.pad = int(math.ceil((self.radius + 1.0) / res))
        cols = int(math.ceil(self.room.width / res - 1e-9))
        rows = int(math.ceil(self.room.length / res - 1e-9))
        self.inside = np.zeros((rows + 2 * self.pad, cols + 2 * self.pad), dtype=bool)
        self.inside[self.pad:self.pad + rows, self.pad:self.pad + cols] = True
        # Open floor excludes door swings: nobody should play or sit where a door opens
        self.open_floor = self.inside.copy()
        for zone in self.door_zones:
            self._fill(self.open_floor, zone, False)
        base = self.inside.copy()
        # Doors open onto a corridor outside the room so the doorway itself is not a pinch point
        for door in self.room.doors:
            outside = self.room.opening_zone(door, -self.pad * res)
            self._fill(base, outside, True)
        self.base_free = base
        self.door_points = [self.room.opening_point(d, self.radius + res) for d in self.room.doors]

    def _cell(self, x, y):
        res = GRID_RESOLUTION
        return int(math.floor(y / res)) + self.pad, int(math.floor(x / res)) + self.pad

    def _fill(self, grid, rect, value):
        res = GRID_RESOLUTION
        x0, y0, x1, y1 = rect
        c0 = max(int(math.floor(x0 / res + 1e-6)) + self.pad, 0)
        c1 = min(int(math.ceil(x1 / res - 1e-6)) + self.pad, grid.shape[1])
        r0 = max(int(math.floor(y0 / res + 1e-6)) + self.pad, 0)
        r1 = min(int(math.ceil(y1 / res - 1e-6)) + self.pad, grid.shape[0])
        if c0 < c1 and r0 < r1:
            grid[r0:r1, c0:c1] = value

    def _feasible_label(self, labels, clearance, point):
        """Label of the walkable cell at ``point`` (or a walkable neighbour), 0 if none."""
        r, c = self._cell(*point)
        best = 0
        for dr in (0, -1, 1):
            for dc in (0, -1, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < labels.shape[0] and 0 <= cc < labels.shape[1] and labels[rr, cc]:
                    if dr == 0 and dc == 0:
                        return labels[rr, cc]
                    best = best or labels[rr, cc]
        return best

    # --- evaluation ---------------------------------------------------------------------------------------

    def evaluate(self, placements):
        room, pieces, specs = self.room, self.pieces, self.specs
        rects = [footprint(p, pl) for p, pl in zip(pieces, placements)]
        terms = dict.fromkeys(BASE_WEIGHTS, 0.0)

        for i, a in enumerate(rects):
            terms["out_of_room"] += outside_area(a, room)
            for b in rects[i + 1:]:
                terms["overlap"] += overlap_area(a, b)
            for zone in self.door_zones:
                terms["door"] += overlap_area(a, zone)
            if specs[i]["tall"]:
                for zone in self.window_zones:
                    terms["window"] += overlap_area(a, zone)
            if specs[i]["against_wall"]:
                terms["wall"] += max(0.0, back_wall_distance(pieces[i], placements[i], room))

        cramped = []
        for i, (piece, placement) in enumerate(zip(pieces, placements)):
            zone = front_zone(piece, placement, self.front_depths[i])
            blocked = outside_area(zone, room) + sum(
                overlap_area(zone, rects[j]) for j in range(len(rects)) if j != i)
            if blocked > 0.05 * area(zone):
                cramped.append(piece.id)
            terms["clearance"] += blocked

        # Walkways: free floor, eroded by the agent's radius, must connect each door to each piece's front
        res = GRID_RESOLUTION
        free, clearance, walkable = self.walk_grid(rects)
        labels, _ = ndimage.label(walkable)
        door_labels = {self._feasible_label(labels, clearance, p) for p in self.door_points} - {0}
        unreachable = []
        for piece, placement in zip(pieces, placements):
            target = front_point(piece, placement, self.radius + res)
            if self._feasible_label(labels, clearance, target) not in door_labels:
                unreachable.append(piece.id)
        terms["unreachable"] = float(len(unreachable))

        # Open floor: the largest clear circle inside the room, away from furniture, walls and door swings
        room_clearance = ndimage.distance_transform_edt(self.open_floor & free) * res - res / 2
        r, c = np.unravel_index(np.argmax(room_clearance), room_clearance.shape)
        open_radius = float(max(room_clearance[r, c], 0.0))
        open_center = (float((c - self.pad + 0.5) * res), float((r - self.pad + 0.5) * res))
        terms["open_space"] = -open_radius

        min_play = self.preset.get("min_play_radius", 0.0)
        terms["play_area"] = max(0.0, min_play - open_radius)
        for i, spec in enumerate(specs):
            if spec["hazard"]:
                gap = rect_point_distance(rects[i], open_center) - open_radius
                terms["hazard"] += max(0.0, HAZARD_MARGIN - float(gap))

        if self.weights["play_traffic"]:
            # Straight lines stand in for the walking routes here; the grid search is too slow for the optimizer
            terms["play_traffic"] = sum(
                chord_length(a, b, open_center, open_radius)
                for legs in self.routine_legs(placements) for a, b in legs)

        terms["viewing"] = self._viewing_cost(placements)
        terms["privacy"], terms["desk_group"] = self._sharing_costs(placements)
        terms["preferences"], met = prefs.evaluate(self.preferences, room, pieces, placements)
        if self.anchors:
            for anchor, placement in zip(self.anchors, placements):
                if anchor is not None:
                    terms["anchor"] += math.hypot(placement.x - anchor.x, placement.y - anchor.y)
                    terms["anchor"] += 0.0 if placement.rotation == anchor.rotation else 2.0

        total = sum(self.weights[name] * value for name, value in terms.items())
        return Evaluation(total, terms, unreachable, cramped, open_radius, open_center, met)

    def routine_legs(self, placements):
        """The trips of a typical day as [(start, end), ...] for each occupant (one per bed, at least one)."""
        stops_by_type = {}
        for piece, placement in zip(self.pieces, placements):
            point = front_point(piece, placement, self.radius + GRID_RESOLUTION)
            stops_by_type.setdefault(piece.type, []).append(point)
        stops_by_type["door"] = self.door_points[:1]
        occupants = max(1, len(stops_by_type.get("bed", [])))
        routines = []
        for person in range(occupants):
            stops = [options[person % len(options)] for kind in ROUTINE if (options := stops_by_type.get(kind))]
            routines.append(list(zip(stops, stops[1:])))
        return routines

    def walk_grid(self, rects):
        """(free floor, clearance in feet, cells where the agent's centre fits) for furniture footprints."""
        res = GRID_RESOLUTION
        free = self.base_free.copy()
        for rect in rects:
            self._fill(free, rect, False)
        clearance = ndimage.distance_transform_edt(free) * res - res / 2
        return free, clearance, clearance >= self.radius - res / 2

    def _viewing_cost(self, placements):
        tvs = [i for i, p in enumerate(self.pieces) if p.type == "tv"]
        seats = [i for i, p in enumerate(self.pieces) if p.type == "sofa"] or [
            i for i, p in enumerate(self.pieces) if p.type == "bed"]
        cost = 0.0
        for t in tvs:
            best = None
            for s in seats:
                tx, ty = placements[t].x, placements[t].y
                sx, sy = placements[s].x, placements[s].y
                dist = math.hypot(sx - tx, sy - ty) or 1e-6
                ux, uy = (sx - tx) / dist, (sy - ty) / dist
                fx, fy = FACING[placements[t].rotation]
                c = (1 - (fx * ux + fy * uy)) + abs(dist - IDEAL_VIEWING_DISTANCE) / 4
                if self.pieces[s].type == "sofa":
                    gx, gy = FACING[placements[s].rotation]
                    c += 1 - (-gx * ux - gy * uy)
                best = c if best is None else min(best, c)
            cost += best or 0.0
        return cost

    def _sharing_costs(self, placements):
        def centers(kind):
            return [(pl.x, pl.y) for p, pl in zip(self.pieces, placements) if p.type == kind]

        def pairwise(points):
            return [math.dist(a, b) for i, a in enumerate(points) for b in points[i + 1:]]

        bed_gaps = pairwise(centers("bed"))
        desk_gaps = pairwise(centers("desk"))
        privacy = -min(bed_gaps) if bed_gaps else 0.0
        grouping = sum(desk_gaps) / len(desk_gaps) if desk_gaps else 0.0
        return privacy, grouping


def chord_length(a, b, center, radius):
    """Length of the part of segment a-b that lies inside a circle."""
    ax, ay = a[0] - center[0], a[1] - center[1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    qa = dx * dx + dy * dy
    if qa == 0 or radius <= 0:
        return 0.0
    qb = 2 * (ax * dx + ay * dy)
    qc = ax * ax + ay * ay - radius * radius
    disc = qb * qb - 4 * qa * qc
    if disc <= 0:
        return 0.0
    root = math.sqrt(disc)
    t0 = max((-qb - root) / (2 * qa), 0.0)
    t1 = min((-qb + root) / (2 * qa), 1.0)
    return max(t1 - t0, 0.0) * math.sqrt(qa)
