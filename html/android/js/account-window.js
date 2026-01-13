window.initAccountWindow = function() {
    $("#account-window").kendoWindow({
        modal: true,
        width: 'auto',
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
