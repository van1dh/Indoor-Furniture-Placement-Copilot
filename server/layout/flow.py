"""Simulate a day of walking around a finished layout.

Each occupant (one per bed, at least one) follows a routine between the fronts of their furniture and the door.
Every trip takes the shortest route along the walkways (the same agent-sized grid the scorer uses), and the
cells it crosses are counted, giving a traffic heatmap and the distance walked per day.
"""
import heapq
import math

from .model import footprint
from .scoring import GRID_RESOLUTION
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


def simulate(scorer, placements, play_area=None):
    """Walk every occupant's routine. ``play_area`` is an optional ((x, y), radius) circle; the distance walked
    through it is reported as ``playAreaDistance``."""
    res = GRID_RESOLUTION
    rects = [footprint(p, pl) for p, pl in zip(scorer.pieces, placements)]
    _, _, walkable = scorer.walk_grid(rects)

    def cell_center(cell):
        r, c = cell
        return (c - scorer.pad + 0.5) * res, (r - scorer.pad + 0.5) * res

    def in_play_area(point):
        return play_area is not None and math.dist(point, play_area[0]) < play_area[1]

    routines = scorer.routine_legs(placements)
    counts = {}
    distance = 0.0
    play_distance = 0.0
    missed = 0
    for legs in routines:
        for a, b in legs:
            start = _nearest_walkable(walkable, scorer._cell(*a))
            goal = _nearest_walkable(walkable, scorer._cell(*b))
            path, length = _shortest_path(walkable, start, goal) if start and goal else (None, None)
            if path is None:
                missed += 1
                continue
            distance += length * res
            for cell in path:
                counts[cell] = counts.get(cell, 0) + 1
            for p, q in zip(path, path[1:]):
                (px, py), (qx, qy) = cell_center(p), cell_center(q)
                if in_play_area(((px + qx) / 2, (py + qy) / 2)):
                    play_distance += math.dist((px, py), (qx, qy))

    cells = []
    for cell, n in sorted(counts.items()):
        x, y = cell_center(cell)
        if 0 <= x <= scorer.room.width and 0 <= y <= scorer.room.length:
            cells.append([round(x, 2), round(y, 2), n])
    occupants = len(routines)
    return {
        "cellSize": res,
        "cells": cells,
        "maxCount": max((n for _, _, n in cells), default=0),
        "occupants": occupants,
        "dailyDistance": round(distance / occupants, 1),
        "playAreaDistance": round(play_distance / occupants, 1),
        "missedTrips": missed,
    }
