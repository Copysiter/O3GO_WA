window.initGrid = function() {
    let timer = null;
    let showLoader = true;
    let token = window.isAuth;
    try {
        let { access_token, token_type } = token;

        stripFunnyChars = function (value) {
            return (value+'').replace(/[\x09-\x10]/g, '') ? value : '';
        }

        function statusBadge(item) {
            if (!item.status) return '';
            const classes = {
                active: 'success',
                available: 'primary',
                banned: 'error',
                created: 'light',
                delivered: 'success',
                failed: 'error',
                finished: 'primary',
                paused: 'warning',
                sent: 'primary',
                undelivered: 'warning',
                waiting: 'light'
            };
            const status = String(item.status).toLowerCase();
            const cls = classes[status] || 'light';
            return `<span class='badge badge-sm k-badge k-badge-solid k-badge-md k-badge-rounded k-badge-${cls}'>${status.toUpperCase()}</span>`;
        }

        function contextTemplate(item) {
            if (!item.context || $.isEmptyObject(item.context)) return '';
            return `<span class='log-context'>${kendo.htmlEncode(JSON.stringify(item.context))}</span>`;
        }

        const user_column = window.isAuth.user.is_superuser ? [{
            field: 'user_id',
            width: '100px',
            title: 'User',
            template: function(item) {
                if (!item.user) return '';
                return item.user.name || item.user.login || '';
            },
            filterable: {
                operators: {
                    number: {
                        eq: 'Equal to',
                        neq: 'Not equal to'
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
                        dataTextField: 'text',
                        dataValueField: 'value',
                        valuePrimitive: true,
                        optionLabel: '-- Select User --'
                    });
                }
            }
        }] : [];

        $('#logs-grid').kendoGrid({
            dataSource: {
                transport: {
                    read: {
                        url: `${api_base_url}/api/v1/logs/`,
                        type: 'GET',
                        beforeSend: function (request) {
                            request.setRequestHeader('Authorization', `${token_type} ${access_token}`);
                        },
                        dataType: 'json',
                    },
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
                        if (type === 'read') {
                            const params = window.kendoToFastapiQuery(data);
                            const event = params.get('event');
                            if (['account.', 'session.', 'message.'].includes(event)) {
                                params.delete('event');
                                params.set('event__ilike', event);
                            }
                            return Object.fromEntries(params);
                        }
                        return kendo.stringify(data);
                    },
                },
                pageSize: 100,
                serverPaging: true,
                serverFiltering: true,
                serverSorting: true,
                schema: {
                    data: function (response) {
                        if (response.data !== undefined) return response.data;
                        else return response;
                    },
                    total: 'total',
                    model: {
                        id: 'id',
                        fields: {
                            id: { type: 'number' },
                            event: { type: 'string' },
                            source: { type: 'string' },
                            account_id: { type: 'number' },
                            session_id: { type: 'number' },
                            message_id: { type: 'number' },
                            user_id: { type: 'number' },
                            status: { type: 'string' },
                            context: { type: 'object' },
                            created_at: { type: 'date', editable: false },
                            account: { type: 'object' },
                            user: { type: 'object' },
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
            selectable: 'row',
            sortable: true,
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
                    },
                    number: {
                        eq: 'Equal to',
                        neq: 'Not equal to',
                    },
                },
            },
            pageable: {
                refresh: true,
                pageSizes: [100, 250, 500],
            },
            excel: {
                fileName: 'o3go_logs.xlsx',
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
                    field: 'created_at',
                    title: 'Created',
                    width: '160px',
                    filterable: false,
                    format: '{0: yyyy-MM-dd HH:mm:ss}',
                },
                {
                    field: 'account__number',
                    title: 'Account',
                    width: '150px',
                    sortable: false,
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    },
                    template: function(item) {
                        return item.account && item.account.number ? item.account.number : '';
                    }
                },
                {
                    field: 'event',
                    title: 'Event',
                    width: '160px',
                    filterable: {
                        ui : function(element) {
                            element.kendoDropDownList({
                                animation: false,
                                dataSource: [
                                    {value: 'account', text: 'account.*'},
                                    {value: 'session', text: 'session.*'},
                                    {value: 'message', text: 'message.*'},
                                    {value: 'account.create', text: 'account.create'},
                                    {value: 'account.update', text: 'account.update'},
                                    {value: 'account.status', text: 'account.status'},
                                    {value: 'session.create', text: 'session.create'},
                                    {value: 'session.update', text: 'session.update'},
                                    {value: 'session.status', text: 'session.status'},
                                    {value: 'message.create', text: 'message.create'},
                                    {value: 'message.update', text: 'message.update'},
                                    {value: 'message.status' text: 'message.status'}
                                ],
                                dataTextField: 'text',
                                dataValueField: 'value',
                                valuePrimitive: true,
                                optionLabel: '-- Select Event --'
                            });
                        }
                    }
                },
                {
                    field: 'source',
                    title: 'Source',
                    width: '120px',
                    filterable: {
                        ui : function(element) {
                            element.kendoDropDownList({
                                animation: false,
                                dataSource: ['api', 'ext_api', 'app_api', 'scheduler', 'system'],
                                optionLabel: '-- Select Source --'
                            });
                        }
                    }
                },
                {
                    field: 'status',
                    title: 'Status',
                    width: '120px',
                    template: statusBadge,
                    sortable: false,
                    filterable: {
                        operators: {
                            string: {
                                eq: 'Equal to',
                                neq: 'Not equal to'
                            },
                        },
                        ui : function(element) {
                            element.kendoDropDownList({
                                animation: false,
                                dataSource: [
                                    {value: 'active', text: 'ACTIVE'},
                                    {value: 'available', text: 'AVAILABLE'},
                                    {value: 'banned', text: 'BANNED'},
                                    {value: 'created', text: 'CREATED'},
                                    {value: 'delivered', text: 'DELIVERED'},
                                    {value: 'failed', text: 'FAILED'},
                                    {value: 'finished', text: 'FINISHED'},
                                    {value: 'paused', text: 'PAUSED'},
                                    {value: 'sent', text: 'SENT'},
                                    {value: 'undelivered', text: 'UNDELIVERED'},
                                    {value: 'waiting', text: 'WAITING'}
                                ],
                                dataTextField: 'text',
                                dataValueField: 'value',
                                valuePrimitive: true,
                                optionLabel: '-- Select Status --'
                            });
                        }
                    }
                },
                {
                    field: 'account_id',
                    title: 'Account ID',
                    width: '110px',
                    format: '{0:n0}'
                },
                {
                    field: 'session_id',
                    title: 'Session ID',
                    width: '110px',
                    format: '{0:n0}'
                },
                {
                    field: 'message_id',
                    title: 'Message ID',
                    width: '115px',
                    format: '{0:n0}'
                }
            ].concat(user_column).concat([
                {
                    field: 'context',
                    title: 'Context',
                    filterable: false,
                    sortable: false,
                    template: contextTemplate
                },
                {}
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

        $('#logs-grid').on('dblclick', "td[role='gridcell']", function (e) {
            var text = $(this).find('.text');
            if (text.length) text.selectText();
            else $(this).selectText();
        });

        $(document).keydown(function (e) {
            if (e.key === 'Escape') {
                $('#logs-grid').data('kendoGrid').clearSelection();
            }
        });
    } catch (error) {
        console.warn(error);
    }
    window.optimize_grid(['#logs-grid']);
}
