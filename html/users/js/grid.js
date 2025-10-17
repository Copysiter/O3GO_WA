$(document).ready(function () {
    let timer = null;
    let resizeColumn = false;
    let showLoader = true;
    // let { access_token, token_type } =
    //     window.storageToken.options.offlineStorage.getItem();
    let token = window.isAuth;
    try {
        let { access_token, token_type } = token;

        var popup;
        autoFitColumn = function (grid) {
            setTimeout(function () {
                // grid.autoFitColumn('id');
                grid.autoFitColumn('name');
                grid.autoFitColumn('login');
                grid.autoFitColumn('balance');
                grid.autoFitColumn('balance_lock');
                grid.autoFitColumn('is_superuser');
                grid.autoFitColumn('connections');
            });
        };

        $('#users-grid').kendoGrid({
            dataSource: {
                transport: {
                    read: {
                        url: `http://${api_base_url}/api/v1/users/`,
                        type: 'GET',
                        beforeSend: function (request) {
                            request.setRequestHeader('Authorization', `${token_type} ${access_token}`);
                        },
                        dataType: 'json',
                    },
                    create: {
                        url: `http://${api_base_url}/api/v1/users/`,
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
                            return `http://${api_base_url}/api/v1/users/${options.id}`;
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
                            return `http://${api_base_url}/api/v1/users/${options.id}`;
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
                            id: { type: 'number', editable: false },
                            name: {
                                type: 'string',
                                editable: true,
                                validation: { required: true },
                            },
                            login: {
                                type: 'string',
                                editable: true,
                                validation: { required: true },
                            },
                            password: {
                                type: 'string',
                                editable: true
                            },
                            // balance: { type: 'number', editable: true },
                            // balance_lock: { type: 'number', editable: true },
                            is_active: { type: 'boolean', editable: true },
                            is_superuser: { editable: true },
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
                    title: e.model.id ? 'Edit User' : 'New User',
                });
                popup.center();
            },
            editable: {
                mode: 'popup',
                template: kendo.template($('#users-popup-editor').html()),
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
            save: function (e) {
                // e.model.id = e.sender.dataSource.data().length;
                e.model.is_superuser = e.model.is_superuser == 'true';
            },
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
            change: function (e) {},
            columns: [
                {
                    field: 'is_active',
                    title: '&nbsp;',
                    // width: 44,
                    template: "<div class='marker block #=is_active == 1 ? 'green' : 'red'#'><i></i></div>",
                    filterable: false,
                },
                {
                    field: 'id',
                    title: '#',
                    // width: 33,
                    filterable: false,
                },
                {
                    field: 'name',
                    title: 'Name',
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    },
                },
                {
                    field: 'login',
                    title: 'Login',
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                    },
                },
                {
                    field: 'password',
                    title: 'Password',
                    // width: 120,
                    filterable: false,
                    hidden: true,
                },
                {
                    field: 'is_superuser',
                    title: 'Role',
                    template: function (item) {
                        console.log(item);
                        if (item.is_superuser == true) {
                            return "<span class='info info-blue'>Admin</span>";
                        } else {
                            return "<span class='info info-light'>User</span>";
                        }
                    },
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'eq',
                        },
                        ui: function (element) {
                            element.kendoDropDownList({
                                animation: false,
                                dataSource: [
                                    { text: 'Customer', value: false },
                                    { text: 'Admin', value: true },
                                ],
                                dataTextField: 'text',
                                dataValueField: 'value',
                                valuePrimitive: false,
                                optionLabel: '-- Select Role --',
                            });
                        },
                    },
                },
                /*
                {
                    field: 'balance',
                    title: 'Balance',
                    format: '{0:0.00}',
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'lte',
                        },
                    },
                },
                {
                    field: 'balance_lock',
                    title: 'Lock',
                    // format: '{0:#}',
                    filterable: {
                        cell: {
                            inputWidth: 0,
                            showOperators: true,
                            operator: 'lte',
                        },
                    },
                },
                */
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
                {},
            ],
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

        $('#users-grid').on('dblclick', "td[role='gridcell']", function (e) {
            var text = $(this).find('.text');
            if (text.length) text.selectText();
            else $(this).selectText();
        });

        $(document).keydown(function (e) {
            if (e.key === 'Escape') {
                selectedDataItems = [];
                selectedItemIds = [];
                selectedItemImsi = [];
                $('#users-grid').data('kendoGrid').clearSelection();
            }
        });
    } catch (error) {
        console.warn(error);
    }
    window.optimize_grid(['#users-grid']);
});
