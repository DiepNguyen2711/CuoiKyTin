const API_BASE = "http://127.0.0.1:8000";
const params = new URLSearchParams(window.location.search);
const token = localStorage.getItem("token");

function resolveCreatorId() {
  const fromQuery = params.get("id");
  if (fromQuery) return fromQuery;

  const fromLocal = localStorage.getItem("user_id");
  if (fromLocal) return fromLocal;

  const fromSession = sessionStorage.getItem("user_id");
  if (fromSession) return fromSession;

  return "";
}

const creatorId = resolveCreatorId();

if (!creatorId) {
  if (token) {
    window.location.href = "main.html";
  } else {
    window.location.href = "login.html";
  }
  throw new Error("Missing creator id and no fallback available");
}

const headers = {
  "Authorization": "Bearer " + token
};

const usernameEl = document.getElementById("username");
const followersEl = document.getElementById("followers");
const followBtn = document.getElementById("followBtn");
const courseList = document.getElementById("courseList");
const avatar = document.getElementById("avatar");
const myCoursesLink = document.getElementById("myCoursesLink");

const currentUserId = localStorage.getItem("user_id") || sessionStorage.getItem("user_id") || "";
if (myCoursesLink) {
  myCoursesLink.href = currentUserId
    ? `channel.html?id=${encodeURIComponent(currentUserId)}`
    : "create_course.html";
}

/* =========================
   LOAD CHANNEL INFO
========================= */
fetch(`${API_BASE}/api/channel/?id=${creatorId}`, { headers })
  .then(res => res.json())
  .then(data => {
    if (data.status !== "success") {
      alert(data.message || "Lỗi tải kênh");
      if (token) {
        window.location.href = "main.html";
      } else {
        window.location.href = "login.html";
      }
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
    if (!Array.isArray(data.courses) || data.courses.length === 0) {
      courseList.innerHTML = "<p>Chưa có khóa học nào.</p>";
    } else {
      data.courses.forEach(course => {
        const cardLink = document.createElement("a");
        cardLink.className = "course";
        cardLink.href = `course-detail.html?id=${encodeURIComponent(course.id)}`;

        cardLink.innerHTML = `
          <p class="course-title">${course.title}</p>
          <p class="course-meta">Giá: theo từng video</p>
        `;

        courseList.appendChild(cardLink);
      });
    }
  })
  .catch(() => {
    if (token) {
      window.location.href = "main.html";
    } else {
      window.location.href = "login.html";
    }
  });

/* =========================
   FOLLOW / UNFOLLOW
========================= */
followBtn.onclick = () => {
  fetch(`${API_BASE}/api/follow/${creatorId}/`, {
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