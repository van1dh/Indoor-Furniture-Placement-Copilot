import { placements } from './editing';

// Empty when the API is served from the same origin as the app (as in the Docker image)
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';

async function request(path, options) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch (e) {
    throw new Error(`Cannot reach the server at ${API_BASE_URL}. Is it running?`);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Server error (${response.status})`);
  }
  return data;
}

// Furniture types, presets, limits and form defaults, as described by the server.
export function fetchOptions() {
  return request('/api/options');
}

function post(path, body) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function generateLayout(body) {
  return post('/api/generate', body);
}

// Ask the copilot to change a layout: `layout` is the current result, `history` the chat so far
// as [{ role: 'user' | 'assistant', text }].
export function refineLayout(layout, message, history) {
  return post('/api/refine', {
    request: layout.request,
    layout: { furniture: placements(layout) },
    message,
    history,
  });
}

// Score a layout arranged by hand, without moving anything
export function evaluateLayout(layout) {
  return post('/api/evaluate', { request: layout.request, layout: { furniture: placements(layout) } });
}

// Form state keeps every field as a string so inputs can be empty while the user types.
export function formFromOptions(options) {
  const { room, furniture } = options.defaults;
  const opening = (o) => ({ wall: o.wall, offset: String(o.offset), width: String(o.width) });
  return {
    preset: options.defaultPreset,
    width: String(room.width),
    length: String(room.length),
    doors: room.doors.map(opening),
    windows: room.windows.map(opening),
    furniture: Object.fromEntries(
      Object.entries(options.furniture).map(([type, spec]) => [
        type,
        { count: String(furniture[type] ?? 0), width: String(spec.width), depth: String(spec.depth) },
      ]),
    ),
    notes: '',
  };
}

export function buildRequest(form) {
  const opening = (o) => ({ wall: o.wall, offset: Number(o.offset), width: Number(o.width) });
  return {
    preset: form.preset,
    room: {
      width: Number(form.width),
      length: Number(form.length),
      doors: form.doors.map(opening),
      windows: form.windows.map(opening),
    },
    furniture: Object.entries(form.furniture).map(([type, f]) => ({
      type,
      count: f.count === '' ? 0 : Number(f.count),
      width: Number(f.width),
      depth: Number(f.depth),
    })),
    notes: form.notes,
  };
}

function checkNumber(value, label, min, max) {
  const n = Number(value);
  if (value === '' || !Number.isFinite(n) || n < min || n > max) {
    return `${label} must be between ${min} and ${max}.`;
  }
  return null;
}

// Returns an error message, or null if the form can be submitted. The server checks everything again.
export function validateForm(form, options) {
  const { limits } = options;
  const errors = [
    checkNumber(form.width, 'Room width', limits.room_min, limits.room_max),
    checkNumber(form.length, 'Room length', limits.room_min, limits.room_max),
  ];

  if (form.doors.length === 0) errors.push('Add at least one door.');
  for (const [kind, list] of [['Door', form.doors], ['Window', form.windows]]) {
    list.forEach((o, i) => {
      const name = `${kind} ${i + 1}`;
      errors.push(checkNumber(o.width, `${name} width`, limits.opening_min, limits.opening_max));
      errors.push(checkNumber(o.offset, `${name} offset`, 0, limits.room_max));
      const wallLength = Number(['bottom', 'top'].includes(o.wall) ? form.width : form.length);
      if (Number(o.offset) + Number(o.width) > wallLength) {
        errors.push(`${name} does not fit on the ${o.wall} wall.`);
      }
    });
  }

  let total = 0;
  for (const [type, f] of Object.entries(form.furniture)) {
    const label = options.furniture[type].label;
    const count = f.count === '' ? 0 : Number(f.count);
    if (!Number.isInteger(count) || count < 0 || count > limits.max_per_type) {
      errors.push(`${label} count must be a whole number from 0 to ${limits.max_per_type}.`);
      continue;
    }
    total += count;
    if (count > 0) {
      errors.push(checkNumber(f.width, `${label} width`, limits.furniture_min, limits.furniture_max));
      errors.push(checkNumber(f.depth, `${label} depth`, limits.furniture_min, limits.furniture_max));
    }
  }
  if (total === 0) errors.push('Add at least one piece of furniture.');
  if (total > limits.max_total) errors.push(`At most ${limits.max_total} pieces of furniture are supported.`);
  if (form.notes.length > limits.notes_max) errors.push(`Notes must be at most ${limits.notes_max} characters.`);

  return errors.find(Boolean) || null;
}
