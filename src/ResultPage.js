import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import LayoutView from './LayoutView';
import { generateLayout, refineLayout } from './api';
import './ResultPage.css';

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

const ResultPage = () => {
  const navigate = useNavigate();
  const { form, layout: initialLayout } = useLocation().state || {};
  const [layout, setLayout] = useState(initialLayout);
  const [history, setHistory] = useState([]);
  const [showTraffic, setShowTraffic] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

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

  const regenerate = () => run(async () => {
    setLayout(await generateLayout({ ...layout.request, seed: Math.floor(Math.random() * 2 ** 31) }));
  });

  const removePreference = (index) => run(async () => {
    const preferences = layout.request.preferences.filter((_, i) => i !== index);
    setLayout(await generateLayout({ ...layout.request, preferences }));
  });

  const send = (message) => run(async () => {
    const next = await refineLayout(layout, message, history);
    setLayout(next);
    setHistory([
      ...history,
      { role: 'user', text: message },
      { role: 'assistant', text: next.copilot.reply || 'Done.' },
    ]);
  });

  const { metrics, warnings, copilot, flow } = layout;
  const open = metrics.openSpace;

  return (
    <div className="result-container">
      <button className="back-button" onClick={() => navigate('/generation', { state: { form } })}>
        Edit
      </button>
      <div className="result-content">
        <h2>Layout Design</h2>
        <LayoutView layout={layout} showTraffic={showTraffic} />
        <label className="result-toggle">
          <input type="checkbox" checked={showTraffic} onChange={(e) => setShowTraffic(e.target.checked)} />
          Show daily foot traffic
        </label>

        <div className="result-section">
          <p className="copilot-explanation">{copilot.explanation}</p>
          {!copilot.online && (
            <p className="copilot-offline">
              The Claude copilot is offline ({copilot.offlineReason}), so this summary comes from a template and
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

        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button" onClick={regenerate} disabled={loading}>
          {loading ? 'Working…' : 'Try another layout'}
        </button>
      </div>
    </div>
  );
};

export default ResultPage;
