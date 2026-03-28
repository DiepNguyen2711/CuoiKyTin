(function initHourskillUserState(global) {
    const USER_EVENT = 'hourskill:user-updated';
    const USER_CACHE_KEY = 'hourskill_current_user';

    function normalizeNumber(value) {
        const n = Number(value);
        if (!Number.isFinite(n)) return 0;
        return Math.max(0, Math.floor(n));
    }

    function fallbackUser() {
        return {
            id: null,
            username: 'Guest',
            email: '',
            tc_balance: 0,
            avatar_url: '',
            is_vip: false,
            vip_expiry: null,
            vip_expiry_display: '',
            dark_mode: false,
            notify_comments: true,
            notify_follows: true,
        };
    }

    function readCachedUser() {
        const fallback = fallbackUser();
        try {
            const raw = localStorage.getItem(USER_CACHE_KEY);
            if (!raw) {
                const legacyUsername = localStorage.getItem('username') || fallback.username;
                const legacyBalance = normalizeNumber(localStorage.getItem('wallet_balance'));
                return { ...fallback, username: legacyUsername, tc_balance: legacyBalance };
            }
            const parsed = JSON.parse(raw);
            return {
                ...fallback,
                ...parsed,
                username: parsed?.username || fallback.username,
                tc_balance: normalizeNumber(parsed?.tc_balance),
                is_vip: Boolean(parsed?.is_vip),
            };
        } catch (error) {
            return fallback;
        }
    }

    function writeUserCache(nextUser) {
        const merged = {
            ...fallbackUser(),
            ...readCachedUser(),
            ...nextUser,
        };
        merged.username = merged.username || 'Guest';
        merged.tc_balance = normalizeNumber(merged.tc_balance);
        merged.is_vip = Boolean(merged.is_vip);

        localStorage.setItem(USER_CACHE_KEY, JSON.stringify(merged));
        localStorage.setItem('username', merged.username);
        localStorage.setItem('wallet_balance', String(merged.tc_balance));
        localStorage.setItem('is_vip', merged.is_vip ? '1' : '0');
        if (merged.email != null) {
            localStorage.setItem('email', merged.email || '');
        }
        if (merged.avatar_url) {
            localStorage.setItem('avatar_url', merged.avatar_url);
        }

        global.dispatchEvent(new CustomEvent(USER_EVENT, { detail: merged }));
        return merged;
    }

    function parseJsonSafe(response) {
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            throw new Error('Unexpected non-JSON response');
        }
        return response.json();
    }

    async function fetchCurrentUser(options = {}) {
        const { apiBase = 'http://127.0.0.1:8000', token, timeoutMs = 5000 } = options;
        if (!token) {
            return writeUserCache(fallbackUser());
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        try {
            const response = await fetch(`${apiBase}/api/me/`, {
                headers: { Authorization: `Bearer ${token}` },
                signal: controller.signal,
            });
            const payload = await parseJsonSafe(response);
            if (!response.ok) {
                throw new Error(payload?.message || 'Failed to fetch user');
            }

            return writeUserCache({
                id: payload.id ?? null,
                username: payload.username || 'Guest',
                email: payload.email || '',
                tc_balance: normalizeNumber(payload.tc_balance ?? payload.balance_tc ?? 0),
                avatar_url: payload.avatar_url || '',
                is_vip: Boolean(payload.is_vip),
                vip_expiry: payload.vip_expiry || null,
                vip_expiry_display: payload.vip_expiry_display || '',
                dark_mode: Boolean(payload.dark_mode),
                notify_comments: Boolean(payload.notify_comments),
                notify_follows: Boolean(payload.notify_follows),
            });
        } catch (error) {
            return writeUserCache(fallbackUser());
        } finally {
            clearTimeout(timeoutId);
        }
    }

    function subscribe(handler) {
        const wrapped = (event) => {
            handler(event?.detail || readCachedUser());
        };
        global.addEventListener(USER_EVENT, wrapped);
        return () => global.removeEventListener(USER_EVENT, wrapped);
    }

    global.HourskillUserState = {
        getCachedUser: readCachedUser,
        setUser: writeUserCache,
        fetchCurrentUser,
        subscribe,
        eventName: USER_EVENT,
    };
})(window);
