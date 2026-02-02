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
            template: '#: account.user.name #',
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

        $('#sessions-grid').kendoGrid({
            dataSource: {
                transport: {
                    read: {
                        url: `${api_base_url}/api/v1/sessions/`,
                        type: 'GET',
                        beforeSend: function (request) {
                            request.setRequestHeader('Authorization', `${token_type} ${access_token}`);
                        },
                        dataType: 'json',
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
            dataBinding: function (e) {
                clearTimeout(timer);
            },
            dataBound: function (e) {
                showLoader = true;
                // if (!resizeColumn) {
                //     autoFitColumn(e.sender);
                //     resizeColumn = true;
                // }

                // timer = setTimeout(function () {
                //     showLoader = false;
                //     e.sender.dataSource.read();
                // }, 30000);
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
                fileName: 'o3go_sessions.xlsx',
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
                    field: 'ext_id',
                    title: 'Ext ID',
                    // width: 33,
                    filterable: true,
                },
                {
                    field: 'account',
                    title: 'Account',
                    filterable: false,
                    // filterable: {
                    //     cell: {
                    //         inputWidth: 0,
                    //         showOperators: true,
                    //         operator: 'eq',
                    //     },
                    // },
                    template: "#: account.number #"
                },
                {
                    field: 'msg_count',
                    title: 'Messages',
                    format: "{0:n0}",
                    filterable: {
                        ui: function (element) {
                          element.kendoNumericTextBox({
                            format: "n0",
                            decimals: 0,
                            step: 1
                          });
                        },
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq'
                        },
                    },
                },
                {
                    field: 'type',
                    title: 'Type',
                    filterable: false,
                    template: (obj) => {
                        if (obj.account.type == 2) return 'WhatsApp Business';
                        return 'WhatsApp'
                    }
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
                            return "<span class='badge badge-sm k-badge k-badge-solid k-badge-md k-badge-rounded k-badge-primary'>FINISHED</span>"
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
                        number: {
                            eq: "Equal to",
                            neq: "Not equal to"
                        },
                        ui : function(element) {
                            element.kendoDropDownList({
                                animation: false,
                                dataSource: [
                                    {value: -1, text: "BANNED"},
                                    {value: 0, text: "FINISHED"},
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

        $('#sessions-grid').on('dblclick', "td[role='gridcell']", function (e) {
            var text = $(this).find('.text');
            if (text.length) text.selectText();
            else $(this).selectText();
        });

        $(document).keydown(function (e) {
            if (e.key === 'Escape') {
                selectedDataItems = [];
                selectedItemIds = [];
                selectedItemImsi = [];
                $('#sessions-grid').data('kendoGrid').clearSelection();
            }
        });
    } catch (error) {
        console.warn(error);
    }
    window.optimize_grid(['#sessions-grid']);
}
