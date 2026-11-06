const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const cors = require('cors');

const PORT = process.env.PORT || 5000;
const CLIENT_ORIGIN = process.env.CLIENT_ORIGIN || 'http://localhost:3000';
const SCRIPT_PATH = path.join(__dirname, 'placement_generation.py');
const SCRIPT_TIMEOUT_MS = 120000; // the copilot may call the Claude API twice

// Prefer the server's virtualenv if it exists, then $PYTHON, then the platform default.
function resolvePython() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const venvPython = [
    path.join(__dirname, '.venv', 'Scripts', 'python.exe'),
    path.join(__dirname, '.venv', 'bin', 'python.exe'), // MSYS2 Python on Windows
    path.join(__dirname, '.venv', 'bin', 'python'),
  ].find((candidate) => fs.existsSync(candidate));
  if (venvPython) return venvPython;
  return process.platform === 'win32' ? 'python' : 'python3';
}

const PYTHON = resolvePython();

function runPlacementScript(args, input) {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON, [SCRIPT_PATH, ...args], {
      cwd: __dirname,
      timeout: SCRIPT_TIMEOUT_MS,
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (data) => { stdout += data; });
    child.stderr.on('data', (data) => { stderr += data; });
    child.on('error', reject);
    child.on('close', (code) => {
      if (stderr) console.error('placement_generation.py stderr:', stderr.trim());
      let result;
      try {
        result = JSON.parse(stdout.trim().split('\n').pop());
      } catch (e) {
        return reject(new Error(`Unexpected script output (exit code ${code})`));
      }
      resolve({ code, result });
    });

    child.stdin.end(input === undefined ? '' : JSON.stringify(input));
  });
}

// The options only change when the Python code does, so ask once and reuse the answer.
let optionsPromise = null;
function getOptions() {
  if (!optionsPromise) {
    optionsPromise = runPlacementScript(['--describe']).then(({ code, result }) => {
      if (code !== 0) throw new Error(result.error || 'Could not load options');
      return result;
    });
    optionsPromise.catch(() => { optionsPromise = null; });
  }
  return optionsPromise;
}

const app = express();
app.use(cors({ origin: CLIENT_ORIGIN }));
app.use(express.json({ limit: '100kb' }));

app.get('/api/options', async (req, res) => {
  try {
    res.json(await getOptions());
  } catch (err) {
    console.error('Failed to load options:', err);
    res.status(500).json({ error: 'Could not load options' });
  }
});

async function runAndRespond(res, args, input) {
  try {
    const { code, result } = await runPlacementScript(args, input);
    if (code === 0 && !result.error) {
      return res.json(result);
    }
    // 2 = invalid input, 3 = furniture does not fit; both are the client's to fix
    const status = code === 2 || code === 3 ? 400 : 500;
    return res.status(status).json({ error: result.error || 'Layout generation failed' });
  } catch (err) {
    console.error('Failed to run placement_generation.py:', err);
    return res.status(500).json({ error: 'Layout generation failed' });
  }
}

app.post('/api/generate', (req, res) => {
  const { preset, room, furniture, notes, seed, preferences } = req.body || {};
  return runAndRespond(res, [], { preset, room, furniture, notes, seed, preferences });
});

// Change an existing layout as a chat message asks ("move the bed under the window")
app.post('/api/refine', (req, res) => {
  const { request, layout, message, history } = req.body || {};
  return runAndRespond(res, ['--refine'], { request, layout, message, history });
});

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT} (python: ${PYTHON})`);
  });
}

module.exports = app;
