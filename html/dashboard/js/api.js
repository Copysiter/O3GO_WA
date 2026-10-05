(function (window) {
    'use strict';

    var MIN_TIME = Date.parse('1900-01-01T00:00:00Z');
    var METRICS = [
        ['opened', 'opened'], ['finished', 'finished'], ['session_bans', 'sessionBans'],
        ['account_bans', 'accountBans'], ['sent', 'sent'], ['delivered', 'delivered'],
        ['undelivered', 'undelivered'], ['failed', 'failed'], ['account_errors', 'accountErrors'],
        ['session_errors', 'sessionErrors'], ['auto_finished', 'autoFinished'],
        ['message_created', 'messageCreated']
    ];
    var MESSAGE_STATUSES = [
        ['sent', 'Отправлены, ожидают результата'], ['delivered', 'Доставлены'],
        ['undelivered', 'Не доставлены'], ['failed', 'Ошибка отправки']
    ];
    var SESSION_STATUSES = [
        ['opened', 'Открыто'], ['finished', 'Завершено'], ['banned', 'Забанено']
    ];
    var MESSAGES = {
        auth: 'Требуется повторный вход в систему.',
        forbidden: 'Нет доступа к выбранной области данных.',
        not_found: 'Выбранный пользователь не найден.',
        validation: 'Проверьте период и выбранного пользователя.',
        unavailable: 'Статистика временно недоступна. Повторите запрос позже.',
        network: 'Не удалось связаться с сервером.',
        timeout: 'Время ожидания ответа сервера истекло.',
        aborted: 'Запрос отменён.',
        protocol: 'Сервер вернул некорректный ответ.',
        session_changed: 'Сеанс пользователя изменился. Обновите данные.',
        scope_mismatch: 'Область данных в ответе не соответствует запросу.'
    };

    function ApiError(kind, status) {
        this.name = 'DashboardApiError';
        this.kind = Object.prototype.hasOwnProperty.call(MESSAGES, kind) ? kind : 'protocol';
        this.status = Number.isInteger(status) && status >= 0 && status <= 599 ? status : 0;
        this.message = MESSAGES[this.kind];
        if (Error.captureStackTrace) Error.captureStackTrace(this, ApiError);
    }
    ApiError.prototype = Object.create(Error.prototype);
    ApiError.prototype.constructor = ApiError;

    function isObject(value) {
        return value !== null && typeof value === 'object' && !Array.isArray(value);
    }

    function requireShape(valid) {
        if (!valid) throw new ApiError('protocol', 200);
    }

    function userId(value) {
        if (!((typeof value === 'string' && /^[0-9]+$/.test(value) && value.trim() === value) ||
                typeof value === 'number')) {
            throw new RangeError('Требуется положительный целочисленный ID пользователя.');
        }
        var id = Number(value);
        if (!Number.isInteger(id) || id < 1 || id > 2147483647) {
            throw new RangeError('ID пользователя должен быть в пределах от 1 до 2147483647.');
        }
        return id;
    }

    function daysInMonth(year, month) {
        var date = new Date(0);
        date.setUTCFullYear(year, month, 0);
        return date.getUTCDate();
    }

    function parseInstant(value) {
        var match = typeof value === 'string' && /^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?([Zz]|([+-])(\d{2}):(\d{2}))$/.exec(value);
        if (!match || match[0] !== value) throw new RangeError('Требуется дата RFC 3339 с часовым поясом.');
        var year = Number(match[1]), month = Number(match[2]), day = Number(match[3]);
        var hour = Number(match[4]), minute = Number(match[5]), second = Number(match[6]);
        var fraction = ((match[7] || '') + '000000').slice(0, 6);
        var offsetHour = Number(match[10] || 0), offsetMinute = Number(match[11] || 0);
        if (year < 1 || month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month) ||
                hour > 23 || minute > 59 || second > 59 || offsetHour > 23 || offsetMinute > 59) {
            throw new RangeError('Укажите существующую дату и корректный часовой пояс.');
        }
        var date = new Date(0);
        date.setUTCFullYear(year, month - 1, day);
        date.setUTCHours(hour, minute, second, Number(fraction.slice(0, 3)));
        var offset = (offsetHour * 60 + offsetMinute) * (match[9] === '-' ? -1 : 1);
        date = new Date(date.getTime() - offset * 60000);
        if (date.getUTCFullYear() < 1 || date.getUTCFullYear() > 9999) {
            throw new RangeError('Дата выходит за допустимые границы UTC.');
        }
        var micro = Number(fraction.slice(3));
        var iso = date.toISOString();
        // Keep sub-millisecond precision without exceeding JS safe integer timestamps.
        if (micro) iso = iso.slice(0, -1) + fraction.slice(3) + 'Z';
        return { iso: iso, time: date.getTime(), micro: micro };
    }

    function compare(left, right) {
        return left.time - right.time || left.micro - right.micro;
    }

    function nextMonth(instant) {
        var date = new Date(instant.time), day = date.getUTCDate();
        date.setUTCDate(1);
        date.setUTCMonth(date.getUTCMonth() + 1);
        if (date.getUTCFullYear() > 9999) return parseInstant('9999-12-31T23:59:59.999999Z');
        date.setUTCDate(Math.min(day, daysInMonth(date.getUTCFullYear(), date.getUTCMonth() + 1)));
        return { time: date.getTime(), micro: instant.micro };
    }

    function validateRange(query, now) {
        if (!isObject(query)) throw new RangeError('Укажите параметры периода.');
        if (now === undefined) now = new Date();
        if (!(now instanceof Date) || !isFinite(now.getTime()) || now.getTime() < MIN_TIME ||
                now.getUTCFullYear() > 9999) {
            throw new RangeError('Текущее время должно быть корректной датой не ранее 1900 года.');
        }
        var start = parseInstant(query.startAt);
        var clock = { time: now.getTime(), micro: 0 };
        var end = query.endAt === null || query.endAt === undefined ? null : parseInstant(query.endAt);
        var effectiveEnd = end || clock;
        if (start.time < MIN_TIME || (end && end.time < MIN_TIME)) {
            throw new RangeError('Период не может начинаться ранее 1900 года UTC.');
        }
        if (compare(start, clock) > 0 || compare(effectiveEnd, clock) > 0) {
            throw new RangeError('Начало и конец периода не могут быть в будущем.');
        }
        if (compare(effectiveEnd, start) < 0) {
            throw new RangeError('Конец периода не может быть раньше начала.');
        }
        if (compare(effectiveEnd, nextMonth(start)) > 0) {
            throw new RangeError('Период не может превышать один календарный месяц.');
        }
        // Demo IDs are allowed here; only the real transport validates owner IDs.
        return { startAt: start.iso, endAt: end ? end.iso : null,
            userId: query.userId === undefined ? null : query.userId };
    }

    function dateValue(value, nullable) {
        if (nullable && value === null) return null;
        try { return parseInstant(value).iso; }
        catch (error) { throw new ApiError('protocol', 200); }
    }

    function count(value, nullable) {
        requireShape((nullable && value === null) || (Number.isSafeInteger(value) && value >= 0));
        return value;
    }

    function mapMetrics(raw) {
        requireShape(isObject(raw));
        var result = {};
        METRICS.forEach(function (field) { result[field[1]] = count(raw[field[0]], true); });
        return result;
    }

    function mapScope(raw) {
        requireShape(isObject(raw) && (raw.mode === 'all' || raw.mode === 'user') &&
            typeof raw.label === 'string' && raw.label.length > 0 &&
            ((raw.mode === 'all') === (raw.user_id === null)));
        var id = null;
        if (raw.mode === 'user') {
            try { id = userId(raw.user_id); }
            catch (error) { throw new ApiError('protocol', 200); }
        }
        return { userId: id, mode: raw.mode, label: raw.label };
    }

    function mapStatuses(raw, names, nullable) {
        requireShape(Array.isArray(raw) && raw.length === names.length);
        var seen = [];
        return raw.map(function (item) {
            requireShape(isObject(item));
            var definition = names.filter(function (entry) { return entry[0] === item.status; })[0];
            requireShape(Boolean(definition) && seen.indexOf(item.status) === -1);
            seen.push(item.status);
            return { status: item.status, label: definition[1], value: count(item.value, nullable) };
        });
    }

    function mapCoverage(raw) {
        // "recorded" means countable retained events, not confirmed complete history.
        // Keep the compatibility `from` field; the UI must not infer readiness from it.
        var states = ['recorded', 'partial', 'unavailable'];
        requireShape(isObject(raw) && states.indexOf(raw.current_state) !== -1 &&
            states.indexOf(raw.previous_state) !== -1);
        function reason(value) {
            requireShape(value === undefined || value === null || typeof value === 'string');
            // The UI translates known reason codes and uses a static fallback for unknown ones.
            return value === undefined ? null : value;
        }
        return { from: dateValue(raw.from, true), currentState: raw.current_state,
            previousState: raw.previous_state, currentReason: reason(raw.current_reason),
            previousReason: reason(raw.previous_reason) };
    }

    function mapSummary(raw) {
        requireShape(isObject(raw) && isObject(raw.comparison) && isObject(raw.delivery) &&
            isObject(raw.message_cohort) && isObject(raw.coverage) &&
            (raw.granularity === 'hour' || raw.granularity === 'day') &&
            Array.isArray(raw.trend) && raw.trend.length <= 32);
        var scope = mapScope(raw.scope);
        var delivery = { delivered: count(raw.delivery.delivered), terminal: count(raw.delivery.terminal),
            rate: raw.delivery.rate };
        requireShape(delivery.delivered <= delivery.terminal &&
            ((delivery.terminal === 0) === (delivery.rate === null)) &&
            (delivery.rate === null || (typeof delivery.rate === 'number' &&
                isFinite(delivery.rate) && delivery.rate >= 0 && delivery.rate <= 100)));
        var trend = raw.trend.map(function (point) {
            var result = mapMetrics(point);
            result.key = dateValue(point.key);
            result.fromAt = dateValue(point.from_at);
            result.toAt = dateValue(point.to_at);
            return result;
        });
        var singleDate = trend.every(function (point) { return point.key.slice(0, 10) === trend[0].key.slice(0, 10); });
        trend.forEach(function (point) {
            var date = point.key.slice(8, 10) + '.' + point.key.slice(5, 7);
            point.label = raw.granularity === 'day' ? date :
                (singleDate ? '' : date + ' ') + point.key.slice(11, 16);
        });
        return {
            startAt: dateValue(raw.start_at), endAt: dateValue(raw.end_at, true),
            effectiveEndAt: dateValue(raw.effective_end_at), generatedAt: dateValue(raw.generated_at),
            granularity: raw.granularity, scope: scope, scopeLabel: scope.label,
            totals: mapMetrics(raw.totals), previous: mapMetrics(raw.previous),
            comparison: { startAt: dateValue(raw.comparison.start_at), endAt: dateValue(raw.comparison.end_at) },
            trend: trend, statuses: mapStatuses(raw.statuses, MESSAGE_STATUSES, false),
            sessionStatuses: mapStatuses(raw.session_statuses, SESSION_STATUSES, true), delivery: delivery,
            messageCohort: { total: count(raw.message_cohort.total), created: count(raw.message_cohort.created),
                waiting: count(raw.message_cohort.waiting), unknownStatus: count(raw.message_cohort.unknown_status) },
            coverage: { lifecycle: mapCoverage(raw.coverage.lifecycle), messageEvents: mapCoverage(raw.coverage.message_events),
                accountErrors: mapCoverage(raw.coverage.account_errors), sessionErrors: mapCoverage(raw.coverage.session_errors) }
        };
    }

    function mapLive(raw) {
        requireShape(isObject(raw));
        var scope = mapScope(raw.scope);
        var result = { asOf: dateValue(raw.as_of), scope: scope, scopeLabel: scope.label,
            available: count(raw.available), active: count(raw.active), paused: count(raw.paused),
            banned: count(raw.banned), total: count(raw.total), other: count(raw.other) };
        requireShape(result.total === result.available + result.active + result.paused + result.banned + result.other);
        return result;
    }

    function mapUsers(raw) {
        requireShape(Array.isArray(raw));
        return raw.map(function (item) {
            requireShape(isObject(item) && typeof item.text === 'string');
            var id;
            try { id = userId(item.value); }
            catch (error) { throw new ApiError('protocol', 200); }
            return { id: String(id), name: item.text };
        });
    }

    function readAuth(getToken) {
        try {
            var token = getToken();
            if (!isObject(token) || !isObject(token.user) ||
                    typeof token.access_token !== 'string' || !/^[A-Za-z0-9._~+\/-]+=*$/.test(token.access_token) ||
                    token.access_token.trim() !== token.access_token ||
                    typeof token.token_type !== 'string' || token.token_type.toLowerCase() !== 'bearer' ||
                    typeof token.user.is_superuser !== 'boolean' || token.user.is_active === false) {
                throw new ApiError('auth', 0);
            }
            var id = userId(token.user.id);
            return { userId: id, isAdmin: token.user.is_superuser,
                authorization: token.token_type + ' ' + token.access_token,
                fingerprint: JSON.stringify([token.access_token, id, token.user.is_superuser]) };
        } catch (error) { throw new ApiError('auth', 0); }
    }

    function statusOf(xhr) {
        return xhr && Number.isInteger(xhr.status) && xhr.status >= 0 && xhr.status <= 599 ? xhr.status : 0;
    }

    function failureKind(xhr, textStatus) {
        var status = statusOf(xhr);
        var detail = xhr && isObject(xhr.responseJSON) ? xhr.responseJSON.detail : null;
        if (textStatus === 'timeout') return 'timeout';
        if (status === 401 || (status === 403 && detail === 'Could not validate credentials') ||
                (status === 400 && detail === 'Inactive user')) return 'auth';
        if (status === 403) return 'forbidden';
        if (status === 404) return 'not_found';
        if (status === 422) return 'validation';
        if (status >= 500) return 'unavailable';
        return status === 0 ? 'network' : 'protocol';
    }

    function create(options) {
        options = options || {};
        var baseUrl = options.baseUrl === undefined ? '' : options.baseUrl;
        if (typeof baseUrl !== 'string' || /[?#]/.test(baseUrl)) {
            throw new TypeError('Укажите корректный базовый адрес API.');
        }
        baseUrl = baseUrl.replace(/\/+$/, '');
        var getToken = options.getToken;
        var ajax = options.ajax || function (settings) { return window.jQuery.ajax(settings); };

        function request(kind, query) {
            var xhr, auth, settled = false, abortIntent = false, resolvePromise, rejectPromise;
            var promise = new Promise(function (resolve, reject) { resolvePromise = resolve; rejectPromise = reject; });
            function finish(error, value) {
                if (settled) return;
                settled = true;
                if (error) rejectPromise(error);
                else resolvePromise(value);
            }
            function current(status, textStatus) {
                if (settled) return false;
                if (abortIntent || textStatus === 'abort' || textStatus === 'canceled') {
                    finish(new ApiError('aborted', status));
                    return false;
                }
                var same = false;
                try { same = readAuth(getToken).fingerprint === auth.fingerprint; }
                catch (error) { same = false; }
                if (!same) finish(new ApiError('session_changed', status));
                return same;
            }
            function abort() {
                if (settled) return;
                abortIntent = true;
                try { if (xhr) xhr.abort(); }
                catch (error) { finish(new ApiError('aborted', statusOf(xhr))); }
                finish(new ApiError('aborted', statusOf(xhr)));
            }
            var handle = { promise: promise, abort: abort };
            var data = {}, selected = null;
            try {
                auth = readAuth(getToken);
                if (kind !== 'users') {
                    if (query === undefined) query = {};
                    if (!isObject(query)) throw new RangeError('Укажите параметры запроса.');
                    if (kind === 'summary') {
                        query = validateRange(query);
                        data.start_at = query.startAt;
                        if (query.endAt !== null) data.end_at = query.endAt;
                    }
                    if (query.userId !== null && query.userId !== undefined) {
                        selected = userId(query.userId);
                        data.user_id = selected;
                    }
                }
            } catch (error) {
                finish(new ApiError(error instanceof RangeError ? 'validation' : 'auth', 0));
                return handle;
            }
            var expectedId = auth.isAdmin ? selected : auth.userId;
            var path = kind === 'users' ? '/api/v1/options/user' : '/api/v1/stats/' + kind;
            var mapper = kind === 'users' ? mapUsers : (kind === 'summary' ? mapSummary : mapLive);
            try {
                xhr = ajax({ url: baseUrl + path, type: 'GET', dataType: 'json', timeout: 20000,
                    global: false, headers: { Accept: 'application/json', Authorization: auth.authorization }, data: data });
                if (!xhr || typeof xhr.done !== 'function' || typeof xhr.fail !== 'function' || typeof xhr.abort !== 'function') {
                    if (current(statusOf(xhr))) finish(new ApiError('protocol', statusOf(xhr)));
                    return handle;
                }
                xhr.done(function (raw, textStatus, response) {
                    var status = statusOf(response || xhr);
                    if (!current(status, textStatus)) return;
                    try {
                        var value = mapper(raw);
                        var matches = kind === 'users' ? auth.isAdmin || value.every(function (user) {
                            return user.id === String(auth.userId);
                        }) : value.scope.userId === expectedId && value.scope.mode === (expectedId === null ? 'all' : 'user');
                        if (!matches) throw new ApiError('scope_mismatch', status);
                        if (kind === 'summary' && (value.startAt !== data.start_at ||
                                value.endAt !== (data.end_at || null) ||
                                (value.endAt !== null && value.effectiveEndAt !== value.endAt))) {
                            throw new ApiError('protocol', status);
                        }
                        finish(null, value);
                    } catch (error) {
                        finish(new ApiError(error instanceof ApiError ? error.kind : 'protocol', status));
                    }
                });
                xhr.fail(function (response, textStatus) {
                    var status = statusOf(response);
                    if (current(status, textStatus)) finish(new ApiError(failureKind(response, textStatus), status));
                });
            } catch (error) {
                if (current(statusOf(xhr))) finish(new ApiError('network', statusOf(xhr)));
            }
            return handle;
        }
        return { summary: function (query) { return request('summary', query); },
            live: function (query) { return request('live', query); },
            users: function () { return request('users'); } };
    }

    var api = { create: create, validateRange: validateRange, mapSummary: mapSummary,
        mapLive: mapLive, mapUsers: mapUsers, ApiError: ApiError };
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (window) window.DashboardApi = api;
}(typeof window === 'undefined' ? null : window));
