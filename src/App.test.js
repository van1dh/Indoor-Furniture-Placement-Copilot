import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';
import GenerationPage from './GenerationPage';
import LayoutView from './LayoutView';
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
  defaultPreset: 'default',
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
      preset: 'default',
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
  expect(await screen.findByRole('combobox', { name: /layout goal/i })).toHaveValue('default');
  expect(screen.getByText('Balanced layout.')).toBeInTheDocument();
  expect(screen.getByRole('spinbutton', { name: 'Bed count' })).toHaveValue(1);
  expect(screen.getByRole('spinbutton', { name: 'Desk width' })).toHaveValue(4);
  expect(global.fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/options$/), undefined);
});
