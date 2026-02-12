window.initGrid = function() {
    let timer = null;
    let resizeColumn = false;
    let showLoader = true;
    // let { access_token, token_type } =
    //     window.storageToken.options.offlineStorage.getItem();
    let token = window.isAuth;
    try {
        let { access_token, token_type } = token;

        stripFunnyChars = function (value) {
            return (value+'').replace(/[\x09-\x10]/g, '') ? value : '';
        }

        const user_column = window.isAuth.user.is_superuser ? [{
            field: 'user_id',
            width: '100px',
            title: 'User',
            template: '#: user.name #',
            filterable: {
                operators: {
                    number: {
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
                        optionLabel: "-- Select User --"
                    });
                }
            }
        }] : [];

        $('#accounts-grid').kendoGrid({
            dataSource: {
                transport: {
                    read: {
                        url: `${api_base_url}/api/v1/accounts/`,
                        type: 'GET',
                        beforeSend: function (request) {
                            request.setRequestHeader('Authorization', `${token_type} ${access_token}`);
                        },
                        dataType: 'json',
                    },
                    create: {
                        url: `${api_base_url}/api/v1/accounts/`,
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
                            return `${api_base_url}/api/v1/accounts/${options.id}`;
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
                            return `${api_base_url}/api/v1/accounts/${options.id}`;
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
                        // if (data.hasOwnProperty('filter') && data.filter) {
                        //     data.filter = data.filter.filters;
                        //     window.kendoToFastapiQuery(data)
                        // }

                        // if (type === 'read') return data;
                        if (type === 'read') {
                            const params = window.kendoToFastapiQuery(data);
                            return Object.fromEntries(params);
                        }
                        return kendo.stringify(data);
                    },
                },
                // data: fakedata,
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
                            id: { type: 'number'},
                            account: {type: 'object'},
                            type: { type: 'number' },
                            msg_count: { type: 'number' },
                            status: { type: 'number' },
                            user_id: { type: 'number' },
                            info_1: {type: 'string'},
                            info_2: {type: 'string'},
                            info_3: {type: 'string'},
                            created_at: { type: 'date', editable: false },
                            updated_at: { type: 'date', editable: false },
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
                        form = showEditForm();
                        popup = e.sender;
                        popup.center();
                    },
                },
            },
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
                        form = showEditForm();
                        popup = e.sender;
                        popup.center();
                    },
                },
            },
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
                        contains: 'Contains',
                        eq: 'Equal to',
                        neq: 'Not equal to',
                        // startswith: 'Starts with',
                        // endswith: 'Ends with',
                        // isnotnullorempty: 'Has value',
                        // doesnotcontain: 'Does not contain',
                        // isnullorempty: 'Has no value',
                    },
                    number: {
                        eq: 'Equal to',
                        neq: 'Not equal to',
                        // gt: 'Greater than',
                        // gte: 'Greater than or equal to',
                        // lt: 'Less than',
                        // lte: 'Less than or equal to',
                    },
                },
            },
            pageable: {
                refresh: true,
                pageSizes: [100, 250, 500],
            },
            change: function (e) {},
            excel: {
                fileName: 'o3go_accounts.xlsx',
                allPages: true,
                filterable: true
            },
            excelExport: function(e){
                var sheet = e.workbook.sheets[0];
                for (var i = 0; i < sheet.rows.length; i++) {
                    for (var ci = 0; ci < sheet.rows[i].cells.length; ci++) {
                        sheet.rows[i].cells[ci].value = stripFunnyChars(sheet.rows[i].cells[ci].value)
                    }
                }
            },
            columns: [
                {
                    field: 'id',
                    title: 'ID',
                    // width: 33,
                    filterable: false,
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
                {
                    field: 'number',
                    title: 'Number',
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    },
                },
                {
                    field: 'type',
                    title: 'Type',
                    filterable: {
                        operators: {
                            number: {
                                eq: "Equal to",
                                neq: "Not equal to"
                            }
                        },
                        ui : function(element) {
                            element.kendoDropDownList({
                                animation: false,
                                dataSource: [
                                    {value: 1, text: "WhatsApp"},
                                    {value: 2, text: "WhatsApp Business"}
                                ],
                                dataTextField: "text",
                                dataValueField: "value",
                                valuePrimitive: true,
                                optionLabel: "-- Select Type --"
                            });
                        }
                    },
                    template: (obj) => {
                        if (obj.type == 2) return 'WhatsApp Business';
                        return 'WhatsApp'
                    }
                },
                {
                    field: 'geo',
                    title: 'Geo',
                    // width: 33,
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    },
                },
                {
                    field: "file_name",
                    title: "Archive File Name",
                    filterable: false,
                },
                {
                    field: "profile_file_name",
                    title: "Profile File Name",
                    filterable: false,
                },
                {
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
                    field: 'status',
                    width: '100px',
                    title: 'Status',
                    template: function(item) {
                        if (item.status == -1) {
                            return "<span class='badge badge-sm k-badge k-badge-solid k-badge-md k-badge-rounded k-badge-error'>BANNED</span>"
                        }
                        else if (item.status == 0) {
                            return "<span class='badge badge-sm k-badge k-badge-solid k-badge-md k-badge-rounded k-badge-primary'>AVAILABLE</span>"
                        }
                        else if (item.status == 1) {
                            return "<span class='badge badge-sm k-badge k-badge-solid k-badge-md k-badge-rounded k-badge-success'>ACTIVE</span>"
                        }
                        else if (item.status == 2) {
                            return "<span class='badge badge-sm k-badge k-badge-solid k-badge-md k-badge-rounded k-badge-warning'>PAUSED</span>"
                        }
                    },
                    sortable: false,
                    filterable: {
                        operators: {
                            number: {
                                eq: "Equal to",
                                neq: "Not equal to"
                            }
                        },
                        ui : function(element) {
                            element.kendoDropDownList({
                                animation: false,
                                dataSource: [
                                    {value: -1, text: "BANNED"},
                                    {value: 0, text: "AVAILABLE"},
                                    {value: 1, text: "ACTIVE"},
                                    {value: 2, text: "PAUSED"}
                                ],
                                dataTextField: "text",
                                dataValueField: "value",
                                valuePrimitive: true,
                                optionLabel: "-- Select Status --"
                            });
                        }
                    }
                },
                {
                    field: "attempts",
                    title: "Attempts",
                    filterable: false
                }].concat(user_column).concat([{
                    field: 'info_1',
                    title: 'Info 1',
                    // width: 33,
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    },
                },
                {
                    field: 'info_2',
                    title: 'Info 2',
                    // width: 33,
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    },
                },
                {
                    field: 'info_3',
                    title: 'Info 3',
                    // width: 33,
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    }
                },
                {
                    field: 'info_4',
                    title: 'Info 4',
                    // width: 33,
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    }
                },
                {
                    field: 'info_5',
                    title: 'Info 5',
                    // width: 33,
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    }
                },
                {
                    field: 'info_6',
                    title: 'Info 6',
                    // width: 33,
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    }
                },
                {
                    field: 'info_7',
                    title: 'Info 7',
                    // width: 33,
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    }
                },
                {
                    field: 'info_8',
                    title: 'Info 8',
                    // width: 33,
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    }
                },
                {
                    field: 'created_at',
                    title: 'Created',
                    filterable: false,
                    format: '{0: yyyy-MM-dd HH:mm:ss}',
                }, {
                    field: 'updated_at',
                    title: 'Updated',
                    filterable: false,
                    format: '{0: yyyy-MM-dd HH:mm:ss}',
                },
                {},
            ])
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
            }
        });
    } catch (error) {
        console.warn(error);
    }
    window.optimize_grid(['#accounts-grid']);
}
