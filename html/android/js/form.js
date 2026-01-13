function showEditForm(model) {
    let user_field = window.isAuth.user.is_superuser ? [{
        field: "user_id",
        label: "User:",
        colSpan: 6,
        editor: "DropDownList",
        editorOptions: {
            dataSource: {
                transport: {
                    read: {
                        url: `${api_base_url}/api/v1/options/user`,
                        type: "GET",
                        beforeSend: function (request) {
                            request.setRequestHeader('Authorization', `${token_type} ${access_token}`);
                        },
                    }
                }
            },
            dataBound: function(e) {
                // this.select(function(item) {
                //     return item.value === isAuth.user.id;
                // });
                //this.trigger("select");
            },
            dataTextField: "text",
            dataValueField: "value",
            optionLabel: "Select user...",
            valuePrimitive: true
        },
    }] : []
    return $('#form-edit-keys').kendoForm({
        orientation: 'vertical',
        formData: model,
        layout: 'grid',
        grid: { cols: 12, gutter: '15px 10px' },
        buttonsTemplate: '',
        items: [
            {
                field: 'value',
                label: 'Key',
                colSpan: window.isAuth.user.is_superuser ? 6 : 12,
                validation: { required: true }
            }].concat(user_field).concat([
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
                field: 'sep1',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15 mt-n3'></div>",
            },
        ]),
        change: function (e) {},
    });
}
