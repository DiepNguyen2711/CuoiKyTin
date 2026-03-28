(function initHourskillLiveFilter(global) {
    function normalize(text) {
        return String(text || '').trim().toLowerCase();
    }

    function create(options) {
        const {
            inputEl,
            buttonEl,
            getItems,
            getText,
            onMatchChange,
            onAfterFilter,
            hideClass = 'is-filter-hidden',
        } = options || {};

        if (!inputEl || typeof getItems !== 'function' || typeof getText !== 'function') {
            return null;
        }

        const apply = (explicitQuery) => {
            const query = normalize(typeof explicitQuery === 'string' ? explicitQuery : inputEl.value);
            const items = getItems() || [];
            let visibleCount = 0;

            items.forEach((item) => {
                const haystack = normalize(getText(item));
                const matched = !query || haystack.includes(query);
                item.classList.toggle(hideClass, !matched);
                if (typeof onMatchChange === 'function') {
                    onMatchChange({ item, matched, query });
                }
                if (matched) {
                    visibleCount += 1;
                }
            });

            if (typeof onAfterFilter === 'function') {
                onAfterFilter({ query, total: items.length, visibleCount });
            }
            return { query, total: items.length, visibleCount };
        };

        inputEl.addEventListener('input', () => apply());
        inputEl.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                apply();
            }
        });

        if (buttonEl) {
            buttonEl.addEventListener('click', () => apply());
        }

        return { apply };
    }

    global.HourskillLiveFilter = { create };
})(window);
