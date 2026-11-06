// Moving and rotating furniture by hand. Positions snap to SNAP feet and pieces stay inside the room;
// the server re-scores the result (see evaluateLayout in api.js).

export const SNAP = 0.25;

// The direction each rotation faces, as in the server (0 faces up the floor plan, 90 right, ...)
const FACING = { 0: [0, 1], 90: [1, 0], 180: [0, -1], 270: [-1, 0] };

const snap = (v) => Math.round(v / SNAP) * SNAP;
const clamp = (v, low, high) => Math.min(Math.max(v, low), Math.max(low, high));

function place(piece, room, x, y, rotation) {
  const turned = rotation === 90 || rotation === 270;
  const footprint = turned
    ? { width: piece.depth, length: piece.width }
    : { width: piece.width, length: piece.depth };
  const cx = clamp(snap(x), footprint.width / 2, room.width - footprint.width / 2);
  const cy = clamp(snap(y), footprint.length / 2, room.length - footprint.length / 2);
  const direction = FACING[rotation];
  return {
    ...piece,
    x: cx,
    y: cy,
    rotation,
    footprint,
    front: { x: cx + (direction[0] * piece.depth) / 2, y: cy + (direction[1] * piece.depth) / 2, direction },
  };
}

function update(layout, id, change) {
  return {
    ...layout,
    furniture: layout.furniture.map((p) => (p.id === id ? change(p) : p)),
  };
}

export function movePiece(layout, id, x, y) {
  return update(layout, id, (p) => place(p, layout.room, x, y, p.rotation));
}

// Turn a piece a quarter clockwise on the floor plan
export function rotatePiece(layout, id) {
  return update(layout, id, (p) => place(p, layout.room, p.x, p.y, (p.rotation + 90) % 360));
}

export function placements(layout) {
  return layout.furniture.map(({ id, x, y, rotation }) => ({ id, x, y, rotation }));
}
