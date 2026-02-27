const express = require('express');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

// Enable CORS for local API calls (Django backend) from the static frontend
app.use(cors());

// Serve all static assets (HTML, CSS, JS, images) from this directory
app.use(express.static(__dirname, {
  extensions: ['html'],
  setHeaders: (res, filePath) => {
    // Cache busting can be tuned here; keep short for HTML
    if (path.extname(filePath) === '.html') {
      res.setHeader('Cache-Control', 'no-store');
    }
  }
}));

// Fallback: any unknown path serves the main landing page
app.get('*', (_req, res) => {
  res.sendFile(path.join(__dirname, 'main.html'));
});

app.listen(PORT, () => {
  console.log(`Static frontend server running at http://localhost:${PORT}`);
});
