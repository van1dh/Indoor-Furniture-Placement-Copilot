"""Search for a low-cost layout with simulated annealing and random restarts."""
import math

from .catalog import FURNITURE_TYPES
from .model import ROTATIONS, WALL_FACING_ROTATION, Placement, footprint_size
from .scoring import Scorer

WALL_NAMES = tuple(WALL_FACING_ROTATION)


class PlacementError(RuntimeError):
    pass


def _rank(evaluation):
    """Any layout that meets the hard constraints beats any layout that does not."""
    return (evaluation.hard_violation, evaluation.total)


class Optimizer:
    def __init__(self, room, pieces, preset_name, rng, restarts=4, iterations=1200, preferences=(), initial=None):
        """With ``initial`` placements (one per piece, or None for a new piece) the search refines that layout:
        it starts there, runs cooler, and pays to move pieces away from where they were."""
        self.room = room
        self.pieces = pieces
        self.rng = rng
        self.restarts = restarts
        self.iterations = iterations
        self.initial = initial
        anchors = {p.id: pl for p, pl in zip(pieces, initial) if pl is not None} if initial else None
        self.scorer = Scorer(room, pieces, preset_name, preferences, anchors)
        self.same_type = [[j for j, q in enumerate(pieces) if q.type == p.type and j != i] for i, p in enumerate(pieces)]

    # --- moves --------------------------------------------------------------------------------------------

    def _clamp(self, piece, x, y, rotation):
        w, h = footprint_size(piece, rotation)
        x = min(max(x, w / 2), self.room.width - w / 2) if w <= self.room.width else self.room.width / 2
        y = min(max(y, h / 2), self.room.length - h / 2) if h <= self.room.length else self.room.length / 2
        return Placement(x, y, rotation)

    def _against_wall(self, piece, wall, along):
        """Place a piece with its back against ``wall``, ``along`` feet from the wall's start."""
        rotation = WALL_FACING_ROTATION[wall]
        w, h = footprint_size(piece, rotation)
        if wall == "bottom":
            return self._clamp(piece, along, h / 2, rotation)
        if wall == "top":
            return self._clamp(piece, along, self.room.length - h / 2, rotation)
        if wall == "left":
            return self._clamp(piece, w / 2, along, rotation)
        return self._clamp(piece, self.room.width - w / 2, along, rotation)

    def _beside(self, piece, other):
        """Line a piece up next to ``other``, facing the same way (e.g. desks in a row)."""
        w, h = footprint_size(piece, other.rotation)
        side = self.rng.choice((-1, 1))
        if other.rotation in (0, 180):
            return self._clamp(piece, other.x + side * w, other.y, other.rotation)
        return self._clamp(piece, other.x, other.y + side * h, other.rotation)

    def _random_placement(self, piece):
        rng = self.rng
        if FURNITURE_TYPES[piece.type]["against_wall"] or rng.random() < 0.3:
            wall = rng.choice(WALL_NAMES)
            length = self.room.width if wall in ("bottom", "top") else self.room.length
            return self._against_wall(piece, wall, rng.uniform(0, length))
        return self._clamp(piece, rng.uniform(0, self.room.width), rng.uniform(0, self.room.length),
                           rng.choice(ROTATIONS))

    def _neighbour(self, placements, temperature_ratio):
        rng = self.rng
        new = list(placements)
        i = rng.randrange(len(new))
        piece, current = self.pieces[i], new[i]
        move = rng.random()
        if move < 0.45:
            sigma = 0.25 + 2.5 * temperature_ratio
            new[i] = self._clamp(piece, current.x + rng.gauss(0, sigma), current.y + rng.gauss(0, sigma),
                                 current.rotation)
        elif move < 0.6:
            new[i] = self._clamp(piece, current.x, current.y, rng.choice(ROTATIONS))
        elif move < 0.8:
            wall = rng.choice(WALL_NAMES)
            along = current.x if wall in ("bottom", "top") else current.y
            new[i] = self._against_wall(piece, wall, along + rng.gauss(0, 1.0))
        elif move < 0.85 and len(new) > 1:
            j = rng.randrange(len(new) - 1)
            j += j >= i
            new[i] = self._clamp(piece, new[j].x, new[j].y, current.rotation)
            new[j] = self._clamp(self.pieces[j], current.x, current.y, new[j].rotation)
        elif move < 0.93 and self.same_type[i]:
            new[i] = self._beside(piece, new[rng.choice(self.same_type[i])])
        else:
            new[i] = self._random_placement(piece)
        return new

    # --- search -------------------------------------------------------------------------------------------

    def _anneal(self, warm):
        if warm:
            placements = [self._clamp(p, pl.x, pl.y, pl.rotation) if pl else self._random_placement(p)
                          for p, pl in zip(self.pieces, self.initial)]
            t_start = 3.0
        else:
            placements = [self._random_placement(p) for p in self.pieces]
            t_start = 30.0
        current = self.scorer.evaluate(placements)
        best_placements, best = placements, current
        t_end = 0.05
        for step in range(self.iterations):
            ratio = step / max(self.iterations - 1, 1)
            temperature = t_start * (t_end / t_start) ** ratio
            candidate = self._neighbour(placements, 1 - ratio)
            result = self.scorer.evaluate(candidate)
            delta = result.total - current.total
            if delta <= 0 or self.rng.random() < math.exp(-delta / temperature):
                placements, current = candidate, result
                if _rank(current) < _rank(best):
                    best_placements, best = placements, current
        return best_placements, best

    def run(self):
        best_placements, best = None, None
        for attempt in range(self.restarts):
            placements, result = self._anneal(warm=self.initial is not None and attempt == 0)
            if best is None or _rank(result) < _rank(best):
                best_placements, best = placements, result
        if best.hard_violation:
            raise PlacementError(
                "Could not fit all of this furniture without overlaps or blocking a door; "
                "try a bigger room or fewer pieces")
        return best_placements, best
