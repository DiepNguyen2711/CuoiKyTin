(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function formatNotificationText(notification) {
    const raw = notification?.text || notification?.content || 'Ban co thong bao moi';
    const escaped = escapeHtml(raw);
    return escaped
      .replace(/(-\s*\d+(?:[.,]\d+)?\s*TC)/gi, '<span class="price-deduction">$1</span>')
      .replace(/(\+\s*\d+(?:[.,]\d+)?\s*VND\s*\(Pending\))/gi, '<span class="vnd-pending-gain">$1</span>');
  }

  function renderNotificationItems(items, listNode) {
    if (!listNode) return;

    if (!Array.isArray(items) || items.length === 0) {
      listNode.innerHTML = '<li class="px-4 py-4 text-sm text-gray-500 dark:text-gray-400">Chua co thong bao nao</li>';
      return;
    }

    listNode.innerHTML = items.map((n) => {
      const text = formatNotificationText(n);
      const createdAt = escapeHtml(n.created_at || '');
      const stateClass = n.is_read ? 'read' : 'unread';
      const isPurchase = n.notification_type === 'purchase';
      const purchaseClass = isPurchase ? 'notif-purchase-item border-l-4 border-orange-400' : '';
      const iconHtml = isPurchase
        ? '<span class="inline-flex items-center justify-center w-7 h-7 rounded-full bg-orange-500/20 text-orange-600 dark:text-orange-300 shrink-0">💳</span>'
        : '';
      const href = n.video_id ? `video-detail.html?id=${encodeURIComponent(n.video_id)}` : '#';
      const thumbnail = n.video_thumbnail || 'https://placehold.co/120x68/e5e7eb/64748b?text=Video';
      const title = n.video_title ? `Thumbnail ${n.video_title}` : 'Thumbnail video';

      const contentHtml = `
        <div class="flex items-start gap-3">
          ${iconHtml}
          <img src="${escapeHtml(thumbnail)}" alt="${escapeHtml(title)}" class="w-16 h-10 rounded object-cover border border-gray-200 dark:border-gray-600 shrink-0" loading="lazy" />
          <div class="min-w-0">
            <p class="text-sm text-gray-800 dark:text-gray-100 leading-5 break-words">${text}</p>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">${createdAt}</p>
          </div>
        </div>
      `;

      if (n.video_id) {
        return `
          <li class="notif-item ${stateClass} ${purchaseClass}">
            <a href="${escapeHtml(href)}" class="block px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-700 transition">
              ${contentHtml}
            </a>
          </li>
        `;
      }

      return `<li class="notif-item ${stateClass} px-4 py-3 ${purchaseClass}">${contentHtml}</li>`;
    }).join('');
  }

  function markAllRenderedAsReadUI(listNode, badgeNode) {
    if (badgeNode) {
      badgeNode.textContent = '';
      badgeNode.classList.add('hidden');
    }

    if (!listNode) return;
    const unreadItems = listNode.querySelectorAll('.notif-item.unread');
    unreadItems.forEach((item) => {
      item.classList.remove('unread');
      item.classList.add('read');
    });
  }

  function setUnreadBadge(count, badgeNode) {
    if (!badgeNode) return;
    const unread = Math.max(0, Number(count || 0));
    if (unread > 0) {
      badgeNode.textContent = unread > 99 ? '99+' : String(unread);
      badgeNode.classList.remove('hidden');
    } else {
      badgeNode.classList.add('hidden');
    }
  }

  window.initHeaderNotifications = function initHeaderNotifications(options) {
    const apiBase = options?.apiBase || 'http://127.0.0.1:8000';
    const token = options?.token || localStorage.getItem('token');
    const pollMs = Number(options?.pollMs || 30000);

    const button = document.getElementById('notificationBtn');
    const dropdown = document.getElementById('notificationDropdown');
    const list = document.getElementById('notificationList');
    const badge = document.getElementById('notificationBadge');

    if (!token || !button || !dropdown || !list || !badge) return;

    badge.classList.add('notif-badge');

    async function fetchNotifications() {
      try {
        const res = await fetch(`${apiBase}/api/notifications/`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        if (!res.ok) return;

        renderNotificationItems(data.notifications || [], list);
        setUnreadBadge(data.unread_count || 0, badge);
      } catch (err) {
        console.error('Failed to fetch notifications', err);
      }
    }

    async function markNotificationsAsRead() {
      try {
        await fetch(`${apiBase}/api/notifications/mark-read/`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch (err) {
        console.error('Failed to mark notifications as read', err);
      }
    }

    button.addEventListener('click', async (event) => {
      event.stopPropagation();
      const isHidden = dropdown.classList.contains('hidden');
      if (isHidden) {
        await fetchNotifications();
        dropdown.classList.remove('hidden');
      } else {
        dropdown.classList.add('hidden');
      }

      // Reflect read state immediately in the UI.
      markAllRenderedAsReadUI(list, badge);
      // Persist read state server-side so refresh keeps notifications as read.
      markNotificationsAsRead();
    });

    document.addEventListener('click', (event) => {
      if (!dropdown.contains(event.target) && !button.contains(event.target)) {
        dropdown.classList.add('hidden');
      }
    });

    fetchNotifications();
    setInterval(fetchNotifications, pollMs);
  };
})();
