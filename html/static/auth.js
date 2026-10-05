(function (window, $) {
    'use strict';

    window.api_base_url = window.location.href.includes('o3go')
        ? 'https://apistat2.o3go.ru' : `http://${document.location.hostname}:8390`;

    let pollTimer;
    let revision = 0;

    function validUser(user) {
        return user && !Array.isArray(user) && Number.isInteger(user.id) && user.id > 0 && user.id <= 2147483647 &&
            typeof user.is_active === 'boolean' && typeof user.is_superuser === 'boolean';
    }

    function validTimestamp(value) {
        // Login and test-token also return legacy naive timestamps.
        return typeof value === 'string' && Number.isFinite(Date.parse(value));
    }

    function validToken(token) {
        return token && !Array.isArray(token) && validUser(token.user) && token.user.is_active &&
            typeof token.access_token === 'string' && /^[A-Za-z0-9._~+\/-]+=*$/.test(token.access_token) &&
            token.access_token.trim() === token.access_token && typeof token.token_type === 'string' &&
            token.token_type.toLowerCase() === 'bearer' && validTimestamp(token.ts);
    }

    window.setToken = function (item) {
        if (item === null) {
            revision += 1;
            window.isAuth = null;
            try { localStorage.removeItem('token'); }
            catch (error) {
                console.warn('Auth: не удалось удалить данные входа из хранилища.');
                return false;
            }
            return true;
        }
        if (!validToken(item)) {
            console.warn('Auth: некорректные данные входа не сохранены.');
            return false;
        }
        const { access_token, token_type, ts, user } = item;
        const token = { access_token, token_type, ts, user };
        try { localStorage.setItem('token', JSON.stringify(token)); }
        catch (error) {
            console.warn('Auth: не удалось сохранить данные входа.');
            return false;
        }
        window.isAuth = token;
        return true;
    };

    window.getToken = function () {
        let raw;
        try { raw = localStorage.getItem('token'); }
        catch (error) {
            console.warn('Auth: не удалось прочитать данные входа.');
            return null;
        }
        if (raw === null) return null;
        try {
            const token = JSON.parse(raw);
            if (validToken(token)) return token;
        } catch (error) {
            console.warn('Auth: некорректный JSON данных входа.');
        }
        window.setToken(null);
        return null;
    };

    function loginPage() {
        return document.location.pathname === '/auth' || document.location.pathname === '/auth/';
    }

    function requireLogin() {
        window.setToken(null);
        if (!loginPage()) document.location.href = document.location.origin + '/auth/';
    }

    function credentials(token) {
        // Ignore profile timestamps: another tab's successful poll is not a new login.
        return token ? JSON.stringify([token.access_token, token.token_type, token.user.id,
            token.user.is_superuser, token.user.is_active]) : null;
    }

    window.checkAuth = function () {
        window.clearTimeout(pollTimer);
        pollTimer = window.setTimeout(window.checkAuth, 60000);
        const requestRevision = ++revision;
        const token = window.getToken();
        if (!token) { requireLogin(); return; }
        const fingerprint = credentials(token);
        function current() {
            return revision === requestRevision && credentials(window.getToken()) === fingerprint;
        }
        try {
            $.ajax({
                type: 'POST', url: `${window.api_base_url}/api/v1/auth/test-token`,
                dataType: 'json', timeout: 20000,
                headers: { Authorization: `${token.token_type} ${token.access_token}`, accept: 'application/json' }
            }).done(function (data) {
                if (!current()) return;
                if (!data || !validUser(data.user) || data.user.id !== token.user.id || !validTimestamp(data.ts)) {
                    console.warn('Auth: некорректный ответ проверки входа. Проверка будет повторена.');
                    return;
                }
                if (!data.user.is_active) { requireLogin(); return; }
                if (window.setToken({ access_token: token.access_token, token_type: token.token_type,
                    user: data.user, ts: data.ts })) window.newDate = new Date(data.ts);
            }).fail(function (xhr, textStatus) {
                if (!current() || textStatus === 'abort') return;
                if ([401, 403, 404].includes(xhr.status) ||
                    (xhr.status === 400 && xhr.responseJSON && xhr.responseJSON.detail === 'Inactive user')) {
                    requireLogin();
                } else {
                    console.warn('Auth: проверка входа временно недоступна. Проверка будет повторена.');
                }
            });
        } catch (error) {
            console.warn('Auth: не удалось запустить проверку входа. Проверка будет повторена.');
        }
    };

    window.isAuth = window.getToken();
    if (window.isAuth && (loginPage() || document.location.pathname === '/' || document.location.pathname === '')) {
        document.location.href = document.location.origin + '/accounts/';
    }
    window.checkAuth();
})(window, jQuery);
