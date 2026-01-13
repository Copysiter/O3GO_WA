function showVersionEditForm(model) {
    return $('#form-edit-version').kendoForm({
        orientation: 'vertical',
        formData: model,
        layout: 'grid',
        grid: { cols: 12, gutter: '15px 10px' },
        buttonsTemplate: '',
        items: [
            // {
            //     field: 'name',
            //     label: 'Name',
            //     colSpan: 12,
            //     validation: { required: true },
            // },
            {
                field: "file",
                label: "",
                colSpan: 12,
                editor: function(container, options) {
                    $('<input type="file" name="' + options.field + '" id="' + options.field + '"/>').appendTo(container).kendoUpload({
                        async: {
                            saveUrl: `${api_base_url}/api/v1/android/versions/upload`,
                            removeUrl: `${api_base_url}/api/v1/android/versions/remove`,
                            removeField: 'file_name',
                            autoUpload: true,
                            withCredentials: false
                        },
                        validation: {
                            allowedExtensions: [".apk"],
                        },
                        multiple: false,
                        beforeSend: function (xhr) {
                            xhr.setRequestHeader ("Authorization", `${token_type} ${access_token}`);
                        },
                        success: function(e) {
                            const file_name = e.response.file_name;
                            const grid = $('#versions-grid').data('kendoGrid');
                            const model = grid.editable && grid.editable.options.model;

                            if (model) {
                                model.set("file_name", file_name);
                            }
                        }
                    });
                },
                validation: { required: true }
            },
            {
                field: 'sep2',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15 mt-n3'></div>",
            },
            {
                field: 'description',
                label: 'Description',
                editor: 'TextArea',
                editorOptions: {
                    rows: 3
                },
                colSpan: 12,
            },
            {
                field: 'sep3',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15 mt-n3'></div>",
            },
        ],
        change: function (e) {},
    });
}
