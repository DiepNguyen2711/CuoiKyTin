(function initHourskillSidebar(global) {
  var STYLE_ID = "hourskill-sidebar-style";

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;

    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = [
      ".hs-sidebar-wrap {",
      "  width: 16rem;",
      "  height: calc(100vh - 70px);",
      "  position: fixed;",
      "  top: 70px;",
      "  left: 0;",
      "  z-index: 40;",
      "  overflow-y: auto;",
      "  padding: 24px;",
      "  background: #f1f5f9;",
      "  border-right: 1px solid #e5e7eb;",
      "}",
      ".hs-sidebar-title {",
      "  margin: 0 0 16px 0;",
      "  font-size: 0.75rem;",
      "  font-weight: 600;",
      "  letter-spacing: 0.08em;",
      "  text-transform: uppercase;",
      "  color: #9ca3af;",
      "}",
      ".hs-sidebar-nav {",
      "  display: flex;",
      "  flex-direction: column;",
      "  gap: 8px;",
      "}",
      ".hs-sidebar-link {",
      "  display: flex;",
      "  align-items: center;",
      "  gap: 8px;",
      "  padding: 12px 14px;",
      "  border-radius: 10px;",
      "  color: #334155;",
      "  text-decoration: none;",
      "  font-weight: 600;",
      "  transition: background-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;",
      "}",
      ".hs-sidebar-link:hover {",
      "  background: #f3f4f6;",
      "  color: #1e293b;",
      "}",
      ".hs-sidebar-link.hs-active {",
      "  color: #2563eb;",
      "  background: #ffffff;",
      "  border: 1px solid #dbeafe;",
      "  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);",
      "}",
      ".hs-sidebar-link-icon {",
      "  width: 1.25rem;",
      "  text-align: center;",
      "}",
      "@media (prefers-color-scheme: dark) {",
      "  .dark .hs-sidebar-wrap {",
      "    background: #1f2937;",
      "    border-right-color: #374151;",
      "  }",
      "  .dark .hs-sidebar-title {",
      "    color: #9ca3af;",
      "  }",
      "  .dark .hs-sidebar-link {",
      "    color: #d1d5db;",
      "  }",
      "  .dark .hs-sidebar-link:hover {",
      "    background: #374151;",
      "    color: #f9fafb;",
      "  }",
      "  .dark .hs-sidebar-link.hs-active {",
      "    color: #60a5fa;",
      "    background: #374151;",
      "    border-color: #4b5563;",
      "  }",
      "}",
    ].join("\n");

    document.head.appendChild(style);
  }

  function getCurrentFileName() {
    var path = (global.location && global.location.pathname) || "";
    var name = path.split("/").pop() || "main.html";
    return name.toLowerCase();
  }

  function buildSidebarHtml() {
    var current = getCurrentFileName();

    var activeRouteMap = {
      "main.html": ["main.html", ""],
      "courses.html": ["courses.html", "course.html", "course-detail.html", "create_course.html"],
      "earn.html": ["earn.html"],
      "teachers.html": ["teachers.html"],
    };

    var links = [
      { href: "main.html", label: "Trang chủ", icon: "🏠" },
      { href: "courses.html", label: "Khóa học", icon: "📚" },
      { href: "earn.html", label: "Kiếm TC", icon: "🪙" },
      { href: "teachers.html", label: "Giáo viên", icon: "👨‍🏫" },
    ];

    var itemsHtml = links
      .map(function (item) {
        var hrefFile = String(item.href || "").toLowerCase();
        var aliases = activeRouteMap[hrefFile] || [hrefFile];
        var activeClass = aliases.indexOf(current) >= 0 ? " hs-active" : "";
        return (
          '<a class="hs-sidebar-link' + activeClass + '" data-sidebar-link href="' + item.href + '">' +
          '<span class="hs-sidebar-link-icon">' + item.icon + "</span>" +
          '<span>' + item.label + "</span>" +
          "</a>"
        );
      })
      .join("");

    return (
      '<aside class="hs-sidebar-wrap">' +
      '<h2 class="hs-sidebar-title">Danh mục</h2>' +
      '<nav class="hs-sidebar-nav">' +
      itemsHtml +
      "</nav>" +
      "</aside>"
    );
  }

  function loadSidebar() {
    var mount = document.getElementById("sidebar-container");
    if (!mount) return;

    ensureStyles();
    mount.innerHTML = buildSidebarHtml();
  }

  global.loadSidebar = loadSidebar;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadSidebar);
  } else {
    loadSidebar();
  }
})(window);
