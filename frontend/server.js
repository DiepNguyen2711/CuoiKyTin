const express = require('express');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

// Enable CORS for local API calls (Django backend) from the static frontend
app.use(cors());

<<<<<<< Updated upstream
let users = []; // fake database

// ================= REGISTER =================
app.post("/api/register", async (req, res) => {
  const { fullName, email, password, confirmPassword } = req.body;

  if (!fullName || !email || !password || !confirmPassword) {
    return res.status(400).json({ message: "Vui lòng nhập đầy đủ thông tin" });
  }

  if (password.length < 8) {
    return res.status(400).json({ message: "Mật khẩu phải ít nhất 8 ký tự" });
  }

  if (password !== confirmPassword) {
    return res.status(400).json({ message: "Mật khẩu xác nhận không khớp" });
  }

  const existingUser = users.find((u) => u.email === email);
  if (existingUser) {
    return res.status(400).json({ message: "Email đã tồn tại" });
  }

  const hashedPassword = await bcrypt.hash(password, 10);

  const newUser = {
    id: users.length + 1,
    fullName,
    email,
    password: hashedPassword,
  };

  users.push(newUser);

  res.json({ message: "Đăng ký thành công!" });
  
  app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "hourskills.html"));
});
});
=======
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
app.use((req, res) => {
    res.sendFile(path.join(__dirname, 'main.html'));
});
app.listen(PORT, () => {
  console.log(`Static frontend server running at http://localhost:${PORT}`);
});
>>>>>>> Stashed changes
