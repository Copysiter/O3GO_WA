window.initToolbar = function() {
    $('#sessions-toolbar').kendoToolBar({
        items: [
            {
                template: "<div class='k-window-title ps-6'>Accounts Sessions</div>",
            },
            {
                type: 'spacer',
            },
            {
                type: 'button',
                text: 'Refresh',
                click: function (e) {
                    $('#sessions-grid').data('kendoGrid').dataSource.read();
                },
            },
            {
                type: 'button',
                text: 'Clear Filter',
                click: function (e) {
                    $('#sessions-grid').data('kendoGrid').dataSource.filter({});
                },
            },
            // {
            //     type: 'button',
            //     text: 'Export to Excel',
            //     icon: 'excel',
            //     click: function (e) {
            //         const grid = $('#sessions-grid').data('kendoGrid');
            //         const filter = grid.dataSource.filter();
            //         const params = new URLSearchParams();
            //         if (filter != undefined) {
            //             filter.filters.forEach((filter, index) => {
            //                 for (const [key, value] of Object.entries(filter)) {
            //                     params.append(`filters[${index}][${key}]`, value);
            //                 }
            //             });
            //         }
            //         const exportURL = `http://${api_base_url}/api/v1/export/sessions?${params.toString()}`;
            //         exportToExcel(exportURL)
            //     },
            // },
        ],
    });
}