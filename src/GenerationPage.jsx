import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { buildRequest, fetchOptions, formFromOptions, generateLayout, validateForm } from './api';
import './GenerationPage.css';

function OpeningList({ kind, items, walls, onChange }) {
  const update = (i, field, value) => onChange(items.map((o, j) => (j === i ? { ...o, [field]: value } : o)));
  return (
    <fieldset className="form-section">
      <legend>{kind}s</legend>
      {items.map((o, i) => (
        <div className="form-row" key={i}>
          <label>
            Wall
            <select value={o.wall} onChange={(e) => update(i, 'wall', e.target.value)}>
              {walls.map((w) => <option key={w} value={w}>{w}</option>)}
            </select>
          </label>
          <label>
            Offset (ft)
            <input type="number" min="0" step="0.5" value={o.offset} onChange={(e) => update(i, 'offset', e.target.value)} />
          </label>
          <label>
            Width (ft)
            <input type="number" min="0" step="0.5" value={o.width} onChange={(e) => update(i, 'width', e.target.value)} />
          </label>
          <button
            type="button"
            className="icon-button"
            aria-label={`Remove ${kind.toLowerCase()} ${i + 1}`}
            onClick={() => onChange(items.filter((_, j) => j !== i))}
          >
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        className="link-button"
        onClick={() => onChange([...items, { wall: walls[0], offset: '1', width: kind === 'Door' ? '3' : '4' }])}
      >
        + Add {kind.toLowerCase()}
      </button>
    </fieldset>
  );
}

const GenerationPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState(location.state?.form || null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchOptions()
      .then((opts) => {
        if (cancelled) return;
        setOptions(opts);
        setForm((current) => current || formFromOptions(opts));
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => { cancelled = true; };
  }, []);

  const setField = (field, value) => setForm({ ...form, [field]: value });
  const setFurniture = (type, field, value) =>
    setForm({ ...form, furniture: { ...form.furniture, [type]: { ...form.furniture[type], [field]: value } } });

  const handleSubmit = async (e) => {
    e.preventDefault();
    const validationError = validateForm(form, options);
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setLoading(true);
    try {
      const request = buildRequest(form);
      const layout = await generateLayout(request);
      navigate('/result', { state: { form, request, layout } });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="generation-container">
      <button className="back-button" onClick={() => navigate('/')}>
        Back
      </button>
      {!form || !options ? (
        <div className="form-container">
          {error ? <p className="form-error" role="alert">{error}</p> : <p>Loading…</p>}
        </div>
      ) : (
        <form className="form-container" onSubmit={handleSubmit} noValidate>
          <fieldset className="form-section">
            <legend>Who is the room for?</legend>
            <select value={form.preset} onChange={(e) => setField('preset', e.target.value)} aria-label="Layout goal">
              <option value="auto">{options.autoPreset.label}</option>
              {Object.entries(options.presets).map(([name, p]) => (
                <option key={name} value={name}>{p.label}</option>
              ))}
            </select>
            <p className="form-hint">{(options.presets[form.preset] || options.autoPreset).description}</p>
          </fieldset>

          <fieldset className="form-section">
            <legend>Room</legend>
            <div className="form-row">
              <label>
                Width (ft)
                <input type="number" step="0.5" value={form.width} onChange={(e) => setField('width', e.target.value)} />
              </label>
              <label>
                Length (ft)
                <input type="number" step="0.5" value={form.length} onChange={(e) => setField('length', e.target.value)} />
              </label>
            </div>
          </fieldset>

          <OpeningList kind="Door" items={form.doors} walls={options.walls} onChange={(v) => setField('doors', v)} />
          <OpeningList kind="Window" items={form.windows} walls={options.walls} onChange={(v) => setField('windows', v)} />

          <fieldset className="form-section">
            <legend>Furniture</legend>
            <table className="furniture-table">
              <thead>
                <tr><th scope="col">Type</th><th scope="col">Count</th><th scope="col">Width (ft)</th><th scope="col">Depth (ft)</th></tr>
              </thead>
              <tbody>
                {Object.entries(options.furniture).map(([type, spec]) => (
                  <tr key={type}>
                    <th scope="row">{spec.label}</th>
                    {['count', 'width', 'depth'].map((field) => (
                      <td key={field}>
                        <input
                          type="number"
                          min="0"
                          step={field === 'count' ? '1' : '0.5'}
                          aria-label={`${spec.label} ${field}`}
                          value={form.furniture[type][field]}
                          onChange={(e) => setFurniture(type, field, e.target.value)}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </fieldset>

          <label>
            Notes for the copilot
            <textarea
              name="notes"
              maxLength={options.limits.notes_max}
              placeholder="e.g. Our toddler plays here a lot. I'd like the bed by the window and the desk away from the door."
              value={form.notes}
              onChange={(e) => setField('notes', e.target.value)}
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? 'Generating…' : 'Generate!'}
          </button>
        </form>
      )}
    </div>
  );
};

export default GenerationPage;
