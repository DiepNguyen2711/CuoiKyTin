(function initHourskillNavigation(global) {
    function inject(options) {
        const {
            headerTargetId = 'header-placeholder',
            sidebarTargetId = 'sidebar-placeholder',
            pageTitle = 'TRANG CHỦ',
            hideSidebar = false,
            sidebar = {},
        } = options || {};

        if (global.HourskillHeader?.mount) {
            global.HourskillHeader.mount({
                targetId: headerTargetId,
                pageTitle,
            });
        }

        if (!hideSidebar && global.HourskillSidebar?.mount) {
            global.HourskillSidebar.mount({
                targetId: sidebarTargetId,
                sectionTitle: sidebar.sectionTitle,
                activeHref: sidebar.activeHref,
                links: sidebar.links,
            });
        }
    }

    global.HourskillNavigation = {
        inject,
    };
})(window);
