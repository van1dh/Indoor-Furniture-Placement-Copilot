import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './GenerationPage.css';

const GenerationPage = () => {
  const [formData, setFormData] = useState({
    bed: '',
    desk: '',
    tv: '',
    wardrobe: '',
    notes: '',
  });
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log('Fetching URL:', 'http://localhost:5000/api/generate');// 调试前端提交数据
  
    fetch('http://localhost:5000/api/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formData),
    })
      .then((response) => {
        console.log('Response status:', response.status); // 检查响应状态码
        if (!response.ok) {
          throw new Error('Failed to fetch data');
        }
        return response.json();
      })
      .then((data) => {
        console.log('Data received:', data); // 检查后端返回的数据
        navigate('/result', { state: { imagePath: data.imagePath } });
      })
      .catch((error) => {
        console.error('Error during fetch:', error.message); // 捕获请求错误
      });
  };
  
  
  

  return (
    <div className="generation-container">
      <button className="back-button" onClick={() => navigate(-1)}>
        Back
      </button>
      <form className="form-container" onSubmit={handleSubmit}>
        <label>
          Bed Count:
          <input
            type="number"
            name="bed"
            value={formData.bed}
            onChange={handleChange}
          />
        </label>
        <label>
          Desk Count:
          <input
            type="number"
            name="desk"
            value={formData.desk}
            onChange={handleChange}
          />
        </label>
        <label>
          TV Count:
          <input
            type="number"
            name="tv"
            value={formData.tv}
            onChange={handleChange}
          />
        </label>
        <label>
          Wardrobe Count:
          <input
            type="number"
            name="wardrobe"
            value={formData.wardrobe}
            onChange={handleChange}
          />
        </label>
        <label>
          Note:
          <textarea
            name="notes"
            value={formData.notes}
            onChange={handleChange}
          />
        </label>
        <button type="submit">Generate!</button>
      </form>
    </div>
  );
};

export default GenerationPage;


