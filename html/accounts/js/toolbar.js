window.initToolbar = function() {
    $('#accounts-toolbar').kendoToolBar({
        items: [
            {
                template: "<div class='k-window-title ps-6'>WhatsApp Accounts</div>",
            },
            {
                type: 'spacer',
            },
            {
                type: 'button',
                id: 'delete',
                text: 'Delete',
                icon: 'cancel',
                hidden: true,
                attributes: { 'class': 'k-button-solid-error' },
                click: function (e) {
                    // $('#proxies-grid').data('kendoGrid').dataSource.read();
                    let grid = $('#accounts-grid').data('kendoGrid');
                    let rows = grid.select();
                    let ids = []
                    for (let i = 0; i < rows.length; i++) {
                        let dataItem = grid.dataItem($(rows[i]));
                        ids.push(dataItem.id);
                    }
                    kendo.confirm("<div style='padding:5px 10px 0 10px;'>Are you sure you want to delete accounts?</div>").done(function() {
                        $.ajax({
                            url: `${api_base_url}/api/v1/accounts/delete`,
                            type: "POST",
                            data: JSON.stringify({ ids: ids }),
                            processData: false,
                            ContentType: 'application/json',
                            headers: {
                                'Content-Type': 'application/json; odata=verbose',
                                'Authorization': `${token_type} ${access_token}`
                            },
                            success: function(data) {

                            },
                            error: function(jqXHR, textStatus, ex) {

                            }
                        }).then(function(data) {
                            if (!data.error) {
                                /*
                                $("#proxies-notification").kendoNotification({
                                    type: "warning",
                                    position: {
                                        top: 54,
                                        right: 8
                                    },
                                    width: "auto",
                                    allowHideAfter: 1000,
                                    autoHideAfter: 5000
                                });
                                */
                                grid.dataSource.read();
                                grid.clearSelection();
                                e.sender.hide($('#delete'));
                                //$("#ports-notification").getKendoNotification().show("Port has been " + (status == 1 ? "enabled" : "disabled"));
                            }
                        });
                    }).fail(function() {

                    });
                },
            },
            {
                type: 'button',
                text: 'Refresh',
                click: function (e) {
                    $('#accounts-grid').data('kendoGrid').dataSource.read();
                },
            },
            {
                type: 'button',
                text: 'Clear Filter',
                click: function (e) {
                    $('#accounts-grid').data('kendoGrid').dataSource.filter({});
                },
            },
            {
                type: 'button',
                text: 'New Account',
                icon: 'plus',
                click: function (e) {
                    // let grid = $('#accounts-grid').data('kendoGrid');
                    // grid.addRow();
                    // Если окно уже создано — просто открываем
                    $("#account-window").data("kendoWindow").center().open();
                },
            }
            // {
            //     type: 'button',
            //     text: 'Export to Excel',
            //     icon: 'excel',
            //     click: function (e) {
            //         const grid = $('#accounts-grid').data('kendoGrid');
            //         const filter = grid.dataSource.filter();
            //         const params = new URLSearchParams();
            //         if (filter != undefined) {
            //             filter.filters.forEach((filter, index) => {
            //                 for (const [key, value] of Object.entries(filter)) {
            //                     params.append(`filters[${index}][${key}]`, value);
            //                 }
            //             });
            //         }
            //         const exportURL = `${api_base_url}/api/v1/export/accounts?${params.toString()}`;
            //         exportToExcel(exportURL)
            //     },
            // },
        ],
    });
}