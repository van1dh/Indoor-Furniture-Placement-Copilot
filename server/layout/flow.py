"""Simulate a day of walking around a finished layout.

Each occupant (one per bed, at least one) follows a routine between the fronts of their furniture and the door.
Every trip takes the shortest route along the walkways (the same agent-sized grid the scorer uses), and the
cells it crosses are counted, giving a traffic heatmap and the distance walked per day.
"""
import heapq
import math

from .model import footprint, front_point
from .scoring import GRID_RESOLUTION

ROUTINE = ("bed", "wardrobe", "door", "desk", "sofa", "wardrobe", "bed")
NEIGHBOURS = [(dr, dc, math.hypot(dr, dc)) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]


def _nearest_walkable(walkable, cell, reach=3):
    r0, c0 = cell
    best, best_d = None, None
    for dr in range(-reach, reach + 1):
        for dc in range(-reach, reach + 1):
            r, c = r0 + dr, c0 + dc
            if 0 <= r < walkable.shape[0] and 0 <= c < walkable.shape[1] and walkable[r, c]:
                d = dr * dr + dc * dc
                if best_d is None or d < best_d:
                    best, best_d = (r, c), d
    return best


def _shortest_path(walkable, start, goal):
    """Cells of the shortest 8-connected path from start to goal, or None."""
    dist = {start: 0.0}
    previous = {}
    queue = [(0.0, start)]
    while queue:
        d, cell = heapq.heappop(queue)
        if cell == goal:
            path = [cell]
            while cell in previous:
                cell = previous[cell]
                path.append(cell)
            return path[::-1], d
        if d > dist[cell]:
            continue
        r, c = cell
        for dr, dc, step in NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < walkable.shape[0] and 0 <= nc < walkable.shape[1]) or not walkable[nr, nc]:
                continue
            # No corner cutting between two blocked cells
            if dr and dc and not (walkable[r, nc] and walkable[nr, c]):
                continue
            nd = d + step
            if nd < dist.get((nr, nc), math.inf):
                dist[(nr, nc)] = nd
                previous[(nr, nc)] = cell
                heapq.heappush(queue, (nd, (nr, nc)))
    return None, None


def simulate(scorer, placements):
    pieces = scorer.pieces
    res = GRID_RESOLUTION
    rects = [footprint(p, pl) for p, pl in zip(pieces, placements)]
    _, _, walkable = scorer.walk_grid(rects)

    stops_by_type = {}
    for piece, placement in zip(pieces, placements):
        point = front_point(piece, placement, scorer.radius + res)
        stops_by_type.setdefault(piece.type, []).append(point)
    stops_by_type["door"] = scorer.door_points[:1]

    occupants = max(1, len(stops_by_type.get("bed", [])))
    counts = {}
    distance = 0.0
    missed = 0
    for person in range(occupants):
        stops = []
        for kind in ROUTINE:
            options = stops_by_type.get(kind)
            if options:
                stops.append(options[person % len(options)])
        for a, b in zip(stops, stops[1:]):
            start = _nearest_walkable(walkable, scorer._cell(*a))
            goal = _nearest_walkable(walkable, scorer._cell(*b))
            path, length = _shortest_path(walkable, start, goal) if start and goal else (None, None)
            if path is None:
                missed += 1
                continue
            distance += length * res
            for cell in path:
                counts[cell] = counts.get(cell, 0) + 1

    cells = [
        [round((c - scorer.pad + 0.5) * res, 2), round((r - scorer.pad + 0.5) * res, 2), n]
        for (r, c), n in sorted(counts.items())
        if 0 <= (c - scorer.pad + 0.5) * res <= scorer.room.width and 0 <= (r - scorer.pad + 0.5) * res <= scorer.room.length
    ]
    return {
        "cellSize": res,
        "cells": cells,
        "maxCount": max((n for _, _, n in cells), default=0),
        "occupants": occupants,
        "dailyDistance": round(distance / occupants, 1),
        "missedTrips": missed,
    }
