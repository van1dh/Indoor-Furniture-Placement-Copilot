import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const ResultPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { imagePath } = location.state || {};

  if (!imagePath) {
    return <p>Not received. Try again.</p>;
  }

  console.log('Image path:', imagePath);
  return (
    <div className="result-container">
      <button onClick={() => navigate(-1)}>Back</button>
      <h1>Layout Design</h1>
      <img src={imagePath} alt="Generated Layout" className="result-image" />
    </div>
  );
};

export default ResultPage;

