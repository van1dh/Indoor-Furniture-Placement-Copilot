import React from 'react';
import { Link } from 'react-router-dom';
import './WelcomePage.css';

const WelcomePage = () => (
  <div className="welcome-container">
    <div className="welcome-content">
      <h1>Indoor Furniture Placement Copilot</h1>
      <h2>Copyright 2024 Yongyi Xie xyy0208@bu.edu</h2>
      <Link to="/generation">
        <button className="welcome-button">Try Generation!</button>
      </Link>
    </div>
  </div>
);

export default WelcomePage;


