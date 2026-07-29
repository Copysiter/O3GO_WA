window.initToolbar = function() {
    $('#logs-toolbar').kendoToolBar({
        items: [
            {
                template: "<div class='k-window-title ps-6'>Logs</div>",
            },
            {
                type: 'spacer',
            },
            {
                type: 'button',
                text: 'Refresh',
                click: function (e) {
                    $('#logs-grid').data('kendoGrid').dataSource.read();
                },
            },
            {
                type: 'button',
                text: 'Clear Filter',
                click: function (e) {
                    $('#logs-grid').data('kendoGrid').dataSource.filter({});
                },
            },
        ],
    });
}
