"""Read-only diagnostics of missing archives and their alternatives.

Run in the application's Docker Compose environment:
    docker compose exec api python /app/missing_files_alt.py

Or from the project root with a POSTGRES_DSN reachable from the host:
    python -m app.missing_files_alt
    python app/missing_files_alt.py --upload-dir /path/to/archives

Reuses missing_files' exact-file and prefix rules. Only archives that are
alternatives for accounts with missing files enter the new file counters.
A file is referenced when any account's file_name equals its full filename;
paths, case and whitespace are not normalized. Duplicate references count once.
Memory usage grows with archive names on disk and distinct file_name values
in the database. The live scan is not an atomic database/filesystem snapshot.
No database records or archives are modified. An unreferenced archive is not
necessarily a valid replacement for a missing one.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import missing_files as base  # noqa: E402
from app.utils.account_files import account_file_exists  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


SCAN_BATCH_SIZE = base.SCAN_BATCH_SIZE


@dataclass
class AlternativeSummary(base.ScanSummary):
    alternative_files: int = 0
    referenced_files: int = 0

    @property
    def unreferenced_files(self) -> int:
        return self.alternative_files - self.referenced_files


def _index_archives(directory: Path) -> dict[str, list[str]]:
    archives: dict[str, list[str]] = {}
    with os.scandir(directory) as entries:
        for entry in entries:
            if not entry.name.endswith(".tar.gz"):
                continue
            prefix = base._file_prefix(entry.name)
            if prefix is not None and account_file_exists(
                directory, entry.name
            ):
                archives.setdefault(prefix, []).append(entry.name)
    return archives


def _scan_batch(
    directory: Path,
    archive_files: Sequence[tuple[int, str]],
    archives: dict[str, list[str]],
) -> tuple[base.ScanSummary, set[str]]:
    if not directory.is_dir():
        raise NotADirectoryError(
            f"Account archive directory is unavailable: {directory}"
        )
    summary = base.ScanSummary()
    missing_prefixes: set[str] = set()
    for _, file_name in archive_files:
        if not file_name:
            continue
        summary.checked += 1
        if not account_file_exists(directory, file_name):
            summary.missing += 1
            prefix = base._file_prefix(file_name)
            if prefix is not None and prefix in archives:
                summary.with_alternatives += 1
                missing_prefixes.add(prefix)
    return summary, missing_prefixes


async def scan_accounts(
    db: AsyncSession,
    directory: Path,
    *,
    progress: Callable[[base.ScanSummary], None] | None = None,
) -> AlternativeSummary:
    """Scan all accounts once and match alternative filenames exactly."""
    from app.crud.account import account

    archives = await asyncio.to_thread(_index_archives, directory)
    database_names: set[str] = set()
    missing_prefixes: set[str] = set()
    summary = AlternativeSummary()
    before_id = None
    while True:
        archive_files = await account.list_archive_files(
            db, before_id=before_id, limit=SCAN_BATCH_SIZE
        )
        if not archive_files:
            break
        database_names.update(name for _, name in archive_files if name)
        batch, prefixes = await asyncio.to_thread(
            _scan_batch, directory, archive_files, archives
        )
        summary.checked += batch.checked
        summary.missing += batch.missing
        summary.with_alternatives += batch.with_alternatives
        missing_prefixes.update(prefixes)
        if progress is not None:
            progress(summary)
        before_id = archive_files[-1][0]
        if len(archive_files) < SCAN_BATCH_SIZE:
            break

    # References can occur before or after the missing account in DB batches.
    for prefix in missing_prefixes:
        for file_name in archives[prefix]:
            summary.alternative_files += 1
            if file_name in database_names:
                summary.referenced_files += 1
    return summary


async def run_scan(
    directory: Path,
    *,
    progress: Callable[[base.ScanSummary], None] | None = None,
) -> AlternativeSummary:
    """Close the DB session and dispose the engine, including on failure."""
    from app.adapters.db.session import async_session, engine

    try:
        async with async_session() as db:
            return await scan_accounts(db, directory, progress=progress)
    finally:
        await engine.dispose()


def _print_summary(summary: AlternativeSummary) -> None:
    print("\nАККАУНТЫ")
    base._print_summary(summary)
    print("\nАЛЬТЕРНАТИВНЫЕ ФАЙЛЫ ДЛЯ ОТСУТСТВУЮЩИХ АРХИВОВ")
    rows = [
        ("Уникальных альтернативных архивов", summary.alternative_files),
        ("  Есть точное совпадение file_name в БД", summary.referenced_files),
        ("  Нет точного совпадения file_name в БД",
         summary.unreferenced_files),
    ]
    label_width = max(len(label) for label, _ in rows)
    count_width = max(len(base._count(value)) for _, value in rows)
    print("┌" + "─" * (label_width + 2) + "┬" + "─" * (count_width + 2) + "┐")
    for label, value in rows:
        print(
            f"│ {label:<{label_width}} │ "
            f"{base._count(value):>{count_width}} │"
        )
    print("└" + "─" * (label_width + 2) + "┴" + "─" * (count_width + 2) + "┘")


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 on success, 1 on error and 130 on interruption."""
    parser = argparse.ArgumentParser(
        description="Проверка отсутствующих архивов и ссылок на альтернативы.",
        epilog=(
            "Использует POSTGRES_DSN приложения. Запуск через Docker: "
            "docker compose exec api python /app/missing_files_alt.py"
        ),
    )
    parser.add_argument(
        "--upload-dir", type=Path, default=base.DEFAULT_UPLOAD_DIR,
        help="Каталог архивов (по умолчанию: app/upload/wa).",
    )
    args = parser.parse_args(argv)
    started = monotonic()
    try:
        directory = args.upload_dir.expanduser().resolve()
        print("\nПРОВЕРКА АЛЬТЕРНАТИВНЫХ АРХИВОВ")
        print(f"Каталог: {directory}")
        print("Поиск альтернатив: <префикс>_*.tar.gz, без вложенных папок.")
        print("Сопоставление с БД: точное равенство полному file_name.")
        print("Сканирование каталога и проверка аккаунтов...", flush=True)
        summary = asyncio.run(run_scan(
            directory,
            progress=base._print_progress if sys.stdout.isatty() else None,
        ))
    except KeyboardInterrupt:
        print("\nПроверка прервана. Итоговый отчёт не сформирован.",
              file=sys.stderr)
        return 130
    except Exception as exc:
        print(
            f"\nНе удалось завершить проверку: {type(exc).__name__}: {exc}\n"
            "Итоговый отчёт не сформирован.", file=sys.stderr,
        )
        return 1

    print("\nИТОГИ")
    _print_summary(summary)
    print(f"Время проверки: {monotonic() - started:.1f} с.")
    print("Альтернативные файлы считаются один раз, "
          "независимо от числа ссылок.")
    print("Отсутствие ссылки в БД не доказывает пригодность архива "
          "для замены.")
    print("БД и архивы не изменялись.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
