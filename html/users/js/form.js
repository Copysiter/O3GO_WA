function showEditForm(model) {
    const roleOptions = {
        dataSource: [
            { text: 'User', value: false },
            { text: 'Admin', value: true },
        ],
        dataTextField: 'text',
        dataValueField: 'value',
        valuePrimitive: true,
        downArrow: true,
        animation: false,
        autoClose: false,
    };

    return $('#form-edit-users').kendoForm({
        orientation: 'vertical',
        formData: model,
        layout: 'grid',
        grid: { cols: 12, gutter: '15px 10px' },
        buttonsTemplate: '',
        items: [
            {
                field: 'name',
                label: 'Name:',
                colSpan: 6,
            },
            {
                field: 'is_superuser',
                label: 'Role',
                colSpan: 6,
                editor: function (container, options) {
                    $('<input name="' + options.field + '" ' +
                        'data-bind="value:' + options.field + '" />')
                        .appendTo(container)
                        .kendoDropDownList(roleOptions);
                },
                validation: { required: true },
            },
            {
                field: 'sep1',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15'></div>",
            },

            {
                field: 'login',
                label: 'Login',
                colSpan: 6,
            },
            {
                field: 'password',
                label: 'Password',
                colSpan: 6,
                hidden: true,
            },
            {
                field: 'sep2',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15'></div>",
            },
            {
                field: 'ext_api_key',
                label: 'External API Key',
                colSpan: 12,
            },
            {
                field: 'sep3',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15'></div>",
            },
            {
                field: 'text',
                colSpan: 6,
                label: false,
                editor: "<div class='mt-3'>Enabled:</div>",
            },
            {
                field: 'is_active',
                label: '',
                editor: 'Switch',
                editorOptions: {
                    width: 70,
                },
                colSpan: 6,
            },
            {
                field: 'sep4',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15 mt-n3'></div>",
            },
        ],
        change: function (e) {},
    });
}
