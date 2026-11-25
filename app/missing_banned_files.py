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
import json
import os
import sys
from dataclasses import dataclass
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


@dataclass
class Summary:
    checked: int = 0
    present: int = 0
    missing: int = 0
    empty: int = 0


def ensure_directory(directory: Path) -> None:
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    # Fail on an unreadable storage root instead of reporting missing files.
    with os.scandir(directory) as entries:
        next(entries, None)


def check_batch(directory: Path, rows: list[ArchiveRow]) -> tuple[Summary, list[dict]]:
    ensure_directory(directory)
    summary = Summary()
    issues = []
    for row in rows:
        summary.checked += 1
        if not row.file_name:
            summary.empty += 1
            reason = "empty_file_name"
        elif account_file_exists(directory, row.file_name):
            summary.present += 1
            continue
        else:
            summary.missing += 1
            reason = "missing_file"
        issues.append({"account_id": row.id, "file_name": row.file_name, "reason": reason})
    return summary, issues


async def scan_accounts(db, directory: Path, *, details: bool = False) -> Summary:
    from sqlalchemy import select
    from app.models.account import Account, AccountStatus

    await asyncio.to_thread(ensure_directory, directory)
    summary = Summary()
    before_id = None
    columns = Account.__table__.c
    while True:
        query = select(columns.id, columns.file_name).where(
            columns.status == AccountStatus.BANNED,
        )
        if before_id is not None:
            query = query.where(columns.id < before_id)
        result = await db.execute(query.order_by(columns.id.desc()).limit(BATCH_SIZE))
        rows = [ArchiveRow(*row) for row in result.all()]
        if not rows:
            break
        batch, issues = await asyncio.to_thread(check_batch, directory, rows)
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
    print("Считаются аккаунты, а не уникальные файлы: один архив может быть указан "
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
