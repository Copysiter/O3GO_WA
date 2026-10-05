(function (window, $) {
    'use strict';

    var api = window.DashboardApi;
    var demo = new URLSearchParams(window.location.search).get('demo') === '1';
    var provider;
    var colors;
    var seriesInfo = {
        opened: { label: 'Открыто', color: 'primary' },
        finished: { label: 'Завершено', color: 'success' },
        sessionBans: { label: 'Забанено', color: 'error' },
        accountBans: { label: 'Баны аккаунтов', color: 'error' },
        sent: { label: 'SENT', color: 'primary' },
        delivered: { label: 'DELIVERED', color: 'success' },
        undelivered: { label: 'UNDELIVERED', color: 'warning' },
        failed: { label: 'FAILED', color: 'error' },
        accountErrors: { label: 'account.error', color: 'error' },
        sessionErrors: { label: 'session.error', color: 'error' }
    };
    var metrics = [
        { key: 'opened', label: 'Открыто сессий', tone: 'blue', icon: 'play-circle-outline',
            description: 'Успешные открытия рабочих сессий за выбранный период.' },
        { key: 'finished', label: 'Завершено сессий', tone: 'teal', icon: 'check-circle-outline',
            description: 'Переходы сессий в FINISHED, включая автоматическое завершение.' },
        { key: 'sessionBans', label: 'Баны сессий', tone: 'red', icon: 'cancel', negative: true,
            description: 'Зарегистрированные переходы сессий в BANNED за выбранный период.' },
        { key: 'accountBans', label: 'Баны аккаунтов', tone: 'red', icon: 'account-off', negative: true,
            description: 'Зарегистрированные переходы аккаунтов в BANNED. Не каждый бан сессии приводит к бану аккаунта.' },
        { key: 'sent', label: 'Подтверждено отправок', tone: 'blue', icon: 'send',
            description: 'Первые сохранённые подтверждения SENT, DELIVERED или UNDELIVERED. Это не число сообщений, которые сейчас имеют статус SENT.' },
        { key: 'delivered', label: 'Подтверждено доставок', tone: 'teal', icon: 'check-all',
            description: 'Первые подтверждения доставки сообщений, зарегистрированные за выбранный период.' },
        { key: 'accountErrors', label: 'Сбои загрузки аккаунтов', tone: 'red', icon: 'alert-circle-outline', negative: true,
            description: 'Операции с account.error. Сбой после сохранения аккаунта может сопровождаться HTTP 201.' },
        { key: 'sessionErrors', label: 'Сбои операций сессий', tone: 'red', icon: 'alert-outline', negative: true,
            description: 'Операции start, finish и ban с зарегистрированным session.error.' }
    ];
    var selectedUserId = null;
    var snapshot;
    var currentUser;
    var detailsWindow;
    var resizeObserver;
    var resizeTimer;
    var liveTimer;
    var liveSnapshot = null;
    var requests = { summary: null, live: null, users: null };
    var revisions = { summary: 0, live: 0, users: 0 };
    var summaryBusy = false;
    var usersLoaded = false;
    var disposed = false;
    var authBlocked = false;
    var identity;
    var summaryKey = null;
    var draftDates = {};
    var demoScript;
    var coverageGroups = {
        lifecycle: { label: 'Сессии и баны', keys: ['opened', 'finished', 'sessionBans', 'accountBans', 'autoFinished'] },
        messageEvents: { label: 'События сообщений', keys: ['sent', 'delivered', 'undelivered', 'failed'] },
        accountErrors: { label: 'Сбои загрузки аккаунтов', keys: ['accountErrors'] },
        sessionErrors: { label: 'Сбои операций сессий', keys: ['sessionErrors'] }
    };

    function badgeColors() {
        var result = {};
        ['primary', 'success', 'warning', 'error'].forEach(function (name) {
            var badge = $('<span class="k-badge k-badge-solid k-badge-' + name + '" aria-hidden="true"></span>')
                .css({ position: 'absolute', visibility: 'hidden' }).appendTo(document.body);
            result[name] = badge.css('background-color');
            badge.remove();
        });
        return result;
    }

    function encode(value) {
        return kendo.htmlEncode(value === null || value === undefined ? '—' : String(value));
    }

    function number(value) {
        return value === null || value === undefined ? '—' : value.toLocaleString('ru-RU');
    }

    function percent(value) {
        return value === null || value === undefined ? '—' : value.toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + '%';
    }

    function displayDate(date) {
        return date.slice(8, 10) + '.' + date.slice(5, 7) + '.' + date.slice(0, 4) + ' ' + date.slice(11, 16);
    }

    function pickerDate(date) {
        var value = new Date(date);
        // Picker wall-clock fields represent UTC, independent of the browser's offset.
        return new Date(value.getUTCFullYear(), value.getUTCMonth(), value.getUTCDate(),
            value.getUTCHours(), value.getUTCMinutes(), value.getUTCSeconds());
    }

    function readDate(selector, optional) {
        var input = $(selector);
        var raw = Object.prototype.hasOwnProperty.call(draftDates, input.attr('id'))
            ? draftDates[input.attr('id')] : input.val();
        raw = raw.trim();
        if (!raw) {
            if (optional) return null;
            throw new RangeError('Укажите начало периода.');
        }
        // Parse wall-clock text as UTC, not as a potentially missing local DST hour.
        var parts = /^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})$/.exec(raw);
        if (parts) {
            var day = Number(parts[1]), month = Number(parts[2]), year = Number(parts[3]);
            var hour = Number(parts[4]), minute = Number(parts[5]);
            var value = new Date(Date.UTC(year, month - 1, day, hour, minute));
            if (value.getUTCFullYear() === year && value.getUTCMonth() === month - 1 &&
                    value.getUTCDate() === day && value.getUTCHours() === hour && value.getUTCMinutes() === minute) {
                return value.toISOString();
            }
        }
        throw new RangeError('Проверьте ' + (optional ? 'окончание' : 'начало') + ' периода: нужен формат ДД.ММ.ГГГГ ЧЧ:ММ.');
    }

    function showError(error, validation) {
        $('#dashboard-error').prop('hidden', false).attr('data-kind', validation ? 'validation' : 'runtime')
            .text(error.message + (snapshot ? ' Ниже показаны ранее загруженные данные за предыдущий корректный период.' : ''));
        if (!(error instanceof RangeError) && !(error instanceof api.ApiError)) console.error('Dashboard:', error);
    }

    function metricChange(metric) {
        if (!snapshot) return { text: 'Нет данных', tone: 'neutral', comparison: '' };
        var value = snapshot.totals[metric.key];
        var previous = snapshot.previous[metric.key];
        if (value === null) return { text: 'Нет полного учёта', tone: 'neutral', comparison: '' };
        if (previous === null) return { text: 'Сравнение недоступно', tone: 'neutral', comparison: '' };
        var difference = value - previous;
        if (!difference) return { text: 'Без изменений', tone: 'neutral' };
        var rising = difference > 0;
        return {
            text: previous ? (rising ? '↑ ' : '↓ ') + percent(Math.abs(difference / previous * 100)) : '+' + number(value),
            tone: rising === Boolean(metric.negative) ? 'negative' : 'positive'
        };
    }

    function renderMetrics() {
        var template = kendo.template(
            '<button type="button" class="dashboard-metric dashboard-tone-#: tone #" data-metric="#: key #" ' +
                'aria-label="#: label #: #: value #. Открыть график за период">' +
                '<span class="dashboard-metric-top"><span>#: label #</span>' +
                    '<span class="dashboard-metric-icon"><i class="mdi mdi-#: icon #" aria-hidden="true"></i></span></span>' +
                '<span class="dashboard-metric-value">#: value #</span>' +
                '<span class="dashboard-metric-bottom"><span class="dashboard-change dashboard-change-#: changeTone #">#: change #</span>' +
                    '<span>#: comparison #</span></span>' +
            '</button>'
        );
        $('#dashboard-metrics').html(metrics.map(function (metric) {
            var change = metricChange(metric);
            return template($.extend({}, metric, {
                value: number(snapshot ? snapshot.totals[metric.key] : null), change: change.text,
                changeTone: change.tone, comparison: change.comparison === '' ? '' : 'к предыдущему периоду'
            }));
        }).join(''));
        $('#dashboard-metrics button').prop('disabled', !snapshot || summaryBusy || authBlocked);
    }

    function chartSeries(keys) {
        return keys.map(function (key) {
            var info = seriesInfo[key];
            return {
                name: info.label, field: key, categoryField: 'label', type: 'column',
                color: colors[info.color], missingValues: 'gap'
            };
        });
    }

    function updateChart(selector, data, series, extra) {
        var options = $.extend(true, {
            transitions: false,
            chartArea: { background: 'transparent', height: 270, margin: { top: 12, right: 12, bottom: 0, left: 0 } },
            legend: { position: 'bottom', labels: { font: '11px Arial', color: '#718298' } },
            dataSource: { data: data },
            series: series,
            seriesDefaults: { border: { width: 0 }, overlay: { gradient: 'none' }, gap: 1.4, spacing: 0.35, missingValues: 'gap' },
            categoryAxis: {
                field: 'label', line: { visible: false }, majorGridLines: { visible: false },
                majorTicks: { visible: false },
                labels: { font: '10px Arial', color: '#8b99ac', step: Math.max(1, Math.ceil(data.length / 12)) }
            },
            valueAxis: {
                min: 0, line: { visible: false }, majorTicks: { visible: false },
                majorGridLines: { color: '#edf1f6', dashType: 'dash' },
                labels: { font: '10px Arial', color: '#8b99ac', format: 'n0' }
            },
            tooltip: {
                visible: true,
                template: function (event) {
                    return encode(event.category) + '<br />' + encode(event.series.name) + ': <strong>' + number(event.dataItem[event.series.field]) + '</strong>';
                }
            },
            seriesClick: function (event) {
                if (snapshot && !summaryBusy && event.dataItem[event.series.field] !== null) openInterval(event.dataItem);
            }
        }, extra || {});
        var chart = $(selector).data('kendoChart');
        if (chart) chart.setOptions(options);
        else $(selector).kendoChart(options);
        if (selector !== '#dashboard-metric-chart') {
            var note = $(selector).siblings('.dashboard-chart-state');
            if (!note.length) note = $('<p class="dashboard-chart-state" role="status"></p>').insertAfter(selector);
            var values = [];
            data.forEach(function (point) { series.forEach(function (item) { values.push(point[item.field]); }); });
            var unknown = values.filter(function (value) { return value === null; }).length;
            note.text(!snapshot ? 'Данные ещё не загружены.' : !data.length ? 'Пустой период.' :
                unknown === values.length ? 'Нет данных учёта для выбранного периода.' :
                    unknown ? 'Учёт неполный: неизвестные интервалы не показаны как нули.' : '');
        }
    }

    function renderCharts() {
        var trend = snapshot ? snapshot.trend : [];
        updateChart('#dashboard-sessions-chart', trend, chartSeries(['opened', 'finished', 'sessionBans']));
        updateChart('#dashboard-messages-chart', trend, chartSeries(['sent', 'delivered', 'undelivered', 'failed']));
        updateChart('#dashboard-account-errors-chart', trend, chartSeries(['accountErrors']));
        updateChart('#dashboard-session-errors-chart', trend, chartSeries(['sessionErrors']));
        renderDistribution('#dashboard-status-chart', snapshot ? snapshot.statuses : [], false);
        renderDistribution('#dashboard-session-status-chart', snapshot ? snapshot.sessionStatuses : [], true);
    }

    function renderDistribution(selector, statuses, sessions) {
        var data = statuses.map(function (item) {
            var key = item.status === 'banned' ? 'sessionBans' : item.status;
            return { label: sessions ? item.label : item.status.toUpperCase(), caption: item.label,
                value: item.value, color: colors[seriesInfo[key].color] };
        });
        updateChart(selector, data, [{
            type: 'bar', field: 'value', categoryField: 'label', colorField: 'color',
            missingValues: 'gap',
            labels: { visible: true, font: '11px Arial', color: '#667b95', template: function (event) {
                return event.dataItem.value === null ? '' : number(event.dataItem.value);
            } }
        }], {
            legend: { visible: false },
            categoryAxis: { reverse: true, labels: { step: 1 } },
            tooltip: { template: function (event) { return encode(event.dataItem.caption) + ': <strong>' + number(event.dataItem.value) + '</strong>'; } },
            seriesClick: function (event) {
                if (!snapshot || summaryBusy || event.dataItem.value === null) return;
                openDetails('Статус ' + event.dataItem.label,
                    '<p>' + encode(event.dataItem.caption) + '</p><div class="dashboard-modal-value">' + number(event.value) + '</div>' +
                    '<p>' + encode(rangeCaption()) + '</p>' +
                    '<p class="dashboard-modal-note">' + (sessions ? 'Количество операций за период.' : 'Текущие статусы сообщений, зарегистрированных за период.') +
                    (demo ? ' ДЕМО: все данные вымышлены.' : '') + '</p>');
            }
        });
    }

    function openDetails(title, content) {
        if (!detailsWindow) {
            detailsWindow = $('#dashboard-details').kendoWindow({
                title: title, modal: true, visible: false, resizable: false,
                width: Math.min(650, window.innerWidth - 32), actions: ['Close'], animation: false
            }).data('kendoWindow');
        }
        kendo.destroy($('#dashboard-details').children());
        detailsWindow.title(title);
        detailsWindow.setOptions({ width: Math.min(650, window.innerWidth - 32) });
        detailsWindow.content('<div class="dashboard-modal">' + content + '</div>').center().open();
        return detailsWindow;
    }

    function openInterval(point) {
        if (!point || !snapshot || summaryBusy) return;
        var caption = point.fromAt && point.toAt ? displayDate(point.fromAt) + ' — ' + displayDate(point.toAt) + ' UTC' :
            displayDate(point.key) + ' UTC · ' + (snapshot.granularity === 'hour' ? 'час' : 'день');
        openDetails('Показатели интервала', '<p>' + encode(caption + ' · ' + snapshot.scopeLabel) + '</p><dl>' +
            Object.keys(seriesInfo).map(function (key) {
                return '<dt>' + encode(seriesInfo[key].label) + '</dt><dd>' + number(point[key]) + '</dd>';
            }).join('') + '</dl><p class="dashboard-modal-note">' + (demo ? 'ДЕМО. ' : '') +
            '«—» означает неизвестный учёт. Граничные интервалы учитываются только в пределах выбранного периода.</p>');
    }

    function openMetric(key) {
        var metric = metrics.filter(function (item) { return item.key === key; })[0];
        if (!metric || !snapshot || summaryBusy) return;
        openDetails(metric.label,
            '<p>' + encode(metric.description) + '</p><div class="dashboard-modal-value">' + number(snapshot.totals[key]) + '</div>' +
            '<p class="dashboard-modal-note">' + encode(rangeCaption() + ' · ' + snapshot.scopeLabel + (demo ? ' · ДЕМО' : '')) + '</p>' +
            '<p class="dashboard-modal-note">' + encode(metricCoverage(key)) + '</p>' +
            '<div id="dashboard-metric-chart"></div>');
        updateChart('#dashboard-metric-chart', snapshot.trend, chartSeries([key]), {
            legend: { visible: false }, seriesClick: function () {}
        });
        detailsWindow.center();
    }

    function resizeCharts() {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(function () {
            $('#dashboard-content .dashboard-chart:visible').each(function () {
                var chart = $(this).data('kendoChart');
                if (chart) chart.resize();
            });
            if (detailsWindow && detailsWindow.wrapper.is(':visible')) {
                detailsWindow.setOptions({ width: Math.min(650, window.innerWidth - 32) });
                detailsWindow.center();
                kendo.resize($('#dashboard-details'));
            }
        }, 80);
    }

    function rangeCaption() {
        return displayDate(snapshot.startAt) + ' — ' + displayDate(snapshot.effectiveEndAt) + ' UTC';
    }

    function coverageReason(group, previous) {
        var code = previous ? group.previousReason : group.currentReason;
        var reasons = {
            collection_start_unknown: 'начало сбора не подтверждено',
            before_collection_start: 'период раньше начала сбора',
            period_crosses_collection_start: 'часть периода раньше начала сбора',
            missing_operation_id: 'есть записи без идентификатора операции'
        };
        return reasons[code] || 'нет полного учёта';
    }

    function metricCoverage(key) {
        if (!snapshot || !snapshot.coverage) return '';
        var name = Object.keys(coverageGroups).filter(function (group) {
            return coverageGroups[group].keys.indexOf(key) !== -1;
        })[0];
        var group = name && snapshot.coverage[name];
        if (!group || group.currentState === 'recorded') return '';
        return 'Учёт за период: ' + coverageReason(group, false) + '. Неизвестные значения обозначены «—».';
    }

    function renderCoverage() {
        var items = [];
        if (snapshot && snapshot.coverage && !demo) Object.keys(coverageGroups).forEach(function (name) {
            var group = snapshot.coverage[name];
            var parts = [];
            if (group.currentState !== 'recorded') parts.push('выбранный период — ' + coverageReason(group, false));
            if (group.previousState !== 'recorded') parts.push('сравнение — ' + coverageReason(group, true));
            if (parts.length) items.push('<li>' + encode(coverageGroups[name].label + ': ' + parts.join('; ') +
                (group.from ? '. Сбор с ' + displayDate(group.from) + ' UTC' : '')) + '.</li>');
        });
        $('#dashboard-coverage').prop('hidden', !items.length).html(items.length ?
            '<strong>Неизвестный или неполный учёт.</strong> «—» не означает ноль. Данные текущих статусов сообщений доступны отдельно.' +
            '<ul>' + items.join('') + '</ul>' : '');
    }

    function cancelRequest(channel) {
        revisions[channel] += 1;
        var previous = requests[channel];
        requests[channel] = null;
        if (previous) previous.abort();
        return revisions[channel];
    }

    function requestCurrent(channel, revision) {
        return !disposed && !authBlocked && revisions[channel] === revision;
    }

    function setSummaryLoading(loading) {
        summaryBusy = loading;
        $('#dashboard-summary, #dashboard-trends').attr('aria-busy', String(loading));
        $('#dashboard-metrics button').prop('disabled', loading || !snapshot || authBlocked);
        $('#dashboard-summary-state').text(loading ? 'Загрузка статистики…' : snapshot ?
            'Данные на ' + displayDate(snapshot.generatedAt) + ' UTC' : 'Данные не загружены.');
    }

    function clearSummary() {
        snapshot = null;
        if (detailsWindow) detailsWindow.close();
        $('#dashboard-scope, #dashboard-comparison, #dashboard-range, #dashboard-session-note, #dashboard-delivery-note').empty();
        $('#dashboard-delivery-rate').text('—');
        renderCoverage();
        renderMetrics();
        renderCharts();
    }

    function clearLive() {
        liveSnapshot = null;
        ['available', 'active', 'paused', 'banned'].forEach(function (key) {
            $('#dashboard-live-' + key).text('—');
        });
        $('#dashboard-live-scope').text('Данные не загружены');
        $('#dashboard-live-updated').empty();
        $('#dashboard-live').attr({ 'aria-busy': 'false', 'data-state': 'error' });
    }

    function principal(token) {
        if (!token || !token.user || token.user.is_active === false) throw new api.ApiError('auth', 0);
        return JSON.stringify([String(token.user.id), token.user.is_superuser]);
    }

    function stopAuthentication(error) {
        if (authBlocked || disposed) return;
        authBlocked = true;
        window.clearInterval(liveTimer);
        Object.keys(requests).forEach(cancelRequest);
        if (error.kind === 'auth') {
            localStorage.removeItem('token');
            window.isAuth = null;
        }
        clearSummary();
        clearLive();
        setSummaryLoading(false);
        $('#dashboard-options-error, #dashboard-live-error').prop('hidden', true);
        $('#dashboard-options-state').empty();
        ['#dashboard-start', '#dashboard-end'].forEach(function (selector) {
            var picker = $(selector).data('kendoDateTimePicker');
            if (picker) picker.enable(false);
        });
        var userPicker = $('#dashboard-user').data('kendoDropDownList');
        if (userPicker) {
            userPicker.close();
            userPicker.dataSource.data([]);
            userPicker.value('');
            userPicker.enable(false);
        }
        $('#dashboard-apply').data('kendoButton').enable(false);
        showError(error);
        $('#dashboard-login').prop('hidden', false).text(error.kind === 'auth' ? 'Войти заново' : 'Обновить страницу')
            .off('click.dashboard').on('click.dashboard', function () {
                if (error.kind === 'auth') window.location.href = '/auth/';
                else window.location.reload();
            });
    }

    function ensureSession() {
        if (disposed || authBlocked) return false;
        try {
            if (principal(window.getToken()) !== identity) throw new api.ApiError('session_changed', 0);
            return true;
        } catch (error) {
            stopAuthentication(error instanceof api.ApiError ? error : new api.ApiError('auth', 0));
            return false;
        }
    }

    function handleAuthError(error) {
        if (['auth', 'session_changed', 'scope_mismatch'].indexOf(error.kind) === -1) return false;
        stopAuthentication(error);
        return true;
    }

    function renderSummary() {
        $('#dashboard-scope').text(snapshot.scopeLabel + ' · ' + rangeCaption() + (snapshot.endAt === null ? ' · до текущего момента' : ''));
        $('#dashboard-comparison').text('Сравнение: ' + displayDate(snapshot.comparison.startAt) + ' — ' + displayDate(snapshot.comparison.endAt) + ' UTC');
        $('#dashboard-range').text(rangeCaption() + ' · ' + (snapshot.granularity === 'hour' ? 'по часам' : 'по дням'));
        $('#dashboard-session-note').text('За период завершено планировщиком: ' + number(snapshot.totals.autoFinished) + '.');
        $('#dashboard-status-caption').text('Текущие статусы сообщений, зарегистрированных за период');
        $('#dashboard-delivery-rate').text(percent(snapshot.delivery.rate));
        $('#dashboard-delivery-note').text('Доставляемость по ' + number(snapshot.delivery.terminal) + ' завершённым результатам. CREATED и WAITING не показаны.');
        renderCoverage();
        renderMetrics();
        renderCharts();
        resizeCharts();
    }

    function refreshLive(force) {
        if (!provider || !ensureSession() || (requests.live && !force)) return;
        var revision = cancelRequest('live');
        $('#dashboard-live').attr({ 'aria-busy': 'true', 'data-state': 'loading' });
        $('#dashboard-live-error').prop('hidden', true);
        if (!liveSnapshot) $('#dashboard-live-updated').text('Загрузка…');
        requests.live = provider.live({ userId: selectedUserId });
        requests.live.promise.then(function (data) {
            if (!requestCurrent('live', revision) || !ensureSession()) return;
            liveSnapshot = data;
            ['available', 'active', 'paused', 'banned'].forEach(function (key) {
                $('#dashboard-live-' + key).text(number(data[key]));
            });
            $('#dashboard-live-scope').text(data.scopeLabel + ' · независимо от периода');
            $('#dashboard-live-updated').text('Обновлено ' + displayDate(data.asOf) + ' UTC');
            $('#dashboard-live').attr('data-state', 'ready');
        }).catch(function (error) {
            if (!requestCurrent('live', revision) || error.kind === 'aborted' || handleAuthError(error)) return;
            if (error.kind === 'forbidden' || error.kind === 'not_found') clearLive();
            $('#dashboard-live').attr('data-state', liveSnapshot ? 'stale' : 'error');
            if (!liveSnapshot) $('#dashboard-live-updated').text('Данные недоступны');
            $('#dashboard-live-error').prop('hidden', false).find('span').text(error.message +
                (liveSnapshot ? ' Показан последний полученный срез: ' + displayDate(liveSnapshot.asOf) + ' UTC.' : ''));
        }).finally(function () {
            if (!requestCurrent('live', revision)) return;
            requests.live = null;
            $('#dashboard-live').attr('aria-busy', 'false');
        });
    }

    function refresh(forceLive) {
        if (!provider || !ensureSession()) return;
        if (currentUser.is_superuser && !usersLoaded && !requests.users) loadUsers();
        var userPicker = $('#dashboard-user').data('kendoDropDownList');
        var userId = userPicker ? userPicker.value() || null : null;
        var changedScope = String(userId) !== String(selectedUserId);
        if (changedScope) {
            selectedUserId = userId;
            cancelRequest('summary');
            cancelRequest('live');
            clearSummary();
            clearLive();
        }
        var next;
        try {
            next = api.validateRange({
                startAt: readDate('#dashboard-start', false),
                endAt: readDate('#dashboard-end', true),
                userId: selectedUserId
            }, new Date());
        } catch (error) {
            cancelRequest('summary');
            summaryKey = null;
            setSummaryLoading(false);
            showError(error, true);
            if (changedScope || !liveSnapshot || forceLive) refreshLive(Boolean(changedScope || forceLive));
            return;
        }
        var key = JSON.stringify(next);
        if (requests.summary && summaryKey === key && !forceLive) return;
        var revision = cancelRequest('summary');
        summaryKey = key;
        if (detailsWindow) detailsWindow.close();
        $('#dashboard-error').prop('hidden', true).empty();
        setSummaryLoading(true);
        requests.summary = provider.summary(next);
        requests.summary.promise.then(function (data) {
            if (!requestCurrent('summary', revision) || !ensureSession()) return;
            snapshot = data;
            renderSummary();
        }).catch(function (error) {
            if (!requestCurrent('summary', revision) || error.kind === 'aborted' || handleAuthError(error)) return;
            if (error.kind === 'forbidden' || error.kind === 'not_found') {
                clearSummary();
            }
            showError(error, error.kind === 'validation' || error instanceof RangeError);
        }).finally(function () {
            if (!requestCurrent('summary', revision)) return;
            requests.summary = null;
            summaryKey = null;
            setSummaryLoading(false);
        });
        if (changedScope || !liveSnapshot || forceLive) refreshLive(Boolean(changedScope || forceLive));
    }

    function loadUsers() {
        if (!provider || !currentUser.is_superuser || !ensureSession()) return;
        var revision = cancelRequest('users');
        var picker = $('#dashboard-user').data('kendoDropDownList');
        picker.enable(false);
        $('#dashboard-options-error').prop('hidden', true);
        $('#dashboard-options-state').text('Загрузка списка…');
        requests.users = provider.users();
        requests.users.promise.then(function (users) {
            if (!requestCurrent('users', revision) || !ensureSession()) return;
            if (selectedUserId && !users.some(function (user) { return user.id === String(selectedUserId); })) {
                users.push({ id: String(selectedUserId), name: 'Недоступный пользователь #' + selectedUserId });
            }
            picker.dataSource.data(users);
            picker.value(selectedUserId || '');
            usersLoaded = true;
            picker.enable(true);
            $('#dashboard-options-state').empty();
        }).catch(function (error) {
            if (!requestCurrent('users', revision) || error.kind === 'aborted' || handleAuthError(error)) return;
            usersLoaded = false;
            $('#dashboard-options-state').empty();
            $('#dashboard-options-error').prop('hidden', false).find('span').text('Список пользователей: ' + error.message);
        }).finally(function () {
            if (requestCurrent('users', revision)) requests.users = null;
        });
    }

    function demoProvider() {
        var mock = window.DashboardMock;
        var demoUser = $.extend({}, currentUser, {
            name: currentUser.name || currentUser.login || 'Пользователь ' + currentUser.id
        });
        function local(build) {
            var aborted = false;
            return { promise: Promise.resolve().then(function () {
                if (aborted) throw new api.ApiError('aborted', 0);
                return build();
            }), abort: function () { aborted = true; } };
        }
        return {
            summary: function (query) { return local(function () {
                var now = new Date();
                var data = mock.build($.extend({}, query, { currentUser: demoUser, now: now }));
                data.generatedAt = now.toISOString();
                return data;
            }); },
            live: function (query) { return local(function () {
                var now = new Date();
                var users = mock.createUsers(demoUser);
                var owner = users.filter(function (user) { return user.id === query.userId; })[0];
                return $.extend(mock.live({ currentUser: demoUser, userId: query.userId, now: now }), {
                    asOf: now.toISOString(), scopeLabel: owner ? owner.name : currentUser.is_superuser ? 'Все пользователи' : users[0].name
                });
            }); },
            users: function () { return local(function () { return mock.createUsers(demoUser); }); }
        };
    }

    function updatePickerMaximum() {
        var maximum = pickerDate(new Date().toISOString());
        ['#dashboard-start', '#dashboard-end'].forEach(function (selector) {
            var picker = $(selector).data('kendoDateTimePicker');
            if (picker) picker.max(maximum);
        });
    }

    window.initDashboard = function () {
        if (!window.isAuth || !window.isAuth.user) return;
        try {
            var token = window.getToken();
            identity = principal(token);
            currentUser = token.user;
            colors = badgeColors();
            var startAt = new Date().toISOString().slice(0, 10) + 'T00:00:00.000Z';
            ['#dashboard-start', '#dashboard-end'].forEach(function (selector) {
                var popupOpen = false;
                $(selector).kendoDateTimePicker({
                    format: 'dd.MM.yyyy HH:mm', timeFormat: 'HH:mm', parseFormats: ['dd.MM.yyyy HH:mm'], interval: 30,
                    value: selector === '#dashboard-start' ? pickerDate(startAt) : null,
                    min: new Date(1900, 0, 1), max: pickerDate(new Date().toISOString()),
                    open: function () { popupOpen = true; },
                    close: function () { popupOpen = false; },
                    change: function () {
                        if (popupOpen) delete draftDates[this.element.attr('id')];
                        refresh();
                    }
                });
                $(selector).on('focus.dashboard', updatePickerMaximum).on('input.dashboard', function () {
                    draftDates[this.id] = this.value;
                }).on('blur.dashboard', function () {
                    if (Object.prototype.hasOwnProperty.call(draftDates, this.id)) {
                        this.value = draftDates[this.id];
                        delete draftDates[this.id];
                        refresh();
                    }
                });
            });
            $('#dashboard-apply').kendoButton({ icon: 'reload', click: function () { refresh(true); } });
            $('#dashboard-options-retry').kendoButton({ click: loadUsers });
            $('#dashboard-live-retry').kendoButton({ click: function () { refreshLive(true); } });
            $('#dashboard-login').kendoButton();
            if (currentUser.is_superuser) {
                $('#dashboard-user-filter').prop('hidden', false);
                $('#dashboard-user').kendoDropDownList({
                    dataSource: [], dataTextField: 'name', dataValueField: 'id', enable: false,
                    optionLabel: 'Все пользователи', filter: 'contains',
                    template: '#: name #', valueTemplate: '#: name #',
                    change: function () { refresh(); }
                });
            } else {
                $('#dashboard-own-scope').prop('hidden', false);
            }
            $('#dashboard-metrics').on('click', '[data-metric]', function () { openMetric($(this).attr('data-metric')); });
            $(window).on('resize.dashboard', resizeCharts);
            if (window.ResizeObserver) {
                resizeObserver = new window.ResizeObserver(resizeCharts);
                resizeObserver.observe(document.getElementById('dashboard-content'));
            }
            clearSummary();
            clearLive();
            $('#dashboard-source').text(demo ? 'ДЕМО: вымышленные данные · API статистики не используется' : 'Статистика сервиса · UTC');
            function start() {
                if (disposed) return;
                provider = demo ? demoProvider() : api.create({ baseUrl: window.api_base_url, getToken: window.getToken });
                refresh();
                liveTimer = window.setInterval(function () { refreshLive(); }, 60000);
            }
            if (demo) {
                demoScript = $.getScript('/dashboard/js/mock_data.js').done(start).fail(function () {
                    if (!disposed) showError(new Error('Не удалось загрузить демонстрационные данные.'));
                });
            } else start();
            $(window).on('storage.dashboard', function (event) {
                if (!event.originalEvent.key || event.originalEvent.key === 'token') ensureSession();
            });
            $(window).on('pagehide.dashboard', function () {
                disposed = true;
                Object.keys(requests).forEach(cancelRequest);
                if (demoScript) demoScript.abort();
                window.clearInterval(liveTimer);
                window.clearTimeout(resizeTimer);
                if (resizeObserver) resizeObserver.disconnect();
            });
            $(window).on('pageshow.dashboard', function (event) {
                if (!event.originalEvent.persisted || !disposed) return;
                if (authBlocked || !provider) { window.location.reload(); return; }
                disposed = false;
                if (resizeObserver) resizeObserver.observe(document.getElementById('dashboard-content'));
                refresh(true);
                liveTimer = window.setInterval(function () { refreshLive(); }, 60000);
            });
        } catch (error) {
            showError(error);
        }
    };

    $(function () { window.initDashboard(); });
})(window, jQuery);
