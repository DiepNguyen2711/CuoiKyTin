const express = require("express");
const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const cors = require("cors");
const path = require("path");

const app = express();
const PORT = 3000;
const SECRET_KEY = "mysecretkey";

app.use(express.json());
app.use(cors());
app.use(express.static("public"));

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
    role: null,
    survey: null,
    avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(fullName)}&background=3b82f6&color=fff`
  };

  users.push(newUser);

  res.json({ message: "Đăng ký thành công!" });
});

// ================= LOGIN =================
app.post("/api/login", async (req, res) => {
  const { email, password } = req.body;

  const user = users.find((u) => u.email === email);
  if (!user) return res.status(400).json({ message: "Email không tồn tại" });

  const isMatch = await bcrypt.compare(password, user.password);
  if (!isMatch) return res.status(400).json({ message: "Sai mật khẩu" });

  const token = jwt.sign(
  { 
    id: user.id,
    fullName: user.fullName,
    avatar: user.avatar
  }, 
  SECRET_KEY, 
  { expiresIn: "1h" }
);

  res.json({ token });
});

// ================= CHỌN ROLE =================
app.post("/api/select-role", (req, res) => {
  const { email, role } = req.body;

  const user = users.find((u) => u.email === email);
  if (!user) return res.status(400).json({ message: "Không tìm thấy user" });

  user.role = role;

  res.json({ message: "Cập nhật role thành công" });
});

// ================= LƯU KHẢO SÁT =================
app.post("/api/survey", (req, res) => {
  const { email, answers } = req.body;

  const user = users.find((u) => u.email === email);
  if (!user) return res.status(400).json({ message: "Không tìm thấy user" });

  user.survey = answers;

  res.json({ message: "Lưu khảo sát thành công" });
});

// ================= ROOT =================
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "header-footer.html"));
});

app.listen(PORT, () => console.log("Server chạy tại http://localhost:3000"));