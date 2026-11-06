import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import './ResultPage.css';

const ResultPage = () => {
  const imageUrl = useLocation().state?.imageUrl;

  return (
    <div className="result-container">
      <button className="back-button" onClick={() => window.history.back()}>
        Back
      </button>
      <div className="result-content">
        <h2>Layout Design</h2>
        {imageUrl ? (
          <img src={imageUrl} alt="Layout Design" className="result-image" />
        ) : (
          <p>
            No layout generated yet. <Link to="/generation">Generate one</Link>.
          </p>
        )}
      </div>
    </div>
  );
};

export default ResultPage;
