const express = require('express');
const { spawn } = require('child_process');
const path = require('path');
const bodyParser = require('body-parser');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(bodyParser.json());

app.use('/images', express.static(path.join(__dirname, 'images')));

app.post('/api/generate', (req, res) => {
    const { bed, desk, tv, wardrobe, notes } = req.body;
  
    if (!bed || !desk || !tv || !wardrobe) {
      return res.status(400).json({ error: 'Invalid input' });
    }
  
    const pythonProcess = spawn('python', [
      './placement_generation.py',
      bed,
      desk,
      tv,
      wardrobe,
      notes
    ]);
  
    let scriptOutput = '';
  
    pythonProcess.stdout.on('data', (data) => {
      scriptOutput += data.toString();
    });
  
    pythonProcess.stderr.on('data', (data) => {
      console.error('Python script error:', data.toString());
    });
  
    pythonProcess.on('close', (code) => {
      console.log(`Python script exited with code ${code}`);
      if (code !== 0) {
        return res.status(500).json({ error: 'Python script failed' });
      }
  
      const imagePath = scriptOutput.trim();
      res.json({ imagePath });
    });
  });
  

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});

