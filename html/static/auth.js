window.api_base_url = `${document.location.hostname}:8390`

window.getToken = function () {
    return JSON.parse(localStorage.getItem('token'));
};
window.setToken = function (item) {
    let { access_token, token_type, ts, user } = item;
    localStorage.setItem(
        'token',
        JSON.stringify({
            access_token,
            token_type,
            ts,
            user,
        })
    );
};

window.isAuth = window.getToken('token');
if (!isAuth && document.location.pathname !== '/auth' && document.location.pathname !== '/auth/') {
    document.location.href = document.location.origin + '/auth/';
}

if (isAuth) {
    const user = window.isAuth.user.name;
    const is_superuser = window.isAuth.user.is_superuser;

    if (
        // (!is_superuser && document.location.pathname === '/auth/') ||
        // (!is_superuser && document.location.pathname === '/auth/')
        (document.location.pathname === '/') ||
        (document.location.pathname === '') ||
        (document.location.pathname === '/auth/') ||
        (document.location.pathname === '/auth')
    ) {
        document.location.href = document.location.origin + '/accounts/';
    }
}

// Test token
checkAuth = function () {
    if (window.isAuth) {
        let { access_token, token_type, ts, user } = isAuth;
        $.ajax({
            type: 'POST',
            url: `http://${api_base_url}/api/v1/auth/test-token`,
            headers: {
                Authorization: `${token_type} ${access_token}`,
                accept: 'application/json',
            },
        })
            .done(function (data) {
                let { access_token, token_type } = isAuth;
                let { user, ts } = data;
                if (data.user.is_active !== user.is_active) {
                    window.setToken(null);
                }
                window.setToken({
                    access_token,
                    token_type,
                    ts,
                    user,
                });
                window.newDate = new Date(ts);
            })
            .fail(function (data) {
                if (localStorage.getItem('token')) localStorage.removeItem('token');
                if (!isAuth && document.location.pathname !== '/auth' && document.location.pathname !== '/auth/') {
                    document.location.href = document.location.origin + '/auth/';
                }
            });
    } else {
        if (localStorage.getItem('token')) localStorage.removeItem('token');
        if (!isAuth && document.location.pathname !== '/auth' && document.location.pathname !== '/auth/') {
            document.location.href = document.location.origin + '/auth/';
        }
    }
    // $('#notification')
    //    .getKendoNotification()
    //    .show(`Session expired.`);
    setTimeout(() => checkAuth(), 60000)

}

checkAuth(isAuth)
/*
setInterval(() => {
    if (isAuth) {
        let { access_token, token_type, ts, user } = isAuth;
        $.ajax({
            type: 'POST',
            url: '/api/v1/auth/test-token',
            headers: {
                Authorization: `${token_type} ${access_token}`,
                accept: 'application/json',
            },
        })
            .done(function (data) {
                let { access_token, token_type } = isAuth;
                let { user, ts } = data;
                if (data.user.is_active !== user.is_active) {
                    window.setToken(null);
                }
                window.setToken({
                    access_token,
                    token_type,
                    ts,
                    user,
                });
                window.newDate = new Date(ts);
            })
            .fail(function (data) {
                if (localStorage.getItem('token')) localStorage.removeItem('token');
                if (document.location.pathname !== '/auth') {
                    document.location.href = document.location.origin + '/auth';
                }
                $('#notification')
                    .getKendoNotification()
                    .show(`Session expired.`);
            });
    }
}, 60000);
*/