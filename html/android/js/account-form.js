function initAccountForm() {
    return $('#account-form').kendoForm({
        orientation: 'vertical',
        formData: {
            files: []
        },
        layout: 'grid',
        grid: { cols: 12, gutter: '15px 10px' },
        buttonsTemplate: '',
        items: [
            {
                field: "limit",
                label: "Message Sending Limit :",
                editor: 'NumericTextBox',
                editorOptions: {
                    format: "n0",
                    min: -1
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
                field: "sep0",
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15'></div>"
            }, {
                field: "file",
                label: "",
                colSpan: 12,
                editor: function(container, options) {
                    $('<input type="file" name="' + options.field + '" id="' + options.field + '"/>')
                        .appendTo(container)
                        .kendoUpload({
                            async: {
                                saveUrl: `${api_base_url}/api/v1/android/accounts/upload`,
                                removeUrl: `${api_base_url}/api/v1/android/accounts/remove`,
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
                field: 'sep1',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15 mt-n3'></div>",
            }
        ],
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
                    url: `${api_base_url}/api/v1/android/accounts/`,
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

function showAccountEditForm(model) {
    return $('#form-edit-account').kendoForm({
        orientation: 'vertical',
        formData: model,
        layout: 'grid',
        grid: { cols: 12, gutter: '15px 10px' },
        buttonsTemplate: '',
        items: [
            {
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
                field: "sep0",
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15'></div>"
            }
        ],
        change: function (e) {},
    });
}
