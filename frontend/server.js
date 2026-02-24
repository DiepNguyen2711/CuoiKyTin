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
  };

  users.push(newUser);

  res.json({ message: "Đăng ký thành công!" });
  
  app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "hourskills.html"));
});
});