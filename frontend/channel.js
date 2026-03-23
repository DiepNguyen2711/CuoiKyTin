const params = new URLSearchParams(window.location.search);
const creatorId = params.get("id");

if (!creatorId) {
  alert("Thiếu id trên URL");
  throw new Error("Missing id");
}

const token = localStorage.getItem("token");

const headers = {
  "Authorization": "Bearer " + token
};

const usernameEl = document.getElementById("username");
const followersEl = document.getElementById("followers");
const followBtn = document.getElementById("followBtn");
const courseList = document.getElementById("courseList");
const avatar = document.getElementById("avatar");

/* =========================
   LOAD CHANNEL INFO
========================= */
fetch(`http://localhost:8000/api/channel/?id=${creatorId}`, { headers })
  .then(res => res.json())
  .then(data => {
    if (data.status !== "success") {
      alert(data.message || "Lỗi tải kênh");
      return;
    }

    const owner = data.owner;

    usernameEl.innerText = owner.username;
    avatar.innerText = owner.username[0].toUpperCase();

    followersEl.innerText = data.followers_count;

    // trạng thái follow
    if (data.is_following) {
      followBtn.innerText = "Đã theo dõi";
      followBtn.classList.add("followed");
    }

    // render khóa học
    if (data.courses.length === 0) {
      courseList.innerHTML = "<p>Chưa có khóa học nào.</p>";
    } else {
      data.courses.forEach(course => {
  const div = document.createElement("div");
  div.className = "course";

  div.innerHTML = `
    <strong>${course.title}</strong><br/>
    Giá: ${course.bundle_price_tc} TC
  `;

  // 👉 CLICK → CHUYỂN TRANG
  div.onclick = () => {
    window.location.href =
      `video-detail.html?course_id=${course.id}`;
  };

  courseList.appendChild(div);
});
    }
  });

/* =========================
   FOLLOW / UNFOLLOW
========================= */
followBtn.onclick = () => {
  fetch(`http://localhost:8000/api/follow/${creatorId}/`, {
    method: "POST",
    headers
  })
    .then(res => res.json())
    .then(data => {
      if (data.status !== "success") {
        alert(data.message);
        return;
      }

      followersEl.innerText = data.followers_count;

      if (data.is_following) {
        followBtn.innerText = "Đã theo dõi";
        followBtn.classList.add("followed");
      } else {
        followBtn.innerText = "Theo dõi";
        followBtn.classList.remove("followed");
      }
    });
};