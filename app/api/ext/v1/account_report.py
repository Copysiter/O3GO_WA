from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Iterable, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.deps as deps
import app.models as models


router = APIRouter()

UPLOAD_DIR = Path('upload/wa')
PROFILE_UPLOAD_DIR = Path('upload/wa/profile')


ACCOUNT_STATUS = {
    -1: "banned",
    0: "available",
    1: "active",
    2: "paused",
}
SESSION_STATUS = {
    -1: "banned",
    0: "finished",
    1: "active",
    2: "paused",
}
MESSAGE_STATUS = {
    -1: "waiting",
    0: "created",
    1: "sent",
    2: "delivered",
    3: "undelivered",
    4: "failed",
}


def _safe(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return escape(value.strftime("%Y-%m-%d %H:%M:%S"))
    return escape(str(value))


def _mask(value: Any) -> str:
    if not value:
        return "-"
    text = str(value)
    if len(text) <= 8:
        return "***"
    return escape(f"{text[:4]}...masked...{text[-4:]}")


def _status_badge(value: Any, mapping: dict[int, str]) -> str:
    if value is None:
        return '<span class="status-badge light">-</span>'
    raw = int(value)
    label = mapping.get(raw, 'unknown')
    cls = "dark" if raw > 0 else "mid" if raw == 0 else "outline"
    return f'<span class="status-badge {cls}">{escape(label)}</span>'


def _bool_badge(value: Any) -> str:
    label = "true" if bool(value) else "false"
    cls = "dark" if bool(value) else "light"
    return f'<span class="status-badge {cls}">{label}</span>'


def _columns(model: type) -> list[str]:
    return [column.name for column in model.__table__.columns]


def _status_map_for(model: type) -> dict[int, str] | None:
    if model is models.Account:
        return ACCOUNT_STATUS
    if model is models.Session:
        return SESSION_STATUS
    if model is models.Message:
        return MESSAGE_STATUS
    return None


def _cell(
    obj: Any,
    column: str,
    model: type,
    *,
    include_sensitive: bool,
) -> str:
    value = getattr(obj, column)

    if column == "status":
        mapping = _status_map_for(model)
        if mapping is not None:
            return _status_badge(value, mapping)

    if isinstance(value, bool):
        return _bool_badge(value)

    if (
        column in {"auth_code", "ext_api_key", "hashed_password", "push_id"}
        and not include_sensitive
    ):
        return f'<span class="mono muted">{_mask(value)}</span>'

    if column == "text":
        return f'<div class="message-text">{_safe(value)}</div>'

    if (
        column == "id"
        or column.endswith("_id")
        or column in {"uuid", "number", "device", "device_origin", "ext_id"}
        or isinstance(value, datetime)
    ):
        return f'<span class="mono">{_safe(value)}</span>'

    return _safe(value)


def _render_table(
    model: type,
    rows: Sequence[Any],
    *,
    include_sensitive: bool,
) -> str:
    columns = _columns(model)
    headers = "".join(f"<th>{escape(column)}</th>" for column in columns)

    if not rows:
        body = (
            f'<tr><td class="empty-cell" colspan="{len(columns)}">'
            "Нет данных"
            "</td></tr>"
        )
    else:
        body = "".join(
            "<tr>"
            + "".join(
                f"<td>{_cell(row, column, model, include_sensitive=include_sensitive)}</td>"
                for column in columns
            )
            + "</tr>"
            for row in rows
        )

    return f"""
        <div class="table-wrap">
            <table>
                <thead><tr>{headers}</tr></thead>
                <tbody>{body}</tbody>
            </table>
        </div>
    """


def _file_checks(account: models.Account) -> list[dict[str, Any]]:
    checks = [
        ("archive", "file_name", account.file_name, UPLOAD_DIR),
        (
            "profile",
            "profile_file_name",
            account.profile_file_name,
            PROFILE_UPLOAD_DIR,
        ),
    ]

    rows: list[dict[str, Any]] = []
    for kind, field, file_name, base_dir in checks:
        path = base_dir / file_name if file_name else None
        exists = bool(path and path.is_file())
        stat = path.stat() if exists and path else None
        rows.append({
            "kind": kind,
            "field": field,
            "file_name": file_name,
            "base_dir": str(base_dir),
            "path": str(path) if path else None,
            "exists": exists,
            "size_bytes": stat.st_size if stat else None,
            "modified_at": (
                datetime.fromtimestamp(stat.st_mtime) if stat else None
            ),
        })
    return rows


def _render_file_checks(rows: Sequence[dict[str, Any]]) -> str:
    headers = "".join(
        f"<th>{header}</th>" for header in [
            "kind", "db_field", "file_name", "base_dir",
            "path", "exists", "size_bytes", "modified_at"
        ]
    )
    body = "".join(
        "<tr>"
        f"<td>{_safe(row['kind'])}</td>"
        f"<td class=\"mono\">{_safe(row['field'])}</td>"
        f"<td class=\"mono\">{_safe(row['file_name'])}</td>"
        f"<td class=\"mono\">{_safe(row['base_dir'])}</td>"
        f"<td class=\"mono\">{_safe(row['path'])}</td>"
        f"<td>{_bool_badge(row['exists'])}</td>"
        f"<td class=\"mono\">{_safe(row['size_bytes'])}</td>"
        f"<td class=\"mono\">{_safe(row['modified_at'])}</td>"
        "</tr>"
        for row in rows
    )
    return f"""
        <div class="table-wrap">
            <table>
                <thead><tr>{headers}</tr></thead>
                <tbody>{body}</tbody>
            </table>
        </div>
    """


def _render_section(
    index: str,
    anchor: str,
    title: str,
    note: str,
    content: str,
    right_note: str = "",
) -> str:
    return f"""
        <section class="section" id="{escape(anchor)}">
            <div class="section-header">
                <div>
                    <div class="section-kicker">{escape(index)}</div>
                    <h2>{escape(title)}</h2>
                    <p>{escape(note)}</p>
                </div>
                <div class="section-note mono">{escape(right_note)}</div>
            </div>
            {content}
        </section>
    """


def _timeline_events(
    account: models.Account,
    sessions: Sequence[models.Session],
    messages: Sequence[models.Message],
) -> list[tuple[datetime, str, str]]:
    events: list[tuple[datetime, str, str]] = []

    if account.created_at:
        events.append((
            account.created_at,
            f"Создан account #{account.id}",
            f"Номер {account.number}, статус "
            f"{ACCOUNT_STATUS.get(int(account.status), 'unknown')}.",
        ))
    if account.updated_at and account.updated_at != account.created_at:
        events.append((
            account.updated_at,
            f"Обновлен account #{account.id}",
            f"Текущий статус {ACCOUNT_STATUS.get(int(account.status), 'unknown')}.",
        ))

    for session in sessions:
        if session.created_at:
            events.append((
                session.created_at,
                f"Создана session #{session.id}",
                f"ext_id={session.ext_id}, msg_count={session.msg_count}.",
            ))
        if session.updated_at and session.updated_at != session.created_at:
            events.append((
                session.updated_at,
                f"Обновлена session #{session.id}",
                f"Статус {SESSION_STATUS.get(int(session.status), 'unknown')}.",
            ))

    for message in messages:
        if message.created_at:
            events.append((
                message.created_at,
                f"Создано message #{message.id}",
                f"session_id={message.session_id}, получатель "
                f"{message.number}, статус "
                f"{MESSAGE_STATUS.get(int(message.status), 'unknown')}.",
            ))
        if message.updated_at:
            events.append((
                message.updated_at,
                f"Обновлено message #{message.id}",
                f"session_id={message.session_id}, получатель "
                f"{message.number}, статус "
                f"{MESSAGE_STATUS.get(int(message.status), 'unknown')}.",
            ))

    return sorted(events, key=lambda event: event[0], reverse=True)[:40]


def _render_timeline(events: Iterable[tuple[datetime, str, str]]) -> str:
    rendered = "".join(
        "<div class=\"event\">"
        f"<time>{_safe(ts)}</time>"
        "<div>"
        f"<strong>{escape(title)}</strong>"
        f"<span>{escape(description)}</span>"
        "</div>"
        "</div>"
        for ts, title, description in events
    )
    if not rendered:
        rendered = '<div class="event"><time>-</time><div>Нет событий</div></div>'
    return f'<div class="timeline">{rendered}</div>'


def _render_report(
    *,
    number: str,
    account: models.Account,
    owner: models.User | None,
    sessions: Sequence[models.Session],
    messages: Sequence[models.Message],
    androids: Sequence[models.Android],
    include_sensitive: bool,
) -> str:
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    owner_id = owner.id if owner else account.user_id
    owner_rows = [owner] if owner else []
    file_checks = _file_checks(account)
    has_linked_android = any(
        android.account_id == account.id for android in androids
    )
    android_nav = (
        '<a href="#devices"><b>06</b><span>Android</span></a>'
        if has_linked_android else ''
    )
    android_metric = (
        '<div class="metric"><span class="metric-label">android</span>'
        f'<strong>{len(androids)}</strong>'
        '<span>устройства аккаунта/владельца</span></div>'
        if has_linked_android else ''
    )
    android_section = (
        _render_section(
            '06 android',
            'devices',
            'Android-устройства',
            'Текущая привязка к аккаунту и устройства владельца аккаунта.',
            _render_table(
                models.Android,
                androids,
                include_sensitive=include_sensitive,
            ),
            f'{len(androids)} rows',
        )
        if has_linked_android else ''
    )

    overview = f"""
        <div class="summary-grid">
            <div class="summary-cell">
                <h3>Интерпретация</h3>
                <p>
                    Отчет строится вокруг одной строки <code>account</code>:
                    <code>account.id = {_safe(account.id)}</code>,
                    <code>account.number = {_safe(account.number)}</code>.
                </p>
                <p>
                    Сессии выбираются по <code>session.account_id</code>, сообщения по найденным
                    <code>session.id</code>, Android-устройства по текущей привязке к аккаунту и по владельцу.
                </p>
            </div>
            <div class="summary-cell">
                <h3>Карта запросов</h3>
                <div class="definition-list">
                    <div class="definition-row">
                        <span>Account</span>
                        <span>account.number = :number</span>
                    </div>
                    <div class="definition-row">
                        <span>Sessions</span>
                        <span>session.account_id = account.id</span>
                    </div>
                    <div class="definition-row">
                        <span>Messages</span>
                        <span>message.session_id in session ids</span>
                    </div>
                    <div class="definition-row">
                        <span>Android</span>
                        <span>android.account_id = account.id or android.user_id = account.user_id</span>
                    </div>
                </div>
            </div>
        </div>
    """

    return f"""<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Отчет по аккаунту {_safe(number)}</title>
    <style>
        :root {{
            --chrome-1: #6f7479;
            --chrome-2: #7f8489;
            --chrome-3: #90959a;
            --work: #b4b7ba;
            --panel: #c4c7ca;
            --panel-soft: #ced1d3;
            --table: #d2d4d6;
            --table-alt: #c9cccf;
            --table-head: #b9bdc1;
            --line: rgba(72, 79, 86, 0.34);
            --line-soft: rgba(72, 79, 86, 0.18);
            --text: #3b4249;
            --text-strong: #2f363d;
            --text-soft: #596168;
            --text-faint: #747b82;
            --sidebar-text: #d9dcde;
            --sidebar-soft: #b7bcc0;
            --sidebar-muted: #92999f;
            --mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            --sans: "Inter", "Segoe UI", Arial, sans-serif;
        }}

        * {{ box-sizing: border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{
            margin: 0;
            min-height: 100vh;
            background: var(--work);
            color: var(--text);
            font-family: var(--sans);
            font-size: 12px;
            line-height: 1.42;
        }}
        a {{ color: inherit; text-decoration: none; }}
        code, .mono {{ font-family: var(--mono); }}

        .app {{ min-height: 100vh; padding-left: 236px; }}
        .sidebar {{
            position: fixed;
            inset: 0 auto 0 0;
            width: 236px;
            background: linear-gradient(180deg, var(--chrome-1), #62676c);
            color: var(--sidebar-text);
        }}
        .sidebar-header {{ padding: 18px 18px 15px; background: rgba(62, 68, 74, 0.46); }}
        .product-label {{
            margin-bottom: 10px;
            color: var(--sidebar-soft);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}
        .sidebar-title {{ margin-bottom: 6px; color: #eceeef; font-size: 15px; font-weight: 700; }}
        .sidebar-number {{ color: var(--sidebar-text); font-family: var(--mono); font-size: 12px; }}
        .sidebar-meta {{ padding: 12px 18px; border-bottom: 1px solid rgba(230, 232, 234, 0.16); }}
        .meta-line {{ display: flex; justify-content: space-between; gap: 12px; padding: 5px 0; color: var(--sidebar-soft); }}
        .meta-line span:last-child {{ color: #e2e4e6; font-family: var(--mono); text-align: right; }}
        .nav {{ padding: 10px 0; }}
        .nav a {{
            display: grid;
            grid-template-columns: 30px 1fr;
            align-items: center;
            min-height: 32px;
            padding: 0 18px;
            color: var(--sidebar-text);
        }}
        .nav a:hover {{ background: rgba(54, 60, 66, 0.38); }}
        .nav b {{ color: var(--sidebar-muted); font-family: var(--mono); font-size: 10px; }}
        .nav span {{ font-size: 12px; }}

        .topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            min-height: 42px;
            padding: 0 20px;
            background: var(--chrome-3);
            color: #eef0f1;
        }}
        .topbar-title {{ font-size: 12px; font-weight: 700; }}
        .topbar-actions {{ display: flex; gap: 8px; color: #d7dadc; font-family: var(--mono); font-size: 11px; }}
        .content {{ padding: 20px 24px 32px; }}

        .report-header {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) 360px;
            gap: 18px;
            align-items: end;
            margin-bottom: 18px;
        }}
        h1, h2, h3, p {{ margin-top: 0; }}
        h1 {{
            margin-bottom: 8px;
            color: var(--text-strong);
            font-size: 24px;
            font-weight: 650;
            letter-spacing: -0.03em;
        }}
        .lead {{ max-width: 780px; margin-bottom: 0; color: var(--text-soft); }}
        .account-chip {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 12px;
            padding: 12px 14px;
            background: var(--panel);
            color: var(--text-soft);
        }}
        .account-chip strong {{ display: block; color: var(--text-strong); font-size: 13px; }}

        .status-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 78px;
            min-height: 22px;
            padding: 2px 8px;
            background: #777d83;
            color: #eff1f2;
            font-family: var(--mono);
            font-size: 10px;
            font-weight: 700;
            white-space: nowrap;
        }}
        .status-badge.mid {{ background: #969ba0; color: #eef0f1; }}
        .status-badge.light {{ background: #c0c3c6; color: var(--text-strong); }}
        .status-badge.outline {{
            background: transparent;
            box-shadow: inset 0 0 0 1px rgba(66, 72, 78, 0.5);
            color: var(--text-strong);
        }}

        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 1px;
            margin-bottom: 18px;
            background: var(--line-soft);
        }}
        .metric {{ min-height: 78px; padding: 12px 14px; background: var(--panel); }}
        .metric-label, .section-kicker, th {{ letter-spacing: 0.08em; text-transform: uppercase; }}
        .metric-label {{ display: block; margin-bottom: 8px; color: var(--text-faint); font-size: 9px; font-weight: 700; }}
        .metric strong {{ display: block; margin-bottom: 4px; color: var(--text-strong); font-size: 20px; line-height: 1; font-weight: 650; }}
        .metric span:last-child {{ color: var(--text-soft); }}

        .section {{ margin-bottom: 18px; }}
        .section-header {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 8px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--line);
        }}
        .section-kicker {{ margin-bottom: 3px; color: var(--text-faint); font-family: var(--mono); font-size: 9px; font-weight: 700; }}
        h2 {{ margin-bottom: 0; color: var(--text-strong); font-size: 15px; font-weight: 650; }}
        .section-header p {{ margin: 4px 0 0; color: var(--text-soft); }}
        .section-note {{ color: var(--text-faint); white-space: nowrap; }}

        .summary-grid {{ display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr); gap: 1px; background: var(--line-soft); }}
        .summary-cell {{ padding: 14px; background: var(--panel); }}
        .summary-cell h3 {{ margin-bottom: 8px; color: var(--text-strong); font-size: 12px; }}
        .summary-cell p {{ margin-bottom: 8px; color: var(--text-soft); }}
        .summary-cell p:last-child {{ margin-bottom: 0; }}
        .definition-list {{ display: grid; gap: 1px; background: var(--line-soft); }}
        .definition-row {{ display: grid; grid-template-columns: 132px minmax(0, 1fr); gap: 12px; padding: 8px 10px; background: var(--panel-soft); }}
        .definition-row span:first-child {{ color: var(--text-faint); }}
        .definition-row span:last-child {{ color: var(--text); font-family: var(--mono); font-size: 11px; word-break: break-word; }}

        .table-wrap {{ overflow-x: auto; background: var(--table); }}
        table {{ width: 100%; min-width: 980px; border-collapse: collapse; background: var(--table); }}
        th, td {{ padding: 8px 10px; border-right: 1px solid var(--line-soft); border-bottom: 1px solid var(--line-soft); text-align: left; vertical-align: top; }}
        th:last-child, td:last-child {{ border-right: 0; }}
        th {{ position: sticky; top: 0; z-index: 1; background: var(--table-head); color: var(--text-soft); font-size: 9px; font-weight: 750; white-space: nowrap; }}
        td {{ color: var(--text); font-size: 11px; }}
        tbody tr:nth-child(even) td {{ background: var(--table-alt); }}
        tbody tr:last-child td {{ border-bottom: 0; }}
        .muted {{ color: var(--text-faint); }}
        .message-text {{ max-width: 460px; white-space: pre-wrap; }}
        .empty-cell {{ color: var(--text-faint); font-style: italic; }}

        .timeline {{ display: grid; gap: 1px; background: var(--line-soft); }}
        .event {{ display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: 14px; padding: 10px 12px; background: var(--panel); }}
        .event time {{ color: var(--text-faint); font-family: var(--mono); font-size: 11px; }}
        .event strong {{ display: block; margin-bottom: 3px; color: var(--text-strong); font-size: 12px; }}
        .event span {{ color: var(--text-soft); }}
        .warning-box {{ padding: 14px; background: var(--panel); color: var(--text-soft); }}
        .warning-box strong {{ display: block; margin-bottom: 6px; color: var(--text-strong); }}

        @media (max-width: 1080px) {{
            .app {{ padding-left: 0; }}
            .sidebar {{ position: static; width: auto; }}
            .nav {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }}
            .report-header, .summary-grid {{ grid-template-columns: 1fr; }}
            .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        }}
        @media (max-width: 640px) {{
            .content {{ padding: 14px; }}
            .nav, .metrics {{ grid-template-columns: 1fr; }}
            .section-header, .event, .definition-row {{ display: block; }}
            .section-note {{ margin-top: 6px; white-space: normal; }}
        }}
    </style>
</head>
<body>
    <aside class="sidebar" aria-label="Навигация отчета">
        <div class="sidebar-header">
            <div class="product-label">Служебный отчет</div>
            <div class="sidebar-title">История аккаунта</div>
            <div class="sidebar-number">{_safe(number)}</div>
        </div>
        <div class="sidebar-meta">
            <div class="meta-line"><span>account.id</span><span>{_safe(account.id)}</span></div>
            <div class="meta-line"><span>статус</span><span>{_safe(ACCOUNT_STATUS.get(int(account.status), 'unknown'))}</span></div>
            <div class="meta-line"><span>дата</span><span>{_safe(generated_at[:10])}</span></div>
            <div class="meta-line"><span>режим</span><span>read only</span></div>
        </div>
        <nav class="nav">
            <a href="#overview"><b>00</b><span>Сводка</span></a>
            <a href="#account"><b>01</b><span>Аккаунт</span></a>
            <a href="#files"><b>02</b><span>Файлы</span></a>
            <a href="#owner"><b>03</b><span>Владелец</span></a>
            <a href="#sessions"><b>04</b><span>Сессии</span></a>
            <a href="#messages"><b>05</b><span>Сообщения</span></a>
            {android_nav}
            <a href="#timeline"><b>07</b><span>Хронология</span></a>
            <a href="#limits"><b>08</b><span>Ограничения</span></a>
        </nav>
    </aside>

    <main class="app">
        <div class="topbar">
            <div class="topbar-title">O3GO WA / Account report</div>
            <div class="topbar-actions"><span>HTML</span><span>UTC</span><span>{'full' if include_sensitive else 'masked'}</span></div>
        </div>
        <div class="content">
            <header class="report-header">
                <div>
                    <h1>Отчет по аккаунту {_safe(number)}</h1>
                    <p class="lead">
                        Нативный служебный экран для просмотра связанных данных по одному аккаунту:
                        сессии, сообщения, Android-устройства и владелец.
                    </p>
                </div>
                <div class="account-chip">
                    <div>
                        <strong>Account #{_safe(account.id)}</strong>
                        <span>number <code>{_safe(account.number)}</code>, user <code>{_safe(owner_id)}</code></span>
                    </div>
                </div>
            </header>

            <section class="metrics" aria-label="Ключевые параметры отчета">
                <div class="metric"><span class="metric-label">account</span><strong>#{_safe(account.id)}</strong><span>строка `account`</span></div>
                <div class="metric"><span class="metric-label">sessions</span><strong>{len(sessions)}</strong><span>по `account_id`</span></div>
                <div class="metric"><span class="metric-label">messages</span><strong>{len(messages)}</strong><span>по `session_id`</span></div>
                {android_metric}
                <div class="metric"><span class="metric-label">owner</span><strong>#{_safe(owner_id)}</strong><span>владелец аккаунта</span></div>
            </section>

            {_render_section('00 summary', 'overview', 'Сводка', 'Как endpoint собирает отчет по номеру аккаунта.', overview, generated_at)}
            {_render_section('01 account', 'account', 'Аккаунт', f'Одна строка таблицы account для номера {number}.', _render_table(models.Account, [account], include_sensitive=include_sensitive), f'account.id = {account.id}')}
            {_render_section('02 files', 'files', 'Файлы', 'Проверка file_name и profile_file_name на диске: upload/wa и upload/wa/profile.', _render_file_checks(file_checks), 'filesystem check')}
            {_render_section('03 owner', 'owner', 'Владелец', 'Таблица user, связь через account.user_id.', _render_table(models.User, owner_rows, include_sensitive=include_sensitive), f'user.id = {owner_id}')}
            {_render_section('04 sessions', 'sessions', 'Сессии', 'Все строки session, где account_id равен ID аккаунта.', _render_table(models.Session, sessions, include_sensitive=include_sensitive), f'{len(sessions)} rows')}
            {_render_section('05 messages', 'messages', 'Сообщения', 'Все строки message, связанные с найденными сессиями аккаунта. В таблице есть session_id.', _render_table(models.Message, messages, include_sensitive=include_sensitive), f'{len(messages)} rows')}
            {android_section}
            {_render_section('07 timeline', 'timeline', 'Хронология', 'created_at сообщения отображается как создание, updated_at как отдельное обновление.', _render_timeline(_timeline_events(account, sessions, messages)), 'latest 40')}
            {_render_section('08 limits', 'limits', 'Ограничения данных', 'Что отчет не сможет восстановить из текущей схемы.', '<div class="warning-box"><strong>В моделях нет audit/history-таблицы.</strong>Отчет показывает текущие строки и связанные записи, но не восстанавливает старые значения полей после обновлений, прошлые Android-привязки после account_id = NULL, а также удаленные строки.</div>')}
        </div>
    </main>
</body>
</html>"""


@router.get("/report", response_class=HTMLResponse)
async def account_history_report(
    *,
    db: AsyncSession = Depends(deps.get_db),
    number: str = Query(..., min_length=1, description="Номер аккаунта"),
    include_sensitive: bool = Query(
        False,
        description=(
            "Показать чувствительные поля: auth_code, ext_api_key, "
            "hashed_password, push_id"
        ),
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> HTMLResponse:
    number = number.strip()
    if not number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'number' must not be empty",
        )

    if include_sensitive and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superuser can include sensitive fields",
        )

    conditions = [models.Account.number == number]
    if not user.is_superuser:
        conditions.append(models.Account.user_id == user.id)

    result = await db.execute(
        select(models.Account)
        .where(*conditions)
        .limit(2)
    )
    accounts = result.scalars().all()

    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with number={number} not found",
        )
    if len(accounts) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"More than one account with number={number} found",
        )

    account = accounts[0]
    owner = await db.get(models.User, account.user_id)

    sessions_result = await db.execute(
        select(models.Session)
        .where(models.Session.account_id == account.id)
        .order_by(models.Session.created_at.desc(), models.Session.id.desc())
    )
    sessions = sessions_result.scalars().all()
    session_ids = [session.id for session in sessions]

    if session_ids:
        messages_result = await db.execute(
            select(models.Message)
            .where(models.Message.session_id.in_(session_ids))
            .order_by(models.Message.created_at.desc(), models.Message.id.desc())
        )
        messages = messages_result.scalars().all()
    else:
        messages = []

    android_result = await db.execute(
        select(models.Android)
        .where(or_(
            models.Android.account_id == account.id,
            models.Android.user_id == account.user_id,
        ))
        .order_by(models.Android.id.desc())
    )
    androids = android_result.scalars().all()

    html = _render_report(
        number=number,
        account=account,
        owner=owner,
        sessions=sessions,
        messages=messages,
        androids=androids,
        include_sensitive=include_sensitive,
    )
    return HTMLResponse(content=html)
