const { test, before, after } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const app = require('../index');

let server;
let baseUrl;

before(async () => {
  server = app.listen(0);
  await new Promise((resolve) => server.once('listening', resolve));
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

after(() => server.close());

function post(body) {
  return fetch(`${baseUrl}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

test('generates a layout image and serves it', async () => {
  const res = await post({ bed: 1, desk: 1, tv: 1, wardrobe: 1, notes: 'api test' });
  assert.strictEqual(res.status, 200);
  const { imageUrl } = await res.json();
  assert.match(imageUrl, /^\/generated\/[0-9a-f]{32}\.png$/);

  const image = await fetch(`${baseUrl}${imageUrl}`);
  assert.strictEqual(image.status, 200);
  assert.strictEqual(image.headers.get('content-type'), 'image/png');

  fs.rmSync(path.join(__dirname, '..', imageUrl), { force: true });
});

test('each request gets its own image', async () => {
  const body = { bed: 1, desk: 0, tv: 0, wardrobe: 0 };
  const [a, b] = await Promise.all([post(body), post(body)]);
  const urlA = (await a.json()).imageUrl;
  const urlB = (await b.json()).imageUrl;
  assert.notStrictEqual(urlA, urlB);
  for (const url of [urlA, urlB]) fs.rmSync(path.join(__dirname, '..', url), { force: true });
});

test('rejects invalid input with 400 and a message', async () => {
  for (const body of [{}, { bed: '' }, { bed: -1 }, { bed: 'abc' }]) {
    const res = await post(body);
    assert.strictEqual(res.status, 400, JSON.stringify(body));
    const { error } = await res.json();
    assert.ok(error);
  }
});
