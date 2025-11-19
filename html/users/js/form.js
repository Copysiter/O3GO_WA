function showEditForm(model) {
    let token = window.isAuth;
    let { access_token, token_type } = token;
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
                editor: 'DropDownList',
                editorOptions: {
                    dataSource: new kendo.data.DataSource({
                        /*
                        schema: {
                            model: {
                                fields: {
                                    text: { type: "string" },
                                    value: { type: "boolean" }
                                }
                            }
                        },
                        */
                        data: [
                            { text: 'User', value: false },
                            { text: 'Admin', value: true },
                        ],
                    }),
                    select: function (e) {},
                    dataTextField: 'text',
                    dataValueField: 'value',
                    valuePrimitive: true,
                    downArrow: true,
                    animation: false,
                    autoClose: false,
                    validation: { required: true },
                    dataBound: function (e) {
                        $('#users-grid')
                            .data('kendoGrid')
                            .autoFitColumn('is_superuser');
                    },
                    change: function (e) {
                        $('#users-grid')
                            .data('kendoGrid')
                            .autoFitColumn('is_superuser');
                    },
                },
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
