import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';
import GenerationPage from './GenerationPage';
import LayoutView from './LayoutView';
import ResultPage from './ResultPage';
import { buildRequest, formFromOptions, validateForm } from './api';
import { movePiece, placements, rotatePiece } from './editing';
import { layoutFilename, standaloneSvg } from './exportLayout';

const options = {
  furniture: {
    bed: { label: 'Bed', width: 5, depth: 6.5 },
    desk: { label: 'Desk', width: 4, depth: 2 },
  },
  presets: {
    default: { label: 'Balanced', description: 'Balanced layout.' },
    child_safe: { label: 'Child-safe', description: 'Play area.' },
  },
  defaultPreset: 'auto',
  autoPreset: { label: 'Let the copilot decide', description: 'Picks a goal from your notes.' },
  walls: ['bottom', 'right', 'top', 'left'],
  limits: {
    room_min: 8, room_max: 60, furniture_min: 1, furniture_max: 15, max_per_type: 6, max_total: 16,
    opening_min: 2, opening_max: 12, max_doors: 3, max_windows: 6, notes_max: 500,
  },
  defaults: {
    room: { width: 16, length: 14, doors: [{ wall: 'bottom', offset: 1, width: 3 }], windows: [] },
    furniture: { bed: 1, desk: 0 },
  },
};

const layout = {
  room: { width: 16, length: 14, doors: [{ wall: 'bottom', offset: 1, width: 3 }], windows: [{ wall: 'top', offset: 5, width: 5 }] },
  furniture: [
    {
      id: 'bed-1', type: 'bed', label: 'Bed', x: 12.75, y: 9, width: 5, depth: 6.5, rotation: 270,
      footprint: { width: 6.5, length: 5 }, front: { x: 9.5, y: 9, direction: [-1, 0] },
    },
    {
      id: 'desk-1', type: 'desk', label: 'Desk', x: 2, y: 13, width: 4, depth: 2, rotation: 180,
      footprint: { width: 4, length: 2 }, front: { x: 2, y: 12, direction: [0, -1] },
    },
  ],
  metrics: { openSpace: { x: 6, y: 6, radius: 4 }, walkwayWidth: 2.5, unreachable: ['desk-1'], cramped: [] },
  warnings: [],
  preferences: [
    { kind: 'near', piece: 'bed', target: 'window', strength: 'high', reason: 'light', met: true, text: 'Bed near the window' },
  ],
  flow: { cellSize: 0.5, cells: [[5, 5, 1], [5.5, 5, 2]], maxCount: 2, occupants: 1, dailyDistance: 42.5, missedTrips: 0 },
  copilot: {
    online: true, provider: 'openai', model: 'qwen3', reply: 'Set it up.',
    explanation: 'The bed is by the window for morning light.', notices: [],
  },
  request: { preset: 'default', preferences: [{ kind: 'near', piece: 'bed', target: 'window', strength: 'high' }], seed: 1 },
};

test('renders the welcome page', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: /indoor furniture placement copilot/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /try generation/i })).toBeInTheDocument();
});

describe('form helpers', () => {
  test('default form is valid and builds a numeric request', () => {
    const form = formFromOptions(options);
    expect(validateForm(form, options)).toBeNull();
    expect(buildRequest(form)).toEqual({
      preset: 'auto',
      room: { width: 16, length: 14, doors: [{ wall: 'bottom', offset: 1, width: 3 }], windows: [] },
      furniture: [
        { type: 'bed', count: 1, width: 5, depth: 6.5 },
        { type: 'desk', count: 0, width: 4, depth: 2 },
      ],
      notes: '',
    });
  });

  test.each([
    ['room too small', (f) => ({ ...f, width: '3' }), /room width/i],
    ['no doors', (f) => ({ ...f, doors: [] }), /at least one door/i],
    ['door off the wall', (f) => ({ ...f, doors: [{ wall: 'bottom', offset: '15', width: '3' }] }), /does not fit/i],
    ['no furniture', (f) => ({ ...f, furniture: { ...f.furniture, bed: { ...f.furniture.bed, count: '0' } } }), /at least one piece/i],
    ['fractional count', (f) => ({ ...f, furniture: { ...f.furniture, bed: { ...f.furniture.bed, count: '1.5' } } }), /bed count/i],
    ['bad size', (f) => ({ ...f, furniture: { ...f.furniture, bed: { ...f.furniture.bed, width: '' } } }), /bed width/i],
  ])('rejects %s', (_, change, message) => {
    expect(validateForm(change(formFromOptions(options)), options)).toMatch(message);
  });
});

test('LayoutView draws each piece and flags unreachable ones', () => {
  const { container } = render(<LayoutView layout={layout} />);
  expect(screen.getByRole('img', { name: /16 by 14 feet/i })).toBeInTheDocument();
  expect(screen.getByText('Bed')).toBeInTheDocument();
  expect(screen.getByText('Desk')).toBeInTheDocument();
  expect(container.querySelectorAll('.layout-piece-flagged')).toHaveLength(1);
  expect(container.querySelector('.layout-piece-desk')).toHaveClass('layout-piece-flagged');
  expect(container.querySelectorAll('.layout-door')).toHaveLength(1);
  expect(container.querySelectorAll('.layout-window')).toHaveLength(1);
});

test('GenerationPage builds its form from the server options', async () => {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(options) });
  render(
    <MemoryRouter>
      <GenerationPage />
    </MemoryRouter>,
  );
  expect(await screen.findByRole('combobox', { name: /layout goal/i })).toHaveValue('auto');
  expect(screen.getByText('Picks a goal from your notes.')).toBeInTheDocument();
  expect(screen.getByRole('spinbutton', { name: 'Bed count' })).toHaveValue(1);
  expect(screen.getByRole('spinbutton', { name: 'Desk width' })).toHaveValue(4);
  expect(global.fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/options$/), undefined);
});

test('LayoutView draws the traffic heatmap only when asked', () => {
  const { container, rerender } = render(<LayoutView layout={layout} />);
  expect(container.querySelectorAll('.layout-traffic rect')).toHaveLength(0);
  rerender(<LayoutView layout={layout} showTraffic />);
  expect(container.querySelectorAll('.layout-traffic rect')).toHaveLength(2);
});

describe('ResultPage', () => {
  const renderResult = () => render(
    <MemoryRouter initialEntries={[{ pathname: '/result', state: { layout } }]}>
      <ResultPage />
    </MemoryRouter>,
  );

  test('shows the copilot explanation, preferences and walking distance', () => {
    renderResult();
    expect(screen.getByText('The bed is by the window for morning light.')).toBeInTheDocument();
    expect(screen.getByText('Bed near the window')).toBeInTheDocument();
    expect(screen.getByText('42.5 ft')).toBeInTheDocument();
    expect(screen.queryByText(/copilot is offline/i)).not.toBeInTheDocument();
    expect(screen.getByText('Copilot: qwen3')).toBeInTheDocument();
  });

  test('sends chat messages to the refine endpoint and shows the reply', async () => {
    const refined = { ...layout, copilot: { ...layout.copilot, reply: 'Moved the desk.' } };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(refined) });
    renderResult();
    fireEvent.change(screen.getByRole('textbox', { name: /message to the copilot/i }), {
      target: { value: 'Move the desk' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('Moved the desk.')).toBeInTheDocument();
    expect(screen.getByText('Move the desk')).toBeInTheDocument();
    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toMatch(/\/api\/refine$/);
    const body = JSON.parse(init.body);
    expect(body).toMatchObject({ message: 'Move the desk', history: [], request: layout.request });
    expect(body.layout.furniture[0]).toEqual({ id: 'bed-1', x: 12.75, y: 9, rotation: 270 });
  });

  test('moving a piece with the keyboard re-scores it, and undo brings it back', async () => {
    const scored = { ...layout, warnings: ['Bed overlaps Desk.'] };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(scored) });
    renderResult();
    const bed = screen.getByRole('button', { name: /^bed: drag/i });
    fireEvent.focus(bed);
    fireEvent.keyDown(bed, { key: 'ArrowLeft' });

    expect(await screen.findByText('Bed overlaps Desk.')).toBeInTheDocument();
    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toMatch(/\/api\/evaluate$/);
    expect(JSON.parse(init.body).layout.furniture[0]).toEqual({ id: 'bed-1', x: 11.75, y: 9, rotation: 270 });

    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(screen.queryByText('Bed overlaps Desk.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Undo' })).toBeDisabled();
  });

  test('rotates the selected piece', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(layout) });
    renderResult();
    expect(screen.getByRole('button', { name: 'Rotate' })).toBeDisabled();
    fireEvent.focus(screen.getByRole('button', { name: /^desk: drag/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Rotate Desk' }));
    await screen.findByRole('button', { name: 'Undo' });
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.layout.furniture[1]).toEqual({ id: 'desk-1', x: 2, y: 12, rotation: 270 });
  });

  test('saves layouts to compare and opens them again', () => {
    renderResult();
    fireEvent.click(screen.getByRole('button', { name: 'Save to compare' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save to compare' }));
    expect(screen.getByRole('region', { name: 'Layout A' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Layout B' })).toHaveTextContent('42.5 ft');
    fireEvent.click(screen.getAllByRole('button', { name: 'Remove' })[0]);
    expect(screen.queryByRole('region', { name: 'Layout A' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    expect(screen.getByRole('button', { name: 'Undo' })).toBeEnabled();
  });

  test('removing a preference regenerates without it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ ...layout, preferences: [] }) });
    renderResult();
    fireEvent.click(screen.getByRole('button', { name: /remove preference: bed near the window/i }));
    await screen.findByRole('button', { name: /try another layout/i });
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).preferences).toEqual([]);
  });
});

describe('editing', () => {
  test('moves a piece on a quarter-foot grid and keeps it inside the room', () => {
    const moved = movePiece(layout, 'bed-1', 3.1, 20);
    const bed = moved.furniture[0];
    expect([bed.x, bed.y]).toEqual([3.25, 11.5]); // the bed is 6.5 x 5 ft on the floor, the room 14 ft long
    expect(bed.front).toEqual({ x: 0, y: 11.5, direction: [-1, 0] });
    expect(moved.furniture[1]).toBe(layout.furniture[1]);
  });

  test('rotates a piece a quarter turn clockwise and swaps its footprint', () => {
    const desk = rotatePiece(layout, 'desk-1').furniture[1];
    expect(desk.rotation).toBe(270);
    expect(desk.footprint).toEqual({ width: 2, length: 4 });
    expect([desk.x, desk.y]).toEqual([2, 12]); // pulled back inside the top wall
    expect(placements(rotatePiece(layout, 'bed-1'))[0].rotation).toBe(0);
  });
});

describe('export', () => {
  test('builds a standalone SVG with inline styles', () => {
    const { container } = render(<LayoutView layout={layout} />);
    const markup = standaloneSvg(container.querySelector('svg'), 10);
    expect(markup).toMatch(/^<svg[^>]+xmlns="http:\/\/www.w3.org\/2000\/svg"/);
    expect(markup).toMatch(/width="190"/); // (16 + 2 * 1.5) ft at 10 px per foot
    expect(markup).toContain('style=');
  });

  test('names files after the preset and seed', () => {
    expect(layoutFilename({ preset: 'default', seed: 1 }, 'png')).toBe('layout-default-1.png');
  });
});
