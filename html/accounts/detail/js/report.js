(function (window, $) {
    'use strict';

    var ACCOUNT_STATUS = {
        '-1': 'banned',
        '0': 'available',
        '1': 'active',
        '2': 'paused'
    };

    var MESSAGE_STATUS = {
        '-1': 'waiting',
        '0': 'created',
        '1': 'sent',
        '2': 'delivered',
        '3': 'undelivered',
        '4': 'failed'
    };

    var accountId = null;

    function escapeHtml(value) {
        return kendo.htmlEncode(
            value === null || value === undefined ? '' : String(value)
        );
    }

    function formatUtc(value) {
        if (!value) return '—';
        var date = value instanceof Date ? value : new Date(value);
        if (isNaN(date.getTime())) return '—';
        return date.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    }

    function getAccountId() {
        var pathMatch = window.location.pathname.match(
            /^\/accounts\/detail\/([0-9]+)\/?$/
        );
        if (pathMatch) return Number(pathMatch[1]);

        var queryValue = new URLSearchParams(
            window.location.search
        ).get('account_id');
        if (queryValue && /^[0-9]+$/.test(queryValue)) {
            return Number(queryValue);
        }
        return null;
    }

    function setAuthorizationHeader(request) {
        var token = window.isAuth || {};
        request.setRequestHeader(
            'Authorization',
            token.token_type + ' ' + token.access_token
        );
    }

    function readParameters(data, fixedFilters) {
        var result = {
            skip: typeof data.skip === 'number' ? data.skip : 0,
            limit: typeof data.take === 'number' ? data.take : 100
        };
        return $.extend(result, fixedFilters);
    }

    function showRequestError(xhr) {
        var detail = xhr && xhr.responseJSON && xhr.responseJSON.detail;
        var message = typeof detail === 'string'
            ? detail
            : 'Unable to load account data.';
        $('#report-error').removeClass('d-none').text(message);
    }

    function statusBadge(status) {
        var badgeClasses = {
            active: 'success',
            available: 'primary',
            banned: 'error',
            created: 'light',
            delivered: 'success',
            failed: 'error',
            finished: 'primary',
            paused: 'warning',
            sent: 'primary',
            undelivered: 'warning',
            waiting: 'light'
        };
        var normalized = String(status || 'unknown').toLowerCase();
        var badgeClass = badgeClasses[normalized] || 'light';
        return '<span class="badge badge-sm k-badge k-badge-solid ' +
            'k-badge-md k-badge-rounded k-badge-' + badgeClass + '">' +
            escapeHtml(normalized.toUpperCase()) + '</span>';
    }

    function fileState(file) {
        var exists = Boolean(file && file.exists);
        var badgeClass = exists ? 'success' : 'error';
        var badgeText = exists ? 'FOUND' : 'NOT FOUND';
        var fileName = file && file.name
            ? '<span class="file-name">' + escapeHtml(file.name) + '</span>'
            : '';
        return '<span class="file-state">' +
            '<span class="badge badge-sm k-badge k-badge-solid ' +
                'k-badge-md k-badge-rounded k-badge-' + badgeClass + '">' +
                badgeText + '</span>' +
            fileName +
        '</span>';
    }

    function formatDelivery(delivery) {
        if (!delivery || delivery.rate === null) return '—';
        return kendo.toString(delivery.rate / 100, 'p1');
    }

    function renderToolbar() {
        $('#report-toolbar').kendoToolBar({
            items: [
                {
                    template: "<div class='k-window-title ps-6'>" +
                        'Account Report #' + escapeHtml(accountId) +
                        '</div>'
                },
                { type: 'spacer' },
                {
                    type: 'button',
                    text: 'Refresh',
                    click: refreshReport
                }
            ]
        });
    }

    function renderMetrics(summary) {
        var currentSessionCaption = summary.current_session_id
            ? 'session #' + summary.current_session_id
            : 'no active session';
        var metrics = [
            {
                label: 'Sessions',
                value: summary.session_count,
                caption: 'all stored session rows'
            },
            {
                label: 'Messages current / total',
                value: summary.message_count_current + ' / ' +
                    summary.message_count_total,
                caption: currentSessionCaption
            },
            {
                label: 'Delivery current session',
                value: formatDelivery(summary.delivery_current),
                caption: currentSessionCaption + ' · ' +
                    summary.delivery_current.terminal + ' terminal outcomes'
            },
            {
                label: 'Delivery all-time',
                value: formatDelivery(summary.delivery_all_time),
                caption: summary.delivery_all_time.terminal +
                    ' stored terminal outcomes'
            }
        ];
        var template = kendo.template(
            '<article class="metric-card">' +
                '<div class="metric-label">#: label #</div>' +
                '<div class="metric-value">#: value #</div>' +
                '<div class="metric-caption">#: caption #</div>' +
            '</article>'
        );

        $('#metric-cards').html(metrics.map(function (metric) {
            return template(metric);
        }).join(''));
    }

    function renderAccountState(summary) {
        var account = summary.account;
        var status = ACCOUNT_STATUS[String(account.status)] || account.status;
        var cooldownValue = account.cooldown
            ? account.cooldown + ' min' + (
                account.cooldown_until
                    ? ' · until ' + formatUtc(account.cooldown_until)
                    : ''
            )
            : 'not configured';
        var stateItems = [
            ['Status', statusBadge(status)],
            ['Account ID / UUID', escapeHtml(
                account.id + ' / ' + (account.uuid || '—')
            )],
            ['Owner', escapeHtml(
                account.owner.name + ' (#' + account.owner.id + ')'
            )],
            ['Cooldown', escapeHtml(cooldownValue)],
            ['Archive', fileState(account.archive)],
            ['Profile', fileState(account.profile)]
        ];
        $('#account-state').html('<dl class="state-grid">' +
            stateItems.map(function (item) {
                return '<div class="state-item"><dt>' +
                    escapeHtml(item[0]) + '</dt><dd>' + item[1] +
                    '</dd></div>';
            }).join('') + '</dl>');
        $('#report-toolbar .k-window-title').text(
            'Account Report · ' + account.number + ' (#' +
            account.id + ')'
        );
    }

    function loadSummary() {
        return $.ajax({
            url: api_base_url + '/api/v1/accounts/' + accountId + '/summary',
            type: 'GET',
            dataType: 'json',
            beforeSend: setAuthorizationHeader
        }).done(function (summary) {
            $('#report-error').addClass('d-none').empty();
            renderMetrics(summary);
            renderAccountState(summary);
        }).fail(showRequestError);
    }

    function baseDataSource(url, fixedFilters, fields) {
        return {
            transport: {
                read: {
                    url: api_base_url + url,
                    type: 'GET',
                    dataType: 'json',
                    beforeSend: setAuthorizationHeader
                },
                parameterMap: function (data, type) {
                    return type === 'read'
                        ? readParameters(data, fixedFilters)
                        : data;
                }
            },
            pageSize: 100,
            serverPaging: true,
            serverFiltering: true,
            serverSorting: false,
            schema: {
                data: 'data',
                total: 'total',
                model: {
                    id: 'id',
                    fields: fields
                }
            },
            error: showRequestError
        };
    }

    function initSessionsGrid() {
        $('#sessions-grid').kendoGrid({
            dataSource: baseDataSource(
                '/api/v1/sessions/',
                { account_id: accountId },
                {
                    id: { type: 'number' },
                    ext_id: { type: 'string' },
                    msg_count: { type: 'number' },
                    created_at: { type: 'date' },
                    updated_at: { type: 'date' }
                }
            ),
            sortable: false,
            resizable: true,
            reorderable: true,
            pageable: { refresh: true, pageSizes: [100, 250, 500] },
            filterable: false,
            columns: [
                { field: 'id', title: 'ID', width: 100 },
                { field: 'ext_id', title: 'External ID', width: 220 },
                { field: 'msg_count', title: 'Messages', width: 140 },
                {
                    field: 'created_at',
                    title: 'Created',
                    width: 180,
                    template: function (item) {
                        return formatUtc(item.created_at);
                    }
                },
                {
                    field: 'updated_at',
                    title: 'Updated',
                    width: 180,
                    template: function (item) {
                        return formatUtc(item.updated_at);
                    }
                },
                {}
            ]
        });
    }

    function initMessagesGrid() {
        $('#messages-grid').kendoGrid({
            dataSource: baseDataSource(
                '/api/v1/messages/',
                { session__account_id: accountId },
                {
                    id: { type: 'number' },
                    session_id: { type: 'number' },
                    geo: { type: 'string' },
                    status: { type: 'number' },
                    text: { type: 'string' },
                    created_at: { type: 'date' },
                    updated_at: { type: 'date' }
                }
            ),
            sortable: false,
            resizable: true,
            reorderable: true,
            pageable: { refresh: true, pageSizes: [100, 250, 500] },
            filterable: false,
            columns: [
                { field: 'id', title: 'ID', width: 100 },
                { field: 'session_id', title: 'Session ID', width: 110 },
                { field: 'geo', title: 'GEO', width: 80 },
                {
                    field: 'status',
                    title: 'Status',
                    width: 120,
                    template: function (item) {
                        return statusBadge(
                            MESSAGE_STATUS[String(item.status)] || item.status
                        );
                    }
                },
                {
                    field: 'created_at',
                    title: 'Created',
                    width: 180,
                    template: function (item) {
                        return formatUtc(item.created_at);
                    }
                },
                {
                    field: 'updated_at',
                    title: 'Updated',
                    width: 180,
                    template: function (item) {
                        return formatUtc(item.updated_at);
                    }
                },
                {
                    field: 'text',
                    title: 'Text',
                    template: function (item) {
                        return '<span class="cell-wrap">' +
                            escapeHtml(item.text) + '</span>';
                    }
                }
            ]
        });
    }

    function contextTemplate(item) {
        if (!item.context || $.isEmptyObject(item.context)) {
            return '<span class="empty-context">empty</span>';
        }
        return '<span class="cell-wrap">' +
            escapeHtml(JSON.stringify(item.context)) + '</span>';
    }

    function initLogsGrid() {
        var userColumn = window.isAuth.user.is_superuser ? [{
            field: 'user_id',
            width: 100,
            title: 'User',
            template: function (item) {
                if (!item.user) return '';
                return escapeHtml(item.user.name || item.user.login || '');
            }
        }] : [];

        $('#events-grid').kendoGrid({
            dataSource: baseDataSource(
                '/api/v1/logs/',
                { account_id: accountId },
                {
                    id: { type: 'number' },
                    created_at: { type: 'date' },
                    event: { type: 'string' },
                    source: { type: 'string' },
                    status: { type: 'string' },
                    account_id: { type: 'number' },
                    session_id: { type: 'number' },
                    message_id: { type: 'number' },
                    user_id: { type: 'number' },
                    context: { type: 'object' },
                    account: { type: 'object' },
                    user: { type: 'object' }
                }
            ),
            sortable: false,
            resizable: true,
            reorderable: true,
            selectable: 'row',
            pageable: { refresh: true, pageSizes: [100, 250, 500] },
            filterable: false,
            columns: [
                {
                    field: 'created_at',
                    title: 'Created',
                    width: 160,
                    template: function (item) {
                        return formatUtc(item.created_at);
                    }
                },
                {
                    field: 'account__number',
                    title: 'Account',
                    width: 150,
                    template: function (item) {
                        return item.account && item.account.number
                            ? escapeHtml(item.account.number)
                            : '';
                    }
                },
                { field: 'event', title: 'Event', width: 160 },
                { field: 'source', title: 'Source', width: 120 },
                {
                    field: 'status',
                    title: 'Status',
                    width: 120,
                    template: function (item) {
                        return item.status ? statusBadge(item.status) : '';
                    }
                },
                { field: 'account_id', title: 'Account ID', width: 110 },
                {
                    field: 'session_id',
                    title: 'Session ID',
                    width: 110,
                    template: function (item) {
                        return item.session_id === null ? '' : item.session_id;
                    }
                },
                {
                    field: 'message_id',
                    title: 'Message ID',
                    width: 115,
                    template: function (item) {
                        return item.message_id === null ? '' : item.message_id;
                    }
                }
            ].concat(userColumn).concat([
                {
                    field: 'context',
                    title: 'Context',
                    template: contextTemplate
                },
                {}
            ])
        });

        $('#events-grid').on('dblclick', 'tbody tr', function () {
            var grid = $('#events-grid').data('kendoGrid');
            var item = grid.dataItem(this);
            if (item) openEventDetails(item);
        });
    }

    function openEventDetails(item) {
        var actor = item.user
            ? item.user.name || item.user.login
            : item.source === 'scheduler' ? 'scheduler' : 'unknown/deleted';
        var context = item.context && !$.isEmptyObject(item.context)
            ? JSON.stringify(item.context, null, 2)
            : '{}';
        var content = '<div class="event-detail">' +
            '<div class="event-detail-grid">' +
                '<div class="event-detail-label">Event ID</div><div>' +
                    escapeHtml(item.id) + '</div>' +
                '<div class="event-detail-label">Created</div><div>' +
                    escapeHtml(formatUtc(item.created_at)) + '</div>' +
                '<div class="event-detail-label">Event / source</div><div>' +
                    escapeHtml(item.event + ' / ' + item.source) + '</div>' +
                '<div class="event-detail-label">Status</div><div>' +
                    statusBadge(item.status) + '</div>' +
                '<div class="event-detail-label">Actor</div><div>' +
                    escapeHtml(actor) + '</div>' +
            '</div>' +
            '<strong>Context</strong><pre>' + escapeHtml(context) + '</pre>' +
        '</div>';
        var detailsWindow = $('#event-details').data('kendoWindow');
        if (!detailsWindow) {
            detailsWindow = $('#event-details').kendoWindow({
                title: 'Log event details',
                modal: true,
                visible: false,
                width: Math.min(620, window.innerWidth - 32),
                actions: ['Close']
            }).data('kendoWindow');
        }
        detailsWindow.content(content).center().open();
    }

    function initTabs() {
        $('#report-tabs').kendoTabStrip({
            animation: false,
            value: 'Overview'
        });
    }

    function refreshReport() {
        loadSummary();
        ['#sessions-grid', '#messages-grid', '#events-grid'].forEach(
            function (selector) {
                var grid = $(selector).data('kendoGrid');
                if (grid) grid.dataSource.read();
            }
        );
    }

    window.initAccountLogReport = function () {
        accountId = getAccountId();
        if (!Number.isSafeInteger(accountId) || accountId < 1) {
            $('#report-error')
                .removeClass('d-none')
                .text(
                    'A valid account ID is required in ' +
                    '/accounts/detail/<account_id>.'
                );
            return;
        }

        renderToolbar();
        initSessionsGrid();
        initMessagesGrid();
        initLogsGrid();
        initTabs();
        loadSummary();
    };
})(window, jQuery);
