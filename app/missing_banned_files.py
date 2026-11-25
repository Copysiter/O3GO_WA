"""Audit BANNED accounts and optionally delete old rows and their archive files.

    docker compose exec api python /app/missing_banned_files.py --details
    python -m app.missing_banned_files --upload-dir /path/to/archives

Counts account rows, not unique files. NULL/empty file_name is reported
separately. Deletion requires interactive y confirmation. Only scanned rows
still BANNED and strictly older than three calendar months are deleted.
DB deletion commits before file cleanup; shared files are preserved. Profiles
are not removed. Pause writers and take a backup before confirming deletion.
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
    candidates: list[ArchiveRow] = field(default_factory=list, compare=False)


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
        if group == "old":
            summary.candidates.append(row)
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
        summary.candidates.extend(batch.candidates)
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


@dataclass
class DeletionSummary:
    requested: int = 0
    deleted: int = 0
    skipped: int = 0
    files_deleted: int = 0
    files_missing: int = 0
    files_shared: int = 0
    files_unsafe: int = 0
    file_errors: int = 0
    files_pending: int = 0
    empty_names: int = 0
    db_outcome: str = "not_started"


def confirm_deletion() -> bool:
    try:
        return input("Удалить забаненные аккаунты старше 3 месяцев? [y/N]: ").strip() == "y"
    except EOFError:
        return False


def unlink_archive(directory: Path, name: str) -> str:
    """Never follow symlinks or remove anything outside the selected storage."""
    ensure_directory(directory)
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        return "unsafe"
    path = directory / relative
    base = directory.resolve()
    if not path.resolve().is_relative_to(base):
        return "unsafe"
    current = directory
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return "unsafe"
    try:
        if not path.is_file():
            return "unsafe" if path.exists() else "missing"
        path.unlink()
    except FileNotFoundError:
        return "missing"
    return "deleted"


async def delete_candidates(db, directory: Path, scan: Summary, result: DeletionSummary) -> None:
    from sqlalchemy import delete, select, text
    from app.models.account import Account, AccountStatus

    if scan.as_of is None:
        raise ValueError("Missing scan timestamp")
    cutoff = months_before(scan.as_of, 3)
    table = Account.__table__
    columns = table.c
    names: set[str] = set()
    deleted_count = 0
    empty_names = 0
    await asyncio.to_thread(ensure_directory, directory)
    result.db_outcome = "transaction_started"
    async with db.begin():
        # Serialize account writers while verifying and deleting scanned rows.
        await db.execute(text('LOCK TABLE account IN SHARE ROW EXCLUSIVE MODE'))
        for offset in range(0, len(scan.candidates), BATCH_SIZE):
            batch = scan.candidates[offset:offset + BATCH_SIZE]
            originals = {row.id: row for row in batch}
            rows = (await db.execute(select(
                columns.id, columns.file_name, columns.updated_at,
            ).where(
                columns.id.in_(originals), columns.status == AccountStatus.BANNED,
                columns.updated_at < cutoff,
            ).with_for_update())).all()
            # Do not delete records changed since the operator's report.
            ids = [row.id for row in rows
                   if row.file_name == originals[row.id].file_name
                   and row.updated_at == originals[row.id].updated_at]
            if not ids:
                continue
            removed = (await db.execute(delete(table).where(
                columns.id.in_(ids), columns.status == AccountStatus.BANNED,
                columns.updated_at < cutoff,
            ).returning(columns.id, columns.file_name))).all()
            deleted_count += len(removed)
            for _, name in removed:
                if name:
                    names.add(name)
                else:
                    empty_names += 1
        result.db_outcome = "commit_unknown"
    # Only confirmed commit permits filesystem changes.
    result.db_outcome = "committed"
    result.deleted = deleted_count
    result.skipped = result.requested - deleted_count
    result.empty_names = empty_names
    result.files_pending = len(names)
    ordered_names = sorted(names)
    for offset in range(0, len(ordered_names), BATCH_SIZE):
        batch_names = ordered_names[offset:offset + BATCH_SIZE]
        async with db.begin():
            # Keep reference checks and unlink protected from account writers.
            await db.execute(text('LOCK TABLE account IN SHARE ROW EXCLUSIVE MODE'))
            referenced = set((await db.execute(select(columns.file_name).where(
                columns.file_name.in_(batch_names),
            ))).scalars().all())
            for name in batch_names:
                if name in referenced:
                    result.files_shared += 1
                else:
                    try:
                        outcome = await asyncio.to_thread(unlink_archive, directory, name)
                    except Exception as exc:
                        result.file_errors += 1
                        print(json.dumps({"file_name": name, "error_type": type(exc).__name__},
                                         ensure_ascii=True), flush=True)
                    else:
                        attr = "files_" + outcome
                        setattr(result, attr, getattr(result, attr) + 1)
                result.files_pending -= 1


async def run_deletion(directory: Path, scan: Summary, result: DeletionSummary) -> None:
    from app.adapters.db.session import async_session, engine

    try:
        async with async_session() as db:
            await delete_candidates(db, directory, scan, result)
    finally:
        await engine.dispose()


def print_deletion_report(result: DeletionSummary) -> None:
    print("\nИТОГИ УДАЛЕНИЯ")
    for label, value in (
        ("Кандидатов в исходном отчёте", result.requested),
        ("Удалено аккаунтов (commit подтверждён)", result.deleted),
        ("Пропущено после повторной проверки", result.skipped),
        ("Удалено уникальных файлов", result.files_deleted),
        ("Файлов уже нет на диске", result.files_missing),
        ("Файлов сохранено: есть ссылки оставшихся аккаунтов", result.files_shared),
        ("Небезопасных путей/необычных файлов пропущено", result.files_unsafe),
        ("Ошибок удаления файлов", result.file_errors),
        ("Файлов ещё не обработано", result.files_pending),
        ("Удалённых аккаунтов без file_name", result.empty_names),
    ):
        print(f"{label}: {value:,}".replace(",", " "))
    print(f"Состояние операции с БД: {result.db_outcome}")
    if result.db_outcome == "commit_unknown":
        print("Результат commit неизвестен. Проверьте БД; файлы не удалялись.")
    elif result.db_outcome != "committed":
        print("Успешное удаление записей не подтверждено; файлы не удалялись.")
    print("Профили не удаляются. Ошибки очистки файлов не откатывают удаление записей.")


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
    print("Сканирование не изменяет БД и файлы и не является атомарным снимком.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Проверка архивов аккаунтов со статусом BANNED (-1).")
    parser.add_argument("--upload-dir", type=Path, default=DEFAULT_UPLOAD_DIR)
    parser.add_argument("--details", action="store_true", help="Вывести проблемные аккаунты в JSON.")
    parser.add_argument("--scan-only", action="store_true", help="Только отчёт, без предложения удаления.")
    args = parser.parse_args(argv)
    deletion = None
    try:
        directory = args.upload_dir.expanduser().resolve()
        print(f"Каталог: {directory}")
        print("Проверка аккаунтов всех пользователей со статусом BANNED (-1)...", flush=True)
        if args.details:
            print("Проблемные аккаунты (JSON): empty_file_name — имя не задано; "
                  "missing_file — файл отсутствует или путь недопустим.")
        summary = asyncio.run(run_scan(directory, details=args.details))
        print_report(summary)
        if args.scan_only or not summary.candidates:
            print("Удаление не выполнялось." if args.scan_only else "Кандидатов на удаление нет.")
            return 0
        print(f"\nК удалению предложено аккаунтов: {len(summary.candidates)}")
        print("Условие: status = -1 и updated_at строго раньше "
              f"{months_before(summary.as_of, 3).isoformat()}. attempts не влияет.")
        print("ВНИМАНИЕ: удаляются записи БД и их файлы file_name. "
              "Каскады БД могут удалить связанные сессии, сообщения и логи; "
              "ссылки устройств могут заблокировать удаление.")
        print("Перед подтверждением сделайте резервную копию и остановите изменения "
              "аккаунтов и файлов. БД и диск не имеют общей транзакции. "
              "Общие архивы сохраняются; профили не удаляются.")
        if not confirm_deletion():
            print("Удаление отменено. БД и файлы не изменялись.")
            return 0
        deletion = DeletionSummary(requested=len(summary.candidates))
        try:
            asyncio.run(run_deletion(directory, summary, deletion))
        finally:
            print_deletion_report(deletion)
        print("\nПОВТОРНАЯ ПРОВЕРКА ОСТАВШИХСЯ ЗАБАНЕННЫХ АККАУНТОВ")
        print_report(asyncio.run(run_scan(directory)))
        return 1 if deletion.file_errors else 0
    except KeyboardInterrupt:
        print("Операция прервана. Отчёт может быть неполным. "
              "Если удаление началось, проверьте итоговое состояние БД и файлов.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Ошибка операции: {type(exc).__name__}. Проверьте подключение к БД, "
              "ограничения внешних ключей и доступность каталога. "
              "Отчёт может быть неполным; подтверждённое удаление не отменяется.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
