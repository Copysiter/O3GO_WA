$(document).ready(function () {
    let isAuth = JSON.parse(localStorage.getItem('token'));
    console.log()
    console.log(document.location)
    console.log(document.location.href)
    console.log(document.location.path)
    console.log()
    if (isAuth) {
        document.location.href = document.location.origin + '/accounts/';
    }
    $('#authorization')
        .kendoWindow({
            modal: false,
            width: 420,
            height: 322,
            opacity: '0.1',
            visible: true,
            animation: false,
            draggable: false,
            resizable: false,
            actions: [],
            open: function (e) {},
            close: function () {},
        })
        .data('kendoWindow');
    let authWindow = $('#authorization').data('kendoWindow');
    authWindow.center();
    authWindow.title({
        encoded: false,
        text: '<div class="w-100 d-flex justify-content-between align-items-center"><div id="logo"><img src="../static/images/logo.svg" height=16 /></div><div class="logo-title d-none">SMS Hub</div><div>Version 1.0</div></div>',
    });

    $(window).resize(function () {
        authWindow.center();
    });

    $('#notification').kendoNotification({
        height: 50,
        width: 150,
        autoHideAfter: 5000,
    });

    $('#auth-form').kendoForm({
        orientation: 'vartical',
        width: 420,
        layout: 'grid',
        grid: {
            cols: 4,
            gutter: 10,
        },
        formData: {
            a: 'login',
            remember: 'Y',
        },
        items: [
            {
                field: 'a',
                editor: 'hidden',
            },
            {
                field: 'remember',
                editor: 'hidden',
            },
            {
                field: 'login',
                label: false,
                editor: 'TextBox',
                editorOptions: {
                    //placeholder: "Login",
                    label: {
                        content: 'Login',
                        floating: true,
                    },
                },
                colSpan: 4,
                validation: { required: true },
            },
            {
                field: 'password',
                label: false,
                colSpan: 4,
                editor: 'TextBox',
                attributes: { type: 'password' },
                editorOptions: {
                    //placeholder: "Password",
                    label: {
                        content: 'Password',
                        floating: true,
                    },
                },
                validation: { required: true },
            },
        ],
        labelPosition: 'before',
        buttonsTemplate:
            "<button id='form-save' type='submit' class='k-button k-button-lg k-rounded-md k-button-solid k-button-solid-base'>Log in</button>",
        change: function (e) {},
        validateField: function (e) {},
        submit: function (e) {
            e.preventDefault();
            console.log(e);
            $.ajax({
                type: 'POST',
                url: `${api_base_url}/api/v1/auth/access-token`,
                data: {
                    username: e.model.login,
                    password: e.model.password,
                },
            })
                .done(function (data) {
                    console.log(data);
                    window.setToken(data);
                    document.location.href = document.location.origin + '/accounts/';
                })
                .fail(function (data) {
                    console.log(2, data);
                    $('#notification')
                        .getKendoNotification()
                        .show(`${data.responseJSON.detail}`);
                });
        },
        // clear: function (e) {
        //     e.preventDefault();
        //     $("#users-window").data("kendoWindow").close();
        // },
    });
});
