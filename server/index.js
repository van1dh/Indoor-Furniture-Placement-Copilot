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

  const pythonProcess = spawn('python', [
    'placement_generation.py',
    bed,
    desk,
    tv,
    wardrobe,
    notes,
  ]);

  let scriptOutput = '';
  let scriptError = '';

  pythonProcess.stdout.on('data', (data) => {
    const imagePath = data.toString().trim(); // 获取 Python 返回的路径
    console.log('Image path from Python:', imagePath); // 调试打印路径
    res.json({ imagePath }); // 返回路径给前端
    scriptOutput += data.toString();
  });

  pythonProcess.stderr.on('data', (data) => {
    scriptError += data.toString();
  });

  pythonProcess.on('close', (code) => {
    if (code !== 0 || scriptError) {
      console.error('Python script error:', scriptError);
      return res.status(500).json({ error: 'Python script execution failed' });
    }   

    const imagePath = scriptOutput.trim();
    console.log('Image generated at:', imagePath);
    res.json({ imagePath });
  });
});

  

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});

