(function initHourskillSidebar(global) {
    function defaultLinks() {
        return [
            { href: '#home', label: 'Trang chủ', icon: '🏠' },
            { href: '#courses', label: 'Khóa học', icon: '📚' },
            { href: 'earn.html', label: 'Kiếm TC', icon: '💰' },
            { href: 'teachers.html', label: 'Giáo viên', icon: '👨‍🏫' },
        ];
    }

    function buildLinkHtml(link, activeHref) {
        const href = String(link?.href || '#');
        const label = String(link?.label || 'Mục');
        const icon = String(link?.icon || '•');
        const isActive = href === activeHref;

        const activeClasses = 'text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-700 font-bold shadow-sm border border-gray-100 dark:border-gray-600';
        const inactiveClasses = 'text-gray-700 dark:text-gray-300 hover:bg-white dark:hover:bg-gray-700 hover:text-blue-600 dark:hover:text-blue-400';

        return `
            <a href="${href}" data-sidebar-link="${href}" class="px-4 py-3 rounded transition-colors ${isActive ? activeClasses : inactiveClasses}">
                ${icon} ${label}
            </a>
        `;
    }

    function buildSidebarHtml(options) {
        const {
            sectionTitle = 'Danh mục',
            links = defaultLinks(),
            activeHref = '#home',
        } = options || {};

        return `
<aside class="w-64 h-[calc(100vh-var(--app-header-height,70px))] bg-[#f1f5f9] dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 p-6 fixed left-0 top-[var(--app-header-height,70px)] overflow-y-auto z-40 transition-colors duration-300">
    <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-4">${sectionTitle}</h2>
    <nav class="flex flex-col gap-2">
        ${links.map((link) => buildLinkHtml(link, activeHref)).join('')}
    </nav>
</aside>
        `;
    }

    function mount(options) {
        const { targetId = 'sidebar-placeholder' } = options || {};
        const mountNode = document.getElementById(targetId);
        if (!mountNode) return;

        mountNode.innerHTML = buildSidebarHtml(options || {});
    }

    global.HourskillSidebar = {
        mount,
    };
})(window);
