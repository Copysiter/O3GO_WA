window.initGrid = function() {
    let timer = null;
    let resizeColumn = false;
    let showLoader = true;
    // let { access_token, token_type } =
    //     window.storageToken.options.offlineStorage.getItem();
    let token = window.isAuth;
    try {
        let { access_token, token_type } = token;

        var popup;

        stripFunnyChars = function (value) {
            return (value+'').replace(/[\x09-\x10]/g, '') ? value : '';
        }

        let user_column = window.isAuth.user.is_superuser ? [{
            field: 'user_id',
            width: '100px',
            title: 'User',
            template: function (obj) {
                 if (obj.user != undefined) return obj.user.name;
                 return '';
            },
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
        }] : []

        $('#android-grid').kendoGrid({
            dataSource: {
                transport: {
                    read: {
                        url: `${api_base_url}/api/v1/androids/`,
                        type: 'GET',
                        beforeSend: function (request) {
                            request.setRequestHeader('Authorization', `${token_type} ${access_token}`);
                        },
                        dataType: 'json',
                    },
                    create: {
                        url: `${api_base_url}/api/v1/androids/`,
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
                            return `${api_base_url}/api/v1/androids/${options.id}`;
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
                            return `${api_base_url}/api/v1/androids/${options.id}`;
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
                                editable: true
                            },
                            color_txt: {
                                type: 'string',
                                editable: true
                            },
                            color_bg: {
                                type: 'string',
                                editable: true
                            },
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
                e.model.color_txt = e.model.color_txt || "#FFFFFF";
                e.model.color_bg = e.model.color_bg || "#000000";
                form.data('kendoForm').setOptions({
                    formData: e.model,
                });
                popup.setOptions({
                    title: e.model.id ? 'Edit Android Device' : 'New Android Device',
                });
                popup.center();
            },
            editable: {
                mode: 'popup',
                template: kendo.template($('#android-popup-editor').html()),
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
                // let toolbar = $('#android-toolbar').data('kendoToolBar');
                // let rows = this.select();
                // if (rows.length > 0) {
                //     toolbar.show($('#delete'));
                // } else {
                //     toolbar.hide($('#delete'));
                // }
            },
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
                    filterable: false
                }].concat(user_column).concat([
                {
                    field: 'auth_code',
                    title: 'Auth Code',
                    filterable: false
                },
                {
                    field: 'device',
                    title: 'Device ID (Api Key)',
                    filterable: false
                },
                {
                    field: 'device_origin',
                    title: 'Origin Device ID',
                    filterable: false
                },
                {
                    field: 'device_name',
                    title: 'Device Name',
                    filterable: false
                },
                {
                    field: 'manufacturer',
                    title: 'Manufacturer',
                    filterable: false
                },
                {
                    field: 'version',
                    title: 'App Version',
                    filterable: false
                },
                {
                    field: 'android_version',
                    title: 'Android version',
                    filterable: false
                },
                {
                    field: 'operator_name',
                    title: 'Operator',
                    filterable: false
                },
                {
                    field: 'bat',
                    title: 'Battery',
                    filterable: false
                },
                {
                    field: 'charging',
                    title: 'Charging',
                    filterable: false
                },
                {
                    field: 'push_id',
                    title: 'Push ID',
                    filterable: false,
                    template: function(item) {
                        if (item.msg_template != undefined) {
                            return `<div class="long_text">
                                    ${item.push_id.replaceAll("\n", "<br>")}
                                    </div>`;
                        } else {
                            return '';
                        }
                    }
                },
                {
                    field: 'info_data',
                    title: 'Info data',
                    filterable: false,
                    template: function(item) {
                        if (item.msg_template != undefined) {
                            return `<div class="long_text">
                                    ${item.info_data.replaceAll("\n", "<br>")}
                                    </div>`;
                        } else {
                            return '';
                        }
                    }
                },
                {
                    field: 'type',
                    title: 'Type',
                    filterable: false,
                    template: "#=is_active == 2 ? 'WhatsApp Business' : 'WhatsApp'#",
                },
                {
                    command: [
                        // {
                        //     name: 'edit',
                        //     iconClass: {
                        //         edit: 'k-icon k-i-edit',
                        //         update: '',
                        //         cancel: '',
                        //     },
                        //     text: {
                        //         edit: '',
                        //         update: 'Save',
                        //         cancel: 'Cancel',
                        //     },
                        // },
                        { name: 'destroy', text: '' },
                    ],
                    title: '',
                    // width: 86,
                },
                {},
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

        $('#android-grid').on('dblclick', "td[role='gridcell']", function (e) {
            var text = $(this).find('.text');
            if (text.length) text.selectText();
            else $(this).selectText();
        });

        $(document).keydown(function (e) {
            if (e.key === 'Escape') {
                selectedDataItems = [];
                selectedItemIds = [];
                selectedItemImsi = [];
                $('#android-grid').data('kendoGrid').clearSelection();
                $('#android-toolbar').data('kendoToolBar').hide($('#delete'));
            }
        });
    } catch (error) {
        console.warn(error);
    }
    window.optimize_grid(['#android-grid']);
}
