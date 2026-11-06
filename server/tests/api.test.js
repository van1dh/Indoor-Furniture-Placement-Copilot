const { test, before, after } = require('node:test');
const assert = require('node:assert');
const app = require('../index');

let server;
let baseUrl;

before(async () => {
  server = app.listen(0);
  await new Promise((resolve) => server.once('listening', resolve));
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

after(() => server.close());

const request = {
  preset: 'default',
  room: {
    width: 16,
    length: 14,
    doors: [{ wall: 'bottom', offset: 1, width: 3 }],
    windows: [{ wall: 'top', offset: 5, width: 5 }],
  },
  furniture: [
    { type: 'bed', count: 1 },
    { type: 'desk', count: 1 },
  ],
  notes: 'api test',
  seed: 3,
};

function post(body) {
  return fetch(`${baseUrl}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

test('serves the form options', async () => {
  const res = await fetch(`${baseUrl}/api/options`);
  assert.strictEqual(res.status, 200);
  const options = await res.json();
  assert.ok(options.furniture.bed.width > 0);
  assert.deepStrictEqual(Object.keys(options.presets).sort(), ['accessible', 'child_safe', 'default', 'shared']);
  assert.ok(options.defaults.room.doors.length > 0);
});

test('generates a layout', async () => {
  const res = await post(request);
  assert.strictEqual(res.status, 200);
  const layout = await res.json();
  assert.deepStrictEqual(layout.furniture.map((f) => f.type), ['bed', 'desk']);
  assert.strictEqual(layout.room.width, 16);
  assert.strictEqual(layout.seed, 3);
  assert.strictEqual(layout.notes, 'api test');
  assert.ok(Array.isArray(layout.warnings));
});

test('ignores fields outside the request schema', async () => {
  const res = await post({ ...request, extra: 'x'.repeat(100) });
  assert.strictEqual(res.status, 200);
});

test('rejects invalid input with 400 and a message', async () => {
  const invalid = [
    {},
    { ...request, furniture: [] },
    { ...request, preset: 'nope' },
    { ...request, room: { ...request.room, width: -1 } },
    { ...request, furniture: [{ type: 'sofa', count: 1, width: 15, depth: 3 }], room: { ...request.room, width: 10, length: 10 } },
  ];
  for (const body of invalid) {
    const res = await post(body);
    assert.strictEqual(res.status, 400, JSON.stringify(body));
    const { error } = await res.json();
    assert.ok(error);
  }
});
