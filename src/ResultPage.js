import React from 'react';
import './ResultPage.css';

const ResultPage = () => {
  return (
    <div className="result-container">
      <button className="back-button" onClick={() => window.history.back()}>
        Back
      </button>
      <div className="result-content">
        <h2>Layout Design</h2>
        <img
          src="/room_layout.png"
          alt="Layout Design"
          className="result-image"
        />
      </div>
    </div>
  );
};

export default ResultPage;



