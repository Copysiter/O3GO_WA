(function (window) {
    'use strict';

    // Demo scoping is not a substitute for server-side authorization.
    var HOUR = 60 * 60 * 1000;
    var DAY = 24 * HOUR;
    var MIN_TIME = Date.parse('1900-01-01T00:00:00.000Z');
    var FIELDS = [
        'opened', 'finished', 'sessionBans', 'accountBans', 'sent',
        'delivered', 'undelivered', 'failed', 'accountErrors', 'sessionErrors',
        'autoFinished', 'messageCreated'
    ];
    var STATUS_NAMES = [
        ['sent', 'Отправлены, ожидают результата'], ['delivered', 'Доставлены'],
        ['undelivered', 'Не доставлены'], ['failed', 'Ошибка отправки']
    ];

    function createUsers(currentUser) {
        if (!currentUser || typeof currentUser !== 'object' ||
                Array.isArray(currentUser)) {
            throw new TypeError('Требуется текущий пользователь.');
        }
        var id = currentUser.id;
        if ((typeof id !== 'string' || !id.trim()) &&
                (typeof id !== 'number' || !Number.isSafeInteger(id))) {
            throw new TypeError('Некорректный ID текущего пользователя.');
        }
        if (typeof currentUser.name !== 'string' || !currentUser.name.trim() ||
                typeof currentUser.is_superuser !== 'boolean') {
            throw new TypeError('Требуются имя и булева роль пользователя.');
        }
        var users = [{ id: String(id), name: currentUser.name }];
        if (currentUser.is_superuser) {
            var demos = [
                { id: 'demo-alpha', name: 'Команда Альфа (демо)' },
                { id: 'demo-beta', name: 'Команда Бета (демо)' },
                { id: 'demo-gamma', name: 'Команда Гамма (демо)' }
            ];
            demos.forEach(function (user) {
                if (user.id === String(id)) {
                    throw new RangeError('ID администратора занят демо-пользователем.');
                }
                users.push(user);
            });
        }
        return users;
    }

    function parseInstant(value) {
        if (typeof value !== 'string' ||
                !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value)) {
            throw new RangeError('Дата должна иметь формат YYYY-MM-DDTHH:mm:ss.sssZ.');
        }
        var time = Date.parse(value);
        if (!isFinite(time) || time < MIN_TIME || new Date(time).toISOString() !== value) {
            throw new RangeError('Требуется существующая дата не ранее 1900 года.');
        }
        return time;
    }

    function addMonth(startAt) {
        var date = new Date(parseInstant(startAt));
        var day = date.getUTCDate();
        date.setUTCDate(1);
        date.setUTCMonth(date.getUTCMonth() + 1);
        var lastDay = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0))
            .getUTCDate();
        date.setUTCDate(Math.min(day, lastDay));
        var result = date.toISOString();
        parseInstant(result);
        return result;
    }

    function hash(value) {
        var result = 2166136261;
        for (var i = 0; i < value.length; i += 1) {
            result = Math.imul(result ^ value.charCodeAt(i), 16777619);
        }
        return result >>> 0;
    }

    function metrics(value) {
        var result = {};
        FIELDS.forEach(function (field) { result[field] = value; });
        return result;
    }

    function add(target, source) {
        FIELDS.forEach(function (field) { target[field] += source[field]; });
    }

    function countEvents(total, from, to, every) {
        // Subsets share every nth parent event, even when an hour is clipped.
        every = every || 1;
        return Math.floor(Math.floor(total * to / HOUR) / every) -
            Math.floor(Math.floor(total * from / HOUR) / every);
    }

    function hourCounts(userId, date, hour, from, to) {
        var seed = hash(JSON.stringify([userId, date, hour]));
        var counts = metrics(0);
        var opened = 4 + seed % 13;
        var finished = Math.floor(opened * 0.8);
        var bans = seed % 4;
        counts.opened = countEvents(opened, from, to);
        counts.finished = countEvents(finished, from, to);
        counts.sessionBans = countEvents(bans, from, to);
        counts.accountBans = countEvents(bans, from, to, 2);
        counts.autoFinished = countEvents(finished, from, to, 3);

        var created = countEvents(5 + seed % 12, from, to);
        var waiting = countEvents(3 + (seed >>> 4) % 10, from, to);
        var pending = countEvents(6 + (seed >>> 8) % 17, from, to);
        counts.delivered = countEvents(50 + (seed >>> 12) % 91, from, to);
        counts.undelivered = countEvents(2 + (seed >>> 20) % 9, from, to);
        counts.failed = countEvents(1 + (seed >>> 24) % 5, from, to);
        // Confirmed sends include pending SENT, DELIVERED and UNDELIVERED.
        counts.sent = pending + counts.delivered + counts.undelivered;
        counts.messageCreated = created + waiting + counts.sent + counts.failed;

        for (var index = 0; index < seed % 3; index += 1) {
            var errorSeed = hash(JSON.stringify([userId, date, hour, index]) + ':error');
            var at = 1 + errorSeed % (HOUR - 1);
            if (from <= at && at < to) {
                counts[errorSeed % 2 === 0 ? 'accountErrors' : 'sessionErrors'] += 1;
            }
        }
        return counts;
    }

    function rangeCounts(start, end, users) {
        var totals = metrics(0);
        if (start === end) return totals;
        // Numeric bounds also allow the comparison range to precede 1900.
        for (var time = Math.floor(start / HOUR) * HOUR; time < end; time += HOUR) {
            var date = new Date(time);
            var from = Math.max(start, time) - time;
            var to = Math.min(end, time + HOUR) - time;
            users.forEach(function (user) {
                add(totals, hourCounts(user.id, date.toISOString().slice(0, 10),
                    date.getUTCHours(), from, to));
            });
        }
        return totals;
    }

    function liveSnapshot(users, now) {
        // Live state depends on the current UTC hour, not the selected report date.
        var live = { available: 0, active: 0, paused: 0, banned: 0 };
        users.forEach(function (user) {
            var seed = hash(JSON.stringify([user.id, now.toISOString().slice(0, 13), 'live']));
            live.available += 50 + seed % 81;
            live.active += 10 + (seed >>> 8) % 31;
            live.paused += 2 + (seed >>> 16) % 10;
            live.banned += 1 + (seed >>> 24) % 15;
        });
        return live;
    }

    function resolveScope(options) {
        if (!options || typeof options !== 'object' || Array.isArray(options)) {
            throw new TypeError('Требуются параметры прототипа.');
        }
        var now = options.now;
        if (!(now instanceof Date) || !isFinite(now.getTime())) {
            throw new RangeError('now должен быть корректным объектом Date.');
        }
        if (now.getTime() < MIN_TIME) {
            throw new RangeError('now должен быть не ранее 1900 года.');
        }
        var users = createUsers(options.currentUser);
        if (options.userId !== null && typeof options.userId !== 'string') {
            throw new RangeError('userId должен быть строкой или null.');
        }
        var selected = options.userId === null ? users.slice() : users.filter(function (user) {
            return user.id === options.userId;
        });
        if (!selected.length) throw new RangeError('Пользователь недоступен в этой области.');
        return { users: users, selected: selected };
    }

    function live(options) {
        var scope = resolveScope(options);
        return liveSnapshot(scope.selected, options.now);
    }

    function build(options) {
        var scope = resolveScope(options);
        var start = parseInstant(options.startAt);
        var endAt = options.endAt === undefined ? null : options.endAt;
        var end = endAt === null ? options.now.getTime() : parseInstant(endAt);
        if (start > options.now.getTime() || end > options.now.getTime()) {
            throw new RangeError('Начало и конец диапазона не могут быть позднее now.');
        }
        if (end < start) throw new RangeError('Конец диапазона не может быть раньше начала.');
        if (end > parseInstant(addMonth(options.startAt))) {
            throw new RangeError('Диапазон не может превышать один календарный месяц.');
        }

        var duration = end - start;
        var step = duration <= DAY ? HOUR : DAY;
        var totals = metrics(0);
        var trend = [];
        if (start < end) {
            for (var bucket = Math.floor(start / step) * step; bucket < end; bucket += step) {
                var key = new Date(bucket).toISOString();
                var point = Object.assign({
                    key: key,
                    label: step === HOUR ? key.slice(11, 16) : key.slice(8, 10) + '.' + key.slice(5, 7)
                }, rangeCounts(Math.max(start, bucket), Math.min(end, bucket + step), scope.selected));
                trend.push(point);
                add(totals, point);
            }
        }
        var statusValues = [totals.sent - totals.delivered - totals.undelivered,
            totals.delivered, totals.undelivered, totals.failed];
        var terminal = totals.delivered + totals.undelivered + totals.failed;
        return {
            users: scope.users,
            scopeLabel: scope.selected.length === 1 ? scope.selected[0].name : 'Все пользователи',
            startAt: options.startAt,
            endAt: endAt,
            effectiveEndAt: new Date(end).toISOString(),
            granularity: step === HOUR ? 'hour' : 'day',
            totals: totals,
            previous: rangeCounts(start - duration, start, scope.selected),
            comparison: { startAt: new Date(start - duration).toISOString(), endAt: options.startAt },
            trend: trend,
            statuses: STATUS_NAMES.map(function (item, index) {
                return { status: item[0], label: item[1], value: statusValues[index] };
            }),
            sessionStatuses: [
                { status: 'opened', label: 'Открыто', value: totals.opened },
                { status: 'finished', label: 'Завершено', value: totals.finished },
                { status: 'banned', label: 'Забанено', value: totals.sessionBans }
            ],
            delivery: {
                terminal: terminal, delivered: totals.delivered,
                rate: terminal ? totals.delivered / terminal * 100 : null
            },
            live: liveSnapshot(scope.selected, options.now)
        };
    }

    var api = { createUsers: createUsers, build: build, addMonth: addMonth, live: live };
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (window) window.DashboardMock = api;
}(typeof window === 'undefined' ? null : window));
