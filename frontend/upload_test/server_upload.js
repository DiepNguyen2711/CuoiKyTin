const express = require('express');
const multer = require('multer');
const cors = require('cors');

const app = express();
app.use(cors());

// Cho phép truy cập video
app.use('/media', express.static('../uploads'));

const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, '../uploads/videos');
  },
  filename: function (req, file, cb) {
    cb(null, Date.now() + '-' + file.originalname);
  }
});

const upload = multer({ storage });

// API upload video
app.post('/api/upload', upload.single('video'), (req, res) => {
  res.json({
    success: true,
    videoUrl: `/media/videos/${req.file.filename}`
  });
});

app.listen(4000, () => {
  console.log('Upload server chạy tại http://localhost:4000');
});