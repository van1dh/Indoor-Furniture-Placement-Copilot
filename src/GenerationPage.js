import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FURNITURE_TYPES, MAX_NOTES_LENGTH, MAX_PER_TYPE, generateLayout, validateForm } from './api';
import './GenerationPage.css';

const GenerationPage = () => {
  const [formData, setFormData] = useState({
    bed: '',
    desk: '',
    tv: '',
    wardrobe: '',
    notes: '',
  });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const validationError = validateForm(formData);
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setLoading(true);
    try {
      const imageUrl = await generateLayout(formData);
      navigate('/result', { state: { imageUrl } });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="generation-container">
      <button className="back-button" onClick={() => navigate(-1)}>
        Back
      </button>
      <form className="form-container" onSubmit={handleSubmit} noValidate>
        {FURNITURE_TYPES.map(({ name, label }) => (
          <label key={name}>
            {label}:
            <input
              type="number"
              name={name}
              min="0"
              max={MAX_PER_TYPE}
              step="1"
              value={formData[name]}
              onChange={handleChange}
            />
          </label>
        ))}
        <label>
          Note:
          <textarea
            name="notes"
            maxLength={MAX_NOTES_LENGTH}
            value={formData.notes}
            onChange={handleChange}
          />
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={loading}>
          {loading ? 'Generating…' : 'Generate!'}
        </button>
      </form>
    </div>
  );
};

export default GenerationPage;
