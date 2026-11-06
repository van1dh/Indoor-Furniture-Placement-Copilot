import React, { useRef } from 'react';
import { movePiece, rotatePiece } from './editing';
import './LayoutView.css';

const MARGIN = 1.5; // feet around the room
const WALL = 0.25;

// Room coordinates have y up; SVG has y down, so every y goes through flip().
function openingSegment(room, o) {
  const a = o.offset;
  const b = o.offset + o.width;
  switch (o.wall) {
    case 'bottom': return [[a, 0], [b, 0]];
    case 'top': return [[a, room.length], [b, room.length]];
    case 'left': return [[0, a], [0, b]];
    default: return [[room.width, a], [room.width, b]];
  }
}

const INWARD = { bottom: [0, 1], top: [0, -1], left: [1, 0], right: [-1, 0] };

function Door({ room, door, flip }) {
  const [[x0, y0], [x1, y1]] = openingSegment(room, door);
  const [nx, ny] = INWARD[door.wall];
  // Hinged at the segment start, swinging into the room
  const leafX = x0 + nx * door.width;
  const leafY = y0 + ny * door.width;
  const sweep = door.wall === 'bottom' || door.wall === 'right' ? 1 : 0;
  return (
    <g className="layout-door">
      <line x1={x0} y1={flip(y0)} x2={x1} y2={flip(y1)} className="layout-opening-gap" />
      <line x1={x0} y1={flip(y0)} x2={leafX} y2={flip(leafY)} className="layout-door-leaf" />
      <path
        d={`M ${leafX} ${flip(leafY)} A ${door.width} ${door.width} 0 0 ${sweep} ${x1} ${flip(y1)}`}
        className="layout-door-swing"
      />
    </g>
  );
}

function Window({ room, window: w, flip }) {
  const [[x0, y0], [x1, y1]] = openingSegment(room, w);
  return (
    <g className="layout-window">
      <line x1={x0} y1={flip(y0)} x2={x1} y2={flip(y1)} className="layout-opening-gap" />
      <line x1={x0} y1={flip(y0)} x2={x1} y2={flip(y1)} className="layout-window-glass" />
    </g>
  );
}

const KEY_STEPS = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };

function Piece({ piece, flip, flagged, selected, handlers }) {
  const { width: w, length: h } = piece.footprint;
  const x = piece.x - w / 2;
  const y = flip(piece.y + h / 2);
  const [dx, dy] = piece.front.direction;
  // Front edge, drawn heavier so the orientation is visible
  const half = dx === 0 ? w / 2 : h / 2;
  const fx0 = piece.front.x - (dx === 0 ? half : 0);
  const fx1 = piece.front.x + (dx === 0 ? half : 0);
  const fy0 = piece.front.y - (dy === 0 ? half : 0);
  const fy1 = piece.front.y + (dy === 0 ? half : 0);
  const vertical = h > w;
  const fontSize = Math.min(0.6, Math.min(w, h) * 0.4);
  return (
    <g
      className={`layout-piece layout-piece-${piece.type}${flagged ? ' layout-piece-flagged' : ''}${
        selected ? ' layout-piece-selected' : ''}`}
      {...(handlers && {
        tabIndex: 0,
        role: 'button',
        'aria-label': `${piece.label}: drag or use the arrow keys to move, R to rotate`,
        'aria-pressed': selected,
        ...handlers,
      })}
    >
      <title>{`${piece.label}: ${piece.width} × ${piece.depth} ft`}</title>
      <rect x={x} y={y} width={w} height={h} rx={0.15} />
      <line x1={fx0} y1={flip(fy0)} x2={fx1} y2={flip(fy1)} className="layout-piece-front" />
      <text
        x={piece.x}
        y={flip(piece.y)}
        fontSize={fontSize}
        transform={vertical ? `rotate(-90 ${piece.x} ${flip(piece.y)})` : undefined}
      >
        {piece.label}
      </text>
    </g>
  );
}

function Traffic({ flow, flip }) {
  const size = flow.cellSize;
  return (
    <g className="layout-traffic">
      {flow.cells.map(([x, y, count]) => (
        <rect
          key={`${x},${y}`}
          x={x - size / 2}
          y={flip(y) - size / 2}
          width={size}
          height={size}
          opacity={0.15 + 0.6 * (count / flow.maxCount)}
        />
      ))}
    </g>
  );
}

// With `onEdit`, furniture can be dragged (or moved with the arrow keys and turned with R).
// onEdit(nextLayout, done) is called while a piece moves, with done = true once the move is finished.
const LayoutView = ({
  layout, showOpenSpace = true, showTraffic = false, onEdit, selectedId, onSelect = () => {}, svgRef, className,
}) => {
  const { room, furniture, metrics } = layout;
  const flip = (y) => room.length - y;
  const flagged = new Set([...(metrics.unreachable || []), ...(metrics.cramped || [])]);
  const open = metrics.openSpace;
  const ownRef = useRef(null);
  const ref = svgRef || ownRef;
  const drag = useRef(null);

  const toRoom = (event) => {
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(ref.current.getScreenCTM().inverse());
    return [point.x, flip(point.y)];
  };

  const handlersFor = (piece) => onEdit && {
    onFocus: () => onSelect(piece.id),
    onPointerDown: (event) => {
      event.preventDefault();
      event.currentTarget.setPointerCapture?.(event.pointerId);
      const [x, y] = toRoom(event);
      drag.current = { dx: piece.x - x, dy: piece.y - y, moved: false };
      onSelect(piece.id);
    },
    onPointerMove: (event) => {
      if (!drag.current) return;
      const [x, y] = toRoom(event);
      const next = movePiece(layout, piece.id, x + drag.current.dx, y + drag.current.dy);
      const moved = next.furniture.find((p) => p.id === piece.id);
      if (moved.x !== piece.x || moved.y !== piece.y) {
        drag.current.moved = true;
        onEdit(next, false);
      }
    },
    onPointerUp: () => {
      if (drag.current?.moved) onEdit(layout, true);
      drag.current = null;
    },
    onKeyDown: (event) => {
      const step = KEY_STEPS[event.key];
      if (step) {
        event.preventDefault();
        const distance = event.shiftKey ? 0.25 : 1;
        onEdit(movePiece(layout, piece.id, piece.x + step[0] * distance, piece.y + step[1] * distance), true);
      } else if (event.key === 'r' || event.key === 'R') {
        onEdit(rotatePiece(layout, piece.id), true);
      }
    },
  };

  return (
    <svg
      ref={ref}
      className={`layout-view${onEdit ? ' layout-view-editable' : ''}${className ? ` ${className}` : ''}`}
      viewBox={`${-MARGIN} ${-MARGIN} ${room.width + 2 * MARGIN} ${room.length + 2 * MARGIN}`}
      role="img"
      aria-label={`Room layout, ${room.width} by ${room.length} feet`}
    >
      <rect x={0} y={0} width={room.width} height={room.length} className="layout-floor" />
      {showOpenSpace && open && open.radius > 0 && (
        <circle cx={open.x} cy={flip(open.y)} r={open.radius} className="layout-open-space">
          <title>{`Largest open area: ${(open.radius * 2).toFixed(1)} ft across`}</title>
        </circle>
      )}
      {showTraffic && layout.flow && <Traffic flow={layout.flow} flip={flip} />}
      <rect
        x={-WALL / 2}
        y={-WALL / 2}
        width={room.width + WALL}
        height={room.length + WALL}
        className="layout-walls"
        strokeWidth={WALL}
      />
      {room.windows.map((w, i) => <Window key={`w${i}`} room={room} window={w} flip={flip} />)}
      {room.doors.map((d, i) => <Door key={`d${i}`} room={room} door={d} flip={flip} />)}
      {furniture.map((piece) => (
        <Piece
          key={piece.id}
          piece={piece}
          flip={flip}
          flagged={flagged.has(piece.id)}
          selected={piece.id === selectedId}
          handlers={handlersFor(piece)}
        />
      ))}
      <text x={room.width / 2} y={room.length + MARGIN * 0.75} className="layout-dimension">
        {`${room.width} ft`}
      </text>
      <text
        x={-MARGIN * 0.6}
        y={room.length / 2}
        className="layout-dimension"
        transform={`rotate(-90 ${-MARGIN * 0.6} ${room.length / 2})`}
      >
        {`${room.length} ft`}
      </text>
    </svg>
  );
};

export default LayoutView;
