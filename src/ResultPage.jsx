import React, { useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import LayoutView from './LayoutView';
import { evaluateLayout, generateLayout, refineLayout } from './api';
import { rotatePiece } from './editing';
import { downloadJson, downloadPng } from './exportLayout';
import './ResultPage.css';

const MAX_UNDO = 20;
const MAX_SAVED = 4;

function Preferences({ preferences, onRemove, disabled }) {
  if (preferences.length === 0) return null;
  return (
    <div className="result-section">
      <h3>Your preferences</h3>
      <ul className="preference-list">
        {preferences.map((p, i) => (
          <li key={`${p.kind}-${p.piece}-${p.target}`} className={p.met ? 'preference-met' : 'preference-unmet'}>
            <span aria-label={p.met ? 'met' : 'not met'}>{p.met ? '✓' : '✗'}</span>
            <span className="preference-text" title={p.reason}>{p.text}</span>
            <button
              type="button"
              className="icon-button"
              aria-label={`Remove preference: ${p.text}`}
              disabled={disabled}
              onClick={() => onRemove(i)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Chat({ history, onSend, loading }) {
  const [message, setMessage] = useState('');
  const send = (e) => {
    e.preventDefault();
    if (!message.trim()) return;
    onSend(message.trim());
    setMessage('');
  };
  return (
    <div className="result-section">
      <h3>Ask for changes</h3>
      {history.length > 0 && (
        <ol className="chat-log">
          {history.map((turn, i) => (
            <li key={i} className={`chat-${turn.role}`}>{turn.text}</li>
          ))}
        </ol>
      )}
      <form className="chat-form" onSubmit={send}>
        <input
          type="text"
          aria-label="Message to the copilot"
          placeholder="e.g. Put the bed under the window"
          maxLength={500}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="primary-button" disabled={loading || !message.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

function stats(layout) {
  return {
    openArea: layout.metrics.openSpace.radius * 2,
    walk: layout.flow.dailyDistance,
    warnings: layout.warnings.length,
    met: layout.preferences.filter((p) => p.met).length,
  };
}

// Saved layouts side by side, with the best value of each measure in bold
function Compare({ saved, onOpen, onRemove }) {
  if (saved.length === 0) return null;
  const all = saved.map((s) => stats(s.layout));
  const best = {
    openArea: Math.max(...all.map((s) => s.openArea)),
    walk: Math.min(...all.map((s) => s.walk)),
    warnings: Math.min(...all.map((s) => s.warnings)),
    met: Math.max(...all.map((s) => s.met)),
  };
  const value = (s, key, text) => (saved.length > 1 && s[key] === best[key] ? <strong>{text}</strong> : text);
  return (
    <div className="result-section">
      <h3>Compare layouts</h3>
      <div className="compare-grid">
        {saved.map(({ name, layout }, i) => {
          const s = all[i];
          return (
            <section key={name} className="compare-card" aria-label={name}>
              <h4>{name}</h4>
              <LayoutView layout={layout} showOpenSpace={false} className="compare-view" />
              <dl>
                <dt>Open area</dt>
                <dd>{value(s, 'openArea', `${s.openArea.toFixed(1)} ft`)}</dd>
                <dt>Walking a day</dt>
                <dd>{value(s, 'walk', `${s.walk} ft`)}</dd>
                <dt>Warnings</dt>
                <dd>{value(s, 'warnings', s.warnings)}</dd>
                {layout.preferences.length > 0 && (
                  <>
                    <dt>Preferences met</dt>
                    <dd>{value(s, 'met', `${s.met} of ${layout.preferences.length}`)}</dd>
                  </>
                )}
              </dl>
              <div className="compare-actions">
                <button type="button" className="link-button" onClick={() => onOpen(i)}>Open</button>
                <button type="button" className="link-button" onClick={() => onRemove(i)}>Remove</button>
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

const ResultPage = () => {
  const navigate = useNavigate();
  const { form, layout: initialLayout } = useLocation().state || {};
  const [layout, setLayout] = useState(initialLayout);
  const [history, setHistory] = useState([]);
  const [showTraffic, setShowTraffic] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [past, setPast] = useState([]); // earlier layouts, for undo
  const [saved, setSaved] = useState([]); // [{ name, layout }] to compare
  const [savedCount, setSavedCount] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const svgRef = useRef(null);
  const editStart = useRef(null); // the layout before the current drag
  const latestEdit = useRef(0); // ignore re-scores that a newer change has overtaken

  if (!layout) {
    return (
      <div className="result-container">
        <div className="result-content">
          <h2>Layout Design</h2>
          <p>
            No layout generated yet. <Link to="/generation">Generate one</Link>.
          </p>
        </div>
      </div>
    );
  }

  const remember = (previous) => setPast((p) => [...p, previous].slice(-MAX_UNDO));

  const run = async (action) => {
    setLoading(true);
    setError(null);
    try {
      return await action();
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  };

  // Replace the layout with what `action` returns, keeping the current one for undo
  const change = (action) => run(async () => {
    const next = await action();
    latestEdit.current += 1;
    remember(layout);
    setLayout(next);
    return next;
  });

  const regenerate = () => change(() => generateLayout({
    ...layout.request, seed: Math.floor(Math.random() * 2 ** 31),
  }));

  const removePreference = (index) => change(() => {
    const preferences = layout.request.preferences.filter((_, i) => i !== index);
    return generateLayout({ ...layout.request, preferences });
  });

  const send = async (message) => {
    const next = await change(() => refineLayout(layout, message, history));
    if (!next) return;
    setHistory([
      ...history,
      { role: 'user', text: message },
      { role: 'assistant', text: next.copilot.reply || 'Done.' },
    ]);
  };

  // Furniture moved by hand: show it at once, then let the server re-score it
  const edit = async (next, done) => {
    if (!editStart.current) editStart.current = layout;
    setLayout(next);
    if (!done) return;
    remember(editStart.current);
    editStart.current = null;
    const request = ++latestEdit.current;
    setError(null);
    try {
      const scored = await evaluateLayout(next);
      if (request === latestEdit.current) setLayout(scored);
    } catch (err) {
      if (request === latestEdit.current) setError(err.message);
    }
  };

  const undo = () => {
    latestEdit.current += 1;
    setLayout(past[past.length - 1]);
    setPast(past.slice(0, -1));
  };

  const save = () => {
    const name = `Layout ${String.fromCharCode(65 + (savedCount % 26))}`;
    setSavedCount(savedCount + 1);
    setSaved([...saved, { name, layout }].slice(-MAX_SAVED));
  };

  const openSaved = (index) => {
    latestEdit.current += 1;
    remember(layout);
    setLayout(saved[index].layout);
  };

  const { metrics, warnings, copilot, flow } = layout;
  const open = metrics.openSpace;
  const selected = layout.furniture.find((p) => p.id === selectedId);

  return (
    <div className="result-container">
      <button className="back-button" onClick={() => navigate('/generation', { state: { form } })}>
        Edit
      </button>
      <div className="result-content">
        <h2>Layout Design</h2>
        <LayoutView
          layout={layout}
          showTraffic={showTraffic}
          onEdit={loading ? undefined : edit}
          selectedId={selectedId}
          onSelect={setSelectedId}
          svgRef={svgRef}
        />
        <div className="result-toolbar">
          <label className="result-toggle">
            <input type="checkbox" checked={showTraffic} onChange={(e) => setShowTraffic(e.target.checked)} />
            Show daily foot traffic
          </label>
          <span className="result-toolbar-buttons">
            <button
              type="button"
              className="link-button"
              disabled={!selected || loading}
              onClick={() => edit(rotatePiece(layout, selected.id), true)}
            >
              {selected ? `Rotate ${selected.label}` : 'Rotate'}
            </button>
            <button type="button" className="link-button" disabled={past.length === 0 || loading} onClick={undo}>
              Undo
            </button>
            <button type="button" className="link-button" onClick={save}>Save to compare</button>
            <button
              type="button"
              className="link-button"
              onClick={() => downloadPng(svgRef.current, layout).catch((err) => setError(err.message))}
            >
              Download PNG
            </button>
            <button type="button" className="link-button" onClick={() => downloadJson(layout)}>
              Download JSON
            </button>
          </span>
        </div>
        <p className="result-hint">Drag furniture to move it; select a piece and press R to rotate it.</p>

        <div className="result-section">
          <p className="copilot-explanation">{copilot.explanation}</p>
          {copilot.online ? (
            copilot.model && <p className="copilot-model">Copilot: {copilot.model}</p>
          ) : (
            <p className="copilot-offline">
              The copilot is offline ({copilot.offlineReason}), so this summary comes from a template and
              notes and messages are only read for keywords.
            </p>
          )}
          {copilot.notices.map((n) => <p key={n} className="copilot-notice">{n}</p>)}
        </div>

        <div className="result-summary">
          <p>
            Largest open area: <strong>{(open.radius * 2).toFixed(1)} ft</strong> across (green circle).
            Walkways are checked at {Math.round(metrics.walkwayWidth * 12)} in wide.
            A typical day takes about <strong>{flow.dailyDistance} ft</strong> of walking per person.
            The heavy edge of each piece is its front.
          </p>
          {warnings.length > 0 ? (
            <ul className="result-warnings">
              {warnings.map((w) => <li key={w}>{w}</li>)}
            </ul>
          ) : (
            <p className="result-ok">Every piece can be reached from a door and has room in front of it.</p>
          )}
        </div>

        <Preferences preferences={layout.preferences} onRemove={removePreference} disabled={loading} />
        <Chat history={history} onSend={send} loading={loading} />
        <Compare saved={saved} onOpen={openSaved} onRemove={(i) => setSaved(saved.filter((_, j) => j !== i))} />

        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button" onClick={regenerate} disabled={loading}>
          {loading ? 'Working…' : 'Try another layout'}
        </button>
      </div>
    </div>
  );
};

export default ResultPage;
