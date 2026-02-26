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
    avatar: user.avatar,
    role: user.role,
    surveyDone: !!user.survey,
    score: user.score || 0
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

  // 🔥 AI SCORING LOGIC (simple heuristic)
  let score = 0;

  answers.forEach(ans => {
    if (ans.includes("%")) score += 20;
    if (ans.toLowerCase().includes("quốc tế")) score += 30;
    if (ans.length > 20) score += 10;
  });

  user.score = score;

  res.json({ message: "Lưu khảo sát thành công", score });
});

// ================= ROOT =================
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "header-footer.html"));
});

app.listen(PORT, () => console.log("Server chạy tại http://localhost:3000"));
  const token = localStorage.getItem("token");
  const videoId =
    new URLSearchParams(window.location.search)
    .get("id");

  /* ================= LOAD VIDEO ================= */

  async function loadVideo(){

  const res = await fetch(`/api/video/${videoId}`,{
    headers:{
      Authorization:"Bearer "+token
    }
  });

  const data = await res.json();

  document.getElementById("videoTitle")
    .innerText = data.title;

  document.getElementById("creatorName")
    .innerText = data.creator.name;

  document.getElementById("creatorAvatar")
    .src = data.creator.avatar;

  // ✅ LOCK CHECK
  if(data.locked){

    document.getElementById("unlockPopup")
      .classList.remove("hidden");

    document.getElementById("unlockText")
      .innerText =
      `Bạn cần ${data.requiredTC} TC để mở khóa`;

  }else{

    document.getElementById("videoPlayer")
      .src = data.videoUrl;
  }

  setupFollow(data.creator.id, data.following);

  }

  loadVideo();

  async function setupFollow(creatorId, following){

  const btn = document.getElementById("followBtn");

  updateBtn();

  btn.onclick = async ()=>{

    await fetch(`/api/follow/${creatorId}`,{
      method:"POST",
      headers:{
        Authorization:"Bearer "+token
      }
    });

    following = !following;
    updateBtn();
  };

  function updateBtn(){
    btn.innerText =
      following ? "Following" : "Follow";

    btn.className =
      following
      ? "px-5 py-2 bg-gray-300 rounded-full"
      : "px-5 py-2 bg-blue-500 text-white rounded-full";
  }

  }
  document
  .getElementById("notifyBtn")
  .onclick = async ()=>{

  await fetch(`/api/creator/notify-toggle`,{
    method:"POST",
    headers:{
      Authorization:"Bearer "+token
    }
  });

  alert("Đã bật thông báo Creator 🔔");
  };
  async function unlockVideo(){

  const res = await fetch(
    `/api/video/${videoId}/unlock`,
    {
      method:"POST",
      headers:{
        Authorization:"Bearer "+token
      }
    }
  );

  const data = await res.json();

  if(res.ok){

    document
      .getElementById("unlockPopup")
      .classList.add("hidden");

    document
      .getElementById("videoPlayer")
      .src = data.videoUrl;

  }else{
    alert(data.message);
  }

  };