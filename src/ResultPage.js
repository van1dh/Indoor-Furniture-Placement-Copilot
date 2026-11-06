import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import LayoutView from './LayoutView';
import { generateLayout } from './api';
import './ResultPage.css';

const ResultPage = () => {
  const navigate = useNavigate();
  const { form, request, layout: initialLayout } = useLocation().state || {};
  const [layout, setLayout] = useState(initialLayout);
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

  const regenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      setLayout(await generateLayout({ ...request, seed: Math.floor(Math.random() * 2 ** 31) }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const { metrics, warnings } = layout;
  const open = metrics.openSpace;

  return (
    <div className="result-container">
      <button className="back-button" onClick={() => navigate('/generation', { state: { form } })}>
        Edit
      </button>
      <div className="result-content">
        <h2>Layout Design</h2>
        <LayoutView layout={layout} />
        <div className="result-summary">
          <p>
            Largest open area: <strong>{(open.radius * 2).toFixed(1)} ft</strong> across (green circle).
            Walkways are checked at {Math.round(metrics.walkwayWidth * 12)} in wide.
            The heavy edge of each piece is its front.
          </p>
          {warnings.length > 0 ? (
            <ul className="result-warnings">
              {warnings.map((w) => <li key={w}>{w}</li>)}
            </ul>
          ) : (
            <p className="result-ok">Every piece can be reached from a door and has room in front of it.</p>
          )}
          {layout.notes && <p className="result-notes">Notes: {layout.notes}</p>}
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button" onClick={regenerate} disabled={loading}>
          {loading ? 'Generating…' : 'Try another layout'}
        </button>
      </div>
    </div>
  );
};

export default ResultPage;
