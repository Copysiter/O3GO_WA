let accountFields = [{
    field: "number",
    label: "Account Number",
    colSpan: 6
}, {
    field: 'type',
    label: 'Account Type',
    colSpan: 6,
    editor: 'DropDownList',
    editorOptions: {
        dataSource: new kendo.data.DataSource({
            data: [
                { text: 'WhatsApp', value: 1 },
                { text: 'WhatsApp Бизнес', value: 2 }
            ]
        }),
        select: function (e) {},
        dataTextField: 'text',
        dataValueField: 'value',
        valuePrimitive: true,
        downArrow: true,
        animation: false,
        autoClose: true,
        validation: { required: true }
    }
}, {
    field: "sep0",
    colSpan: 12,
    label: false,
    editor: "<div class='separator mx-n15'></div>"
}, {
    field: "group",
    label: "Account Group",
    colSpan: 6
}, {
    field: "geo",
    label: "Account GEO",
    colSpan: 6
}, {
    field: "sep1",
    colSpan: 12,
    label: false,
    editor: "<div class='separator mx-n15'></div>"
}, {
    field: "limit",
    label: "Message Sending Limit :",
    editor: 'NumericTextBox',
    editorOptions: {
        format: "n0",
        min: 1
    },
    colSpan: 6
}, {
    field: "cooldown",
    label: "Message Sending Pause:",
    editor: 'NumericTextBox',
    editorOptions: {
        format: "n0",
        min: 1
    },
    colSpan: 6
}, {
    field: "sep2",
    colSpan: 12,
    label: false,
    editor: "<div class='separator mx-n15'></div>"
}, {
    field: "info_1",
    label: "Info 1",
    colSpan: 6
}, {
    field: "info_2",
    label: "Info 2",
    colSpan: 6
}, {
    field: "sep3",
    colSpan: 12,
    label: false,
    editor: "<div class='separator mx-n15'></div>"
}, {
    field: "info_3",
    label: "Info 3",
    colSpan: 6
}, {
    field: "info_4",
    label: "Info 4",
    colSpan: 6
}, {
    field: "sep4",
    colSpan: 12,
    label: false,
    editor: "<div class='separator mx-n15'></div>"
}, {
    field: "info_5",
    label: "Info 5",
    colSpan: 6
}, {
    field: "info_6",
    label: "Info 6",
    colSpan: 6
}, {
    field: "sep5",
    colSpan: 12,
    label: false,
    editor: "<div class='separator mx-n15'></div>"
}, {
    field: "info_7",
    label: "Info 7",
    colSpan: 6
}, {
    field: "info_8",
    label: "Info 8",
    colSpan: 6
}, {
    field: "sep6",
    colSpan: 12,
    label: false,
    editor: "<div class='separator mx-n15'></div>"
}];

window.initWindow = function() {
    $("#account-window").kendoWindow({
        modal: true,
        width: '480px',
        height: 'auto',
        maxHeight: '90%',
        opacity: "0.1",
        visible: false,
        animation: false,
        draggable: true,
        resizable: false,
        appendTo: "body",
        title: 'New Account',
        actions: ["Close"],
        open: function(e) {
        },
        close: function(e) {
        }
    }).data("kendoWindow");

}

function initForm() {
    return $('#account-form').kendoForm({
        orientation: 'vertical',
        formData: {
            files: [],
            profile_file_name: null
        },
        layout: 'grid',
        grid: { cols: 12, gutter: '15px 10px' },
        buttonsTemplate: '',
        items: accountFields.concat([{
            field: "file",
            label: "Account Archive File",
            colSpan: 12,
            editor: function(container, options) {
                $('<input type="file" name="' + options.field + '" id="' + options.field + '"/>')
                    .appendTo(container)
                    .kendoUpload({
                        async: {
                            saveUrl: `${api_base_url}/api/v1/accounts/upload`,
                            removeUrl: `${api_base_url}/api/v1/accounts/remove`,
                            removeField: 'file_name',
                            autoUpload: true,
                            withCredentials: false,
                        },
                        validation: { allowedExtensions: [".gz"] },
                        multiple: true,

                        beforeSend: function (xhr) {
                            xhr.setRequestHeader("Authorization", `${token_type} ${access_token}`);
                        },

                        // Добавляем строки в грид по мере успешной загрузки файлов
                        success: function(e) {
                            if (e.operation !== 'upload') return;
                            let form = $("#account-form").getKendoForm();
                            let model = options.model;
                            const file_name = e.response.file_name;
                            if ('files' in model) {
                                model.files.push(file_name);
                            } else {
                                model.set("files", [file_name]);
                            }
                        },
                        // Пользователь удаляет файл из Upload → удаляем и строку из грида
                        remove: function(e) {
                            let model = options.model;
                            const file_name = e.files[0].name;
                            if ('files' in model) {
                                model.files = model.files.filter(
                                    f => f !== file_name
                                );
                            }
                        },
                        error: function(e) {
                            console.warn('Upload error', e);
                        }
                    });
                },
                validation: { required: true }
            },
            {
                field: 'sep7',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15 mt-n3'></div>",
            },
            {
                field: "profile_file",
                label: "Profile Text File",
                colSpan: 12,
                editor: function(container, options) {
                $('<input type="file" name="' + options.field + '" id="' + options.field + '"/>')
                    .appendTo(container)
                    .kendoUpload({
                        async: {
                            saveUrl: `${api_base_url}/api/v1/accounts/profile/upload`,
                            removeUrl: `${api_base_url}/api/v1/accounts/profile/remove`,
                            removeField: 'file_name',
                            autoUpload: true,
                            withCredentials: false,
                        },
                        validation: { allowedExtensions: [".txt"] },
                        multiple: false,

                        beforeSend: function (xhr) {
                            xhr.setRequestHeader("Authorization", `${token_type} ${access_token}`);
                        },

                        // Добавляем строки в грид по мере успешной загрузки файлов
                        success: function(e) {
                            if (e.operation !== 'upload') return;
                            let model = options.model;
                            if ('profile_file_name' in model) {
                                model.profile_file_name = e.response.file_name;
                            } else {
                                model.set("profile_file_name", e.response.file_name);
                            }
                        },
                        // Пользователь удаляет файл из Upload → удаляем и строку из грида
                        remove: function(e) {
                            let model = options.model;
                            if ('profile_file_name' in model) {
                                delete  model.profile_file_name;
                            }
                        },
                        error: function(e) {
                            console.warn('Upload error', e);
                        }
                    });
                },
                validation: { required: true }
            },
            {
                field: 'sep8',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15 mt-n3'></div>",
            }
        ]),
        buttonsTemplate: "<div class='w-100 mt-15 mb-n15 d-flex'><button id='form-save' type='submit' class='k-button k-button-lg k-rounded-md k-button-solid k-button-solid-primary me-4'>Submit</button><button id='window-cancel' class='k-button k-button-lg k-rounded-md k-button-solid k-button-solid-base k-form-clear ms-4'>Cancel</button></div>",
        submit: function(e) {
            e.preventDefault();
            let model = e.model;
            let grid = $('#accounts-grid').data('kendoGrid');
            let form = $("#account-form").getKendoForm();
            let token = window.isAuth;
            try {
                let { access_token, token_type } = token;
                $.ajax({
                    url: `${api_base_url}/api/v1/accounts/`,
                    type: "POST",
                    dataType: 'json',
                    data: JSON.stringify(model),
                    contentType: 'application/json;charset=UTF-8',
                    beforeSend: function (xhr) {
                        xhr.setRequestHeader ("Authorization", `${token_type} ${access_token}`);
                    },
                    success: function(data) {

                    },
                    error: function(jqXHR, textStatus, ex) {

                    }
                }).then(function(data) {
                    if (true || data.id) {
                        $("#account-window").data("kendoWindow").close();
                        grid.dataSource.read();
                        delete form._model.files
                        form.clear();
                    }
                });
            } catch (error) {
                console.warn(error);
            }
        },
        clear: function(e) {
            $("#account-window").data("kendoWindow").close();
        }
    });
}

function showEditForm(model) {
    return $('#form-edit-account').kendoForm({
        orientation: 'vertical',
        formData: model,
        layout: 'grid',
        grid: { cols: 12, gutter: '15px 10px' },
        buttonsTemplate: '',
        items: accountFields,
        change: function (e) {},
    });
}
