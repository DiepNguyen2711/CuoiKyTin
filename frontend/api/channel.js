const API_BASE = "http://127.0.0.1:8000";
const params = new URLSearchParams(window.location.search);
const token = localStorage.getItem("token");
const DEFAULT_AVATAR = "https://placehold.co/160x160/e2e8f0/64748b?text=U";
const DEFAULT_VIDEO_THUMB = "https://placehold.co/640x360/e2e8f0/64748b?text=Video";

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

const creatorNameEl = document.getElementById("creatorName");
const creatorAvatarEl = document.getElementById("creatorAvatar");
const creatorSpecializationEl = document.getElementById("creatorSpecialization");
const creatorBioEl = document.getElementById("creatorBio");
const followersEl = document.getElementById("followersCount");
const totalCoursesEl = document.getElementById("totalCourses");
const totalVideosEl = document.getElementById("totalVideos");
const followBtn = document.getElementById("followBtn");
const courseList = document.getElementById("courseList");
const courseEmpty = document.getElementById("courseEmpty");
const videoList = document.getElementById("videoList");
const videoEmpty = document.getElementById("videoEmpty");

const currentUserId = localStorage.getItem("user_id") || sessionStorage.getItem("user_id") || "";

function updateSidebarForOwnChannel() {
  const links = Array.from(document.querySelectorAll("#sidebar-container a[data-sidebar-link]"));
  if (!links.length) return;

  const firstLink = links[0];
  if (!firstLink) return;

  const labelNode = firstLink.querySelector("span:last-child");
  if (labelNode) {
    labelNode.textContent = "Kênh cá nhân";
  }

  firstLink.href = `channel.html?id=${encodeURIComponent(currentUserId)}`;
}

function setFollowButtonState(isFollowing) {
  if (!followBtn) return;

  if (isFollowing) {
    followBtn.innerText = "Da theo doi";
    followBtn.classList.remove("bg-blue-600", "hover:bg-blue-700");
    followBtn.classList.add("bg-gray-500", "hover:bg-gray-600");
    return;
  }

  followBtn.innerText = "Theo doi";
  followBtn.classList.remove("bg-gray-500", "hover:bg-gray-600");
  followBtn.classList.add("bg-blue-600", "hover:bg-blue-700");
}

function renderCourses(courses) {
  if (!courseList || !courseEmpty) return;

  courseList.innerHTML = "";
  const normalized = Array.isArray(courses) ? courses : [];

  if (normalized.length === 0) {
    courseEmpty.classList.remove("hidden");
    return;
  }

  courseEmpty.classList.add("hidden");
  normalized.forEach((course) => {
    const card = document.createElement("a");
    card.href = `course-detail.html?id=${encodeURIComponent(course.id)}`;
    card.className = "block bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 hover:border-blue-400 hover:shadow-md transition";
    card.innerHTML = `
      <p class="text-lg font-semibold text-gray-900 dark:text-white">${course.title || "Khong co ten"}</p>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">Gia: theo tung video</p>
    `;
    courseList.appendChild(card);
  });
}

function renderVideos(videos) {
  if (!videoList || !videoEmpty) return;

  videoList.innerHTML = "";
  const normalized = Array.isArray(videos) ? videos : [];

  if (normalized.length === 0) {
    videoEmpty.classList.remove("hidden");
    return;
  }

  videoEmpty.classList.add("hidden");
  normalized.forEach((video) => {
    const card = document.createElement("a");
    card.href = `video-detail.html?id=${encodeURIComponent(video.id)}`;
    card.className = "featured-video-card block bg-slate-900 rounded-xl overflow-hidden border border-slate-700 hover:shadow-lg transition";

    const thumb = video.thumbnail || DEFAULT_VIDEO_THUMB;
    const duration = Number(video.duration_seconds || 0);
    const minutes = Math.floor(duration / 60);
    const seconds = String(duration % 60).padStart(2, "0");

    card.innerHTML = `
      <div class="relative w-full aspect-video bg-black">
        <img src="${thumb}" alt="Thumbnail" class="w-full h-full object-cover" loading="lazy" onerror="this.onerror=null;this.src='${DEFAULT_VIDEO_THUMB}'" />
        <span class="absolute top-2 right-2 bg-black/80 text-white text-xs px-2 py-1 rounded">${minutes}:${seconds}</span>
      </div>
      <div class="p-4">
        <h4 class="featured-video-title font-semibold text-white line-clamp-2">${video.title || "Video khong tieu de"}</h4>
        <p class="featured-video-creator text-sm text-slate-300 mt-2">${ownerLabel(video)}</p>
      </div>
    `;

    videoList.appendChild(card);
  });
}

function ownerLabel(video) {
  const creator = typeof video?.creator === "string" ? video.creator.trim() : "";
  return creator || "Giang vien";
}

/* =========================
   LOAD CHANNEL INFO
========================= */
fetch(`${API_BASE}/api/channel/?id=${creatorId}`, { headers })
  .then(res => res.json())
  .then(data => {
    if (data.status !== "success") {
      if (token) {
        window.location.href = "main.html";
      } else {
        window.location.href = "login.html";
      }
      return;
    }

    const owner = data.owner;

    if (creatorNameEl) {
      creatorNameEl.innerText = owner.username || "Giang vien";
    }

    if (creatorSpecializationEl) {
      creatorSpecializationEl.innerText = owner.specialization || "Giang vien da linh vuc";
    }

    if (creatorBioEl) {
      creatorBioEl.innerText = owner.bio || "Chua cap nhat mo ta giang day.";
    }

    if (creatorAvatarEl) {
      creatorAvatarEl.src = owner.avatar_url || DEFAULT_AVATAR;
      creatorAvatarEl.alt = owner.username ? `Avatar ${owner.username}` : "Avatar giang vien";
    }

    followersEl.innerText = data.followers_count;
    setFollowButtonState(Boolean(data.is_following));

    if (String(currentUserId) === String(creatorId) && followBtn) {
      followBtn.classList.add("hidden");
      updateSidebarForOwnChannel();
    }

    const courses = Array.isArray(data.courses) ? data.courses : [];
    const videos = Array.isArray(data.videos) ? data.videos : [];

    if (totalCoursesEl) {
      totalCoursesEl.innerText = String(courses.length);
    }
    if (totalVideosEl) {
      totalVideosEl.innerText = String(videos.length);
    }

    renderCourses(courses);
    renderVideos(videos);
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
        return;
      }

      followersEl.innerText = data.followers_count;
      setFollowButtonState(Boolean(data.is_following));
    });
};