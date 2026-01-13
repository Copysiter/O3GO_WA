window.initAccountGrid = function() {
    let timer = null;
    let showLoader = true;
    let token = window.isAuth;

    try {
        const user_column = window.isAuth.user.is_superuser ? [{
            field: 'user_id',
            width: '100px',
            title: 'User',
            template: '#: user.name #',
            filterable: {
                operators: {
                    string: {
                        eq: "Equal to",
                        neq: "Not equal to"
                    }
                },
                ui : function(element) {
                    element.kendoDropDownList({
                        animation: false,
                        dataSource: new kendo.data.DataSource({
                            transport: {
                                read: {
                                    url: `${api_base_url}/api/v1/options/user`,
                                    type: 'GET',
                                    beforeSend: function (request) {
                                        request.setRequestHeader(
                                            'Authorization',
                                            `${token_type} ${access_token}`
                                        );
                                    },
                                },
                            },
                        }),
                        dataTextField: "text",
                        dataValueField: "value",
                        valuePrimitive: true,
                        optionLabel: "-- Select Customer --"
                    });
                }
            }
        }] : [];

        let { access_token, token_type } = token;

        var popup;

        stripFunnyChars = function (value) {
            return (value+'').replace(/[\x09-\x10]/g, '') ? value : '';
        }

        $('#accounts-grid').kendoGrid({
            dataSource: {
                transport: {
                    read: {
                        url: `${api_base_url}/api/v1/android/accounts/`,
                        type: 'GET',
                        beforeSend: function (request) {
                            request.setRequestHeader('Authorization', `${token_type} ${access_token}`);
                        },
                        dataType: 'json',
                    },
                    create: {
                        url: `${api_base_url}/api/v1/android/accounts/`,
                        type: 'POST',
                        dataType: 'json',
                        contentType: 'application/json',
                        beforeSend: function (request) {
                            request.setRequestHeader('Authorization', `${token_type} ${access_token}`);
                        },
                    },
                    update: {
                        url: function (options) {
                            console.log(options);
                            return `${api_base_url}/api/v1/android/accounts/${options.id}`;
                        },

                        type: 'PUT',
                        dataType: 'json',
                        contentType: 'application/json',
                        beforeSend: function (request) {
                            request.setRequestHeader('Authorization', `${token_type} ${access_token}`);
                        },
                    },
                    destroy: {
                        url: function (options) {
                            console.log(options);
                            return `${api_base_url}/api/v1/android/accounts/${options.id}`;
                        },

                        type: 'DELETE',
                        dataType: 'json',
                        contentType: 'application/json',
                        beforeSend: function (request) {
                            request.setRequestHeader('Authorization', `${token_type} ${access_token}`);
                        },
                    },
                    // parameterMap: function (options, type) {
                    //     return kendo.stringify(options);
                    // },
                    parameterMap: function (data, type) {
                        if (data.hasOwnProperty('take')) {
                            data.limit = data.take;
                            delete data.take;
                        }
                        if (data.hasOwnProperty('page')) {
                            delete data.page;
                        }
                        if (data.hasOwnProperty('pageSize')) {
                            delete data.pageSize;
                        }
                        if (data.hasOwnProperty('filter') && data.filter) {
                            data.filter = data.filter.filters;
                        }

                        if (type === 'read') return data;
                        return kendo.stringify(data);
                    },
                },
                pageSize: 100,
                serverPaging: true, // true
                serverFiltering: true, // true
                serverSorting: true, // true
                schema: {
                    data: function (response) {
                        if (response.data !== undefined) return response.data;
                        else return response;
                    },
                    total: 'total',
                    model: {
                        id: 'id',
                        fields: {
                            user_id: { type: 'number' },
                            file_name: {
                                type: 'string',
                                editable: true
                            },
                            status: { type: 'number' },
                            limit: { type: 'number' },
                            cooldown: { type: 'number' },
                            actions: { type: 'object', editable: false },
                        },
                    },
                },
                requestStart: function (e) {
                    setTimeout(function (e) {
                        if (showLoader) $('.k-loading-mask').show();
                    });
                },
            },
            height: '100%',
            reorderable: true,
            resizable: true,
            selectable: 'multiple, row',
            persistSelection: true,
            sortable: true,
            edit: function (e) {
                form.data('kendoForm').setOptions({
                    formData: e.model,
                });
                popup.setOptions({
                    title: e.model.id ? 'Edit Account' : 'New Account',
                });
                popup.center();
            },
            editable: {
                mode: 'popup',
                template: kendo.template($('#accounts-popup-editor').html()),
                window: {
                    width: 480,
                    maxHeight: '90%',
                    animation: false,
                    appendTo: '#app-root',
                    visible: false,
                    open: function (e) {
                        form = showAccountEditForm();
                        popup = e.sender;
                        popup.center();
                    },
                },
            },
            // save: function(e) {
            //     // не даём гриду сохранять текущую "редактируемую" модель
            //     e.preventDefault();
            //
            //     const grid = e.sender;
            //     const ds = grid.dataSource;
            //
            //     console.log(grid.dataSource);
            //     return;
            //
            //     if (ds.hasChanges()) {
            //         // по желанию: закрыть попап после успешного sync
            //         ds.one("requestEnd", function() {
            //             if (grid.editable) grid.editable.close();
            //         });
            //
            //         // по желанию: обработка ошибок
            //         ds.one("error", function(ev) {
            //             console.warn("DataSource error", ev);
            //         });
            //
            //         ds.sync(); // отправит create/update/destroy, накопленные из Upload
            //     } else {
            //         // ничего не изменилось — просто закрыть окно
            //         if (grid.editable) grid.editable.close();
            //     }
            // },
            dataBinding: function (e) {
                clearTimeout(timer);
            },
            dataBound: function (e) {
                showLoader = true;
            },
            filterable: {
                mode: 'menu',
                extra: false,
                operators: {
                    string: {
                        eq: 'Equal to',
                        neq: 'Not equal to',
                        startswith: 'Starts with',
                        endswith: 'Ends with',
                        contains: 'Contains',
                        doesnotcontain: 'Does not contain',
                        isnullorempty: 'Has no value',
                        isnotnullorempty: 'Has value',
                    },
                    number: {
                        eq: 'Equal to',
                        neq: 'Not equal to',
                        gt: 'Greater than',
                        gte: 'Greater than or equal to',
                        lt: 'Less than',
                        lte: 'Less than or equal to',
                    },
                },
            },
            pageable: {
                refresh: true,
                pageSizes: [100, 250, 500],
            },
            change: function (e) {
                let toolbar = $('#accounts-toolbar').data('kendoToolBar');
                let rows = this.select();
                if (rows.length > 0) {
                    toolbar.show($('#delete'));
                } else {
                    toolbar.hide($('#delete'));
                }
            },
            columns: [
                {
                    field: 'id',
                    title: '#',
                    filterable: false
                },
                {
                    field: "file_name",
                    title: "File Name",
                    filterable: false,
                },
                {
                    field: "status",
                    title: "Status",
                    filterable: false,
                    template: function(item) {
                        if(item.status == -1) {
                            return "<span class='badge badge-sm k-badge k-badge-solid k-badge-md k-badge-rounded k-badge-error'>BANNED</span>"
                        }
                        else if(item.status == 0) {
                            return "<span class='badge badge-sm k-badge k-badge-solid k-badge-md k-badge-rounded k-badge-light'>AVAILABLE</span>"
                        }
                        else if(item.status == 1) {
                            return "<span class='badge badge-sm k-badge k-badge-solid k-badge-md k-badge-rounded k-badge-success'>ACTIVE</span>"
                        }
                        else if(item.status == 2) {
                            return "<span class='badge badge-sm k-badge k-badge-solid k-badge-md k-badge-rounded k-badge-dark'>PAUSED</span>"
                        }
                    },
                }].concat(user_column).concat([{
                    field: "limit",
                    title: "Limit",
                    filterable: false
                },
                {
                    field: "cooldown",
                    title: "Pause",
                    filterable: false
                },
                {
                    command: [
                        {
                            name: 'edit',
                            iconClass: {
                                edit: 'k-icon k-i-edit',
                                update: '',
                                cancel: '',
                            },
                            text: {
                                edit: '',
                                update: 'Save',
                                cancel: 'Cancel',
                            },
                        },
                        { name: 'destroy', text: '' },
                    ],
                    title: '',
                    // width: 86,
                },
                {}
            ]),
        });
        jQuery.fn.selectText = function () {
            var doc = document;
            var element = this[0];
            $('input, textarea, select').blur();
            if (doc.body.createTextRange) {
                var range = document.body.createTextRange();
                range.moveToElementText(element);
                range.select();
            } else if (window.getSelection) {
                var selection = window.getSelection();
                var range = document.createRange();
                range.selectNodeContents(element);
                selection.removeAllRanges();
                selection.addRange(range);
            }
        };

        $('#accounts-grid').on('dblclick', "td[role='gridcell']", function (e) {
            var text = $(this).find('.text');
            if (text.length) text.selectText();
            else $(this).selectText();
        });

        $(document).keydown(function (e) {
            if (e.key === 'Escape') {
                selectedDataItems = [];
                selectedItemIds = [];
                selectedItemImsi = [];
                $('#accounts-grid').data('kendoGrid').clearSelection();
                $('#accounts-toolbar').data('kendoToolBar').hide($('#delete'));
            }
        });
    } catch (error) {
        console.warn(error);
    }
    window.optimize_grid(['#accounts-grid']);
}
