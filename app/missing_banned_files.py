"""Read-only exact archive existence audit for accounts with BANNED status.

    docker compose exec api python /app/missing_banned_files.py --details
    python -m app.missing_banned_files --upload-dir /path/to/archives

Counts account rows, not unique files. NULL/empty file_name is reported
separately. No prefix matching, archive content checks or database writes.
The scan is live, not an atomic database/filesystem snapshot.
"""

from __future__ import annotations

import argparse
import asyncio
import calendar
from collections import Counter
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.account_files import account_file_exists

DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parent / "upload" / "wa"
BATCH_SIZE = 1000


class ArchiveRow(NamedTuple):
    id: int
    file_name: str | None
    attempts: int | None = None
    updated_at: datetime | None = None


@dataclass
class Summary:
    checked: int = 0
    present: int = 0
    missing: int = 0
    empty: int = 0
    as_of: datetime | None = field(default=None, compare=False)
    distribution: Counter = field(default_factory=Counter, compare=False)


AGE_LABELS = {
    "recent": "Младше месяца",
    "middle": "От 1 до 3 месяцев",
    "old": "Старше 3 месяцев",
    "future": "Дата в будущем",
    "unknown": "Дата не задана/без часового пояса",
}


def months_before(value: datetime, months: int) -> datetime:
    index = value.year * 12 + value.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def age_group(updated_at: datetime | None, as_of: datetime) -> str:
    if updated_at is None or updated_at.utcoffset() is None:
        return "unknown"
    updated_at = updated_at.astimezone(timezone.utc)
    if updated_at > as_of:
        return "future"
    if updated_at > months_before(as_of, 1):
        return "recent"
    if updated_at >= months_before(as_of, 3):
        return "middle"
    return "old"


def ensure_directory(directory: Path) -> None:
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    # Fail on an unreadable storage root instead of reporting missing files.
    with os.scandir(directory) as entries:
        next(entries, None)


def check_batch(
    directory: Path, rows: list[ArchiveRow], *, as_of: datetime | None = None,
) -> tuple[Summary, list[dict]]:
    ensure_directory(directory)
    summary = Summary(as_of=as_of or datetime.now(timezone.utc))
    issues = []
    for row in rows:
        summary.checked += 1
        group = age_group(row.updated_at, summary.as_of)
        summary.distribution[row.attempts, group] += 1
        if not row.file_name:
            summary.empty += 1
            reason = "empty_file_name"
        elif account_file_exists(directory, row.file_name):
            summary.present += 1
            continue
        else:
            summary.missing += 1
            reason = "missing_file"
        issues.append({
            "account_id": row.id, "file_name": row.file_name, "reason": reason,
            "attempts": row.attempts,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "age_group": group,
        })
    return summary, issues


async def scan_accounts(db, directory: Path, *, details: bool = False) -> Summary:
    from sqlalchemy import select
    from app.models.account import Account, AccountStatus

    await asyncio.to_thread(ensure_directory, directory)
    summary = Summary(as_of=datetime.now(timezone.utc))
    before_id = None
    columns = Account.__table__.c
    while True:
        query = select(
            columns.id, columns.file_name, columns.attempts, columns.updated_at,
        ).where(
            columns.status == AccountStatus.BANNED,
        )
        if before_id is not None:
            query = query.where(columns.id < before_id)
        result = await db.execute(query.order_by(columns.id.desc()).limit(BATCH_SIZE))
        rows = [ArchiveRow(*row) for row in result.all()]
        if not rows:
            break
        batch, issues = await asyncio.to_thread(
            check_batch, directory, rows, as_of=summary.as_of,
        )
        summary.distribution.update(batch.distribution)
        summary.checked += batch.checked
        summary.present += batch.present
        summary.missing += batch.missing
        summary.empty += batch.empty
        if details:
            for issue in issues:
                print(json.dumps(issue, ensure_ascii=True), flush=True)
        before_id = rows[-1].id
        if len(rows) < BATCH_SIZE:
            break
    await asyncio.to_thread(ensure_directory, directory)
    return summary


async def run_scan(directory: Path, *, details: bool = False) -> Summary:
    from app.adapters.db.session import async_session, engine

    try:
        async with async_session() as db:
            return await scan_accounts(db, directory, details=details)
    finally:
        await engine.dispose()


def print_statistics(summary: Summary) -> None:
    print("\nСТАТИСТИКА attempts И updated_at")
    if summary.as_of is not None:
        print(f"Момент отсчёта (UTC): {summary.as_of.isoformat()}")
        print(f"Граница 1 месяца: {months_before(summary.as_of, 1).isoformat()}")
        print(f"Граница 3 месяцев: {months_before(summary.as_of, 3).isoformat()}")
    print("Используются календарные месяцы. Ровно 1 и ровно 3 месяца входят "
          "в группу 'От 1 до 3 месяцев'.")
    print("updated_at — последнее обновление записи, НЕ обязательно дата бана.")
    print("Учитываются все забаненные аккаунты независимо от наличия архива.")
    groups = list(AGE_LABELS)
    attempts_values = sorted(
        {attempts for attempts, _ in summary.distribution},
        key=lambda value: (value is None, value if value is not None else 0),
    )
    headers = ["attempts", "Всего", *AGE_LABELS.values()]
    rows = []
    for attempts in attempts_values:
        counts = [summary.distribution[attempts, group] for group in groups]
        rows.append(["NULL" if attempts is None else str(attempts),
                     sum(counts), *counts])
    totals = [sum(count for (_, age), count in summary.distribution.items()
                  if age == group) for group in groups]
    rows.append(["ИТОГО", sum(totals), *totals])
    formatted = [headers] + [
        [str(row[0]), *(f"{value:,}".replace(",", " ") for value in row[1:])]
        for row in rows
    ]
    widths = [max(len(row[i]) for row in formatted) for i in range(len(headers))]
    for index, row in enumerate(formatted):
        print(" | ".join(value.ljust(width) for value, width in zip(row, widths)))
        if index == 0:
            print("-+-".join("-" * width for width in widths))
    print("Будущие даты, отсутствующие даты и даты без часового пояса выделены "
          "отдельно и не входят в три возрастные группы.")


def print_report(summary: Summary) -> None:
    print("\nИТОГИ ПРОВЕРКИ ЗАБАНЕННЫХ АККАУНТОВ")
    for label, value in (
        ("Всего проверено аккаунтов со статусом BANNED (-1)", summary.checked),
        ("Точный файл существует на диске", summary.present),
        ("file_name указан, но файл отсутствует или путь недопустим", summary.missing),
        ("file_name пустой или NULL", summary.empty),
        ("Всего аккаунтов без подтверждённого файла", summary.missing + summary.empty),
    ):
        print(f"{label}: {value:,}".replace(",", " "))
    if not summary.checked:
        print("Забаненных аккаунтов не найдено; проверять нечего.")
    elif summary.missing or summary.empty:
        print("Ответ: НЕТ, не у всех забаненных аккаунтов есть указанный архив на диске.")
    else:
        print("Ответ: ДА, у всех проверенных забаненных аккаунтов указанный файл существует.")
    print_statistics(summary)
    print("\nСчитаются аккаунты, а не уникальные файлы: один архив может быть указан "
          "у нескольких аккаунтов.")
    print("Проверяется точный путь по file_name внутри каталога архивов, без подбора "
          "замен по префиксу. Регистр и пробелы не нормализуются.")
    print("Содержимое и целостность архивов не проверяются; существование файла "
          "не гарантирует его пригодность.")
    print("БД и файлы не изменялись. Проверка не является атомарным снимком.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Проверка архивов аккаунтов со статусом BANNED (-1).")
    parser.add_argument("--upload-dir", type=Path, default=DEFAULT_UPLOAD_DIR)
    parser.add_argument("--details", action="store_true", help="Вывести проблемные аккаунты в JSON.")
    args = parser.parse_args(argv)
    try:
        directory = args.upload_dir.expanduser().resolve()
        print(f"Каталог: {directory}")
        print("Проверка аккаунтов всех пользователей со статусом BANNED (-1)...", flush=True)
        if args.details:
            print("Проблемные аккаунты (JSON): empty_file_name — имя не задано; "
                  "missing_file — файл отсутствует или путь недопустим.")
        summary = asyncio.run(run_scan(directory, details=args.details))
        print_report(summary)
        return 0
    except KeyboardInterrupt:
        print("Проверка прервана. Итоговый отчёт не сформирован; "
              "выведенные детали могут быть неполными.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Ошибка проверки: {type(exc).__name__}. Проверьте подключение к БД "
              "и доступность каталога. Итоговый отчёт не сформирован; "
              "выведенные детали могут быть неполными.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
