(function initHourskillHeader(global) {
    function buildHeaderHtml(pageTitle) {
        return `
<header class="app-header bg-[#1a2236] dark:bg-gray-950 text-white sticky top-0 z-50 shadow-md transition-colors duration-300">
    <div class="app-header-inner">
        <div class="header-left shrink-0">
            <span class="text-2xl">📚</span>
            <a href="main.html" class="text-xl font-bold text-blue-400 hover:text-blue-300 transition">HOURSKILLS</a>
            <h1 class="header-page-title">${pageTitle}</h1>
        </div>

        <div class="header-right w-auto shrink-0" id="userMenu">
            <div class="header-search" role="search" aria-label="Tìm kiếm nhanh toàn trang">
                <input id="headerGlobalSearchInput" class="header-search-input" type="text" placeholder="Tìm kiếm..." autocomplete="off">
                <button id="headerGlobalSearchBtn" class="header-search-btn" type="button" aria-label="Tìm kiếm">🔍</button>
            </div>

            <button id="notificationBtn" class="p-2 h-10 w-10 rounded-full hover:bg-gray-700 transition relative flex items-center justify-center">
                <span id="notificationBadge" class="notif-badge hidden absolute -top-1 -right-1 min-w-[20px] h-5 px-1 text-white text-xs rounded-full flex items-center justify-center font-bold">0</span>
                🔔
            </button>

            <div id="notificationDropdown" class="hidden absolute right-0 top-12 w-96 max-h-[420px] overflow-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl z-50">
                <div class="px-4 py-3 border-b border-gray-100 dark:border-gray-700 font-semibold text-gray-800 dark:text-gray-100">Thông báo</div>
                <ul id="notificationList" class="divide-y divide-gray-100 dark:divide-gray-700"></ul>
            </div>

            <div class="tc-balance" title="Số dư TC">
                <span class="tc-icon">🪙</span>
                <span id="headerWalletBalance"><span id="user-wallet-balance">5</span> TC</span>
            </div>

            <span id="headerVipCrown" class="vip-crown" title="Tài khoản VIP">👑</span>
            <div class="header-user" id="userInfo">
                <span class="text-sm font-medium text-gray-200" id="headerUserGreeting">Chào, test U</span>
                <img id="headerAvatar" src="https://placehold.co/80x80/e2e8f0/64748b?text=U" class="w-8 h-8 rounded-full object-cover border-2 border-blue-400 shrink-0" alt="Avatar" />
            </div>
        </div>
    </div>
</header>
        `;
    }

    function mount(options) {
        const { targetId = 'appHeaderMount', pageTitle = 'TRANG CHỦ' } = options || {};
        const mountNode = document.getElementById(targetId);
        if (!mountNode) return;

        mountNode.innerHTML = buildHeaderHtml(pageTitle);

        const searchInput = document.getElementById('headerGlobalSearchInput');
        const searchBtn = document.getElementById('headerGlobalSearchBtn');

        const emitHeaderSearch = () => {
            const query = searchInput ? searchInput.value : '';
            global.dispatchEvent(new CustomEvent('hourskill:header-search', {
                detail: { query }
            }));
        };

        if (searchBtn) {
            searchBtn.addEventListener('click', emitHeaderSearch);
        }

        if (searchInput) {
            searchInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    emitHeaderSearch();
                }
            });
        }
    }

    global.HourskillHeader = {
        mount,
    };
})(window);
