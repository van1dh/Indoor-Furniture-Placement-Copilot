import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';
import GenerationPage from './GenerationPage';
import LayoutView from './LayoutView';
import ResultPage from './ResultPage';
import { buildRequest, formFromOptions, validateForm } from './api';

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
  copilot: { online: true, reply: 'Set it up.', explanation: 'The bed is by the window for morning light.', notices: [] },
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
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(options) });
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
  });

  test('sends chat messages to the refine endpoint and shows the reply', async () => {
    const refined = { ...layout, copilot: { ...layout.copilot, reply: 'Moved the desk.' } };
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(refined) });
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

  test('removing a preference regenerates without it', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ ...layout, preferences: [] }) });
    renderResult();
    fireEvent.click(screen.getByRole('button', { name: /remove preference: bed near the window/i }));
    await screen.findByRole('button', { name: /try another layout/i });
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).preferences).toEqual([]);
  });
});
