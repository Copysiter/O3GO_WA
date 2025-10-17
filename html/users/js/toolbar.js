if (window.isAuth)
    $('#users-toolbar').kendoToolBar({
        items: [
            {
                template: "<div class='k-window-title ps-6'>Users</div>",
            },
            {
                type: 'spacer',
            },
            {
                type: 'button',
                text: 'Refresh',
                click: function (e) {
                    $('#users-grid').data('kendoGrid').dataSource.read();
                },
            },
            {
                type: 'button',
                text: 'Clear Filter',
                click: function (e) {
                    $('#users-grid').data('kendoGrid').dataSource.filter({});
                },
            },
            {
                type: 'button',
                text: 'New User',
                icon: 'plus',
                click: function (e) {
                    let grid = $('#users-grid').data('kendoGrid');
                    grid.addRow();
                },
            },
        ],
    });
