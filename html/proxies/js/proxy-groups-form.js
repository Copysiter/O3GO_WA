function showProxyGroupsEditForm(model) {
    return $('#form-edit-proxy-groups').kendoForm({
        orientation: 'vertical',
        formData: model,
        layout: 'grid',
        grid: { cols: 12, gutter: '15px 10px' },
        buttonsTemplate: '',
        items: [
            {
                field: 'name',
                label: 'Name',
                colSpan: 12,
            },
            {
                field: 'proxies',
                label: 'Proxies',
                editor: "TextArea",
                editorOptions: {
                    overflow: "auto",
                    rows: 10
                },
                colSpan: 12,
            },
            {
                field: 'sep1',
                colSpan: 12,
                label: false,
                editor: "<div class='separator mx-n15 mt-n3'></div>",
            },
        ],
        change: function (e) {},
    });
}
