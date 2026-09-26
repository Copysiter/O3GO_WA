"""Read-only account archive diagnostics.

Run from the project root:
    python -m app.missing_files
    python app/missing_files.py --upload-dir /path/to/archives

Uses the application's POSTGRES_DSN (environment / .env in the working
directory). Does not start the API, initialize the database or modify files.
Alternative archives must match <prefix>_*.tar.gz in the storage root.
Names without an underscore, an empty prefix and paths are checked for
exact existence but do not qualify for prefix matching.
Results describe a live scan, not an atomic snapshot of the database and disk.
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

from app.utils.account_files import account_file_exists  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parent / "upload" / "wa"
SCAN_BATCH_SIZE = 1000


@dataclass
class ScanSummary:
    checked: int = 0
    missing: int = 0
    with_alternatives: int = 0

    @property
    def present(self) -> int:
        return self.checked - self.missing

    @property
    def without_alternatives(self) -> int:
        return self.missing - self.with_alternatives


def _file_prefix(file_name: str) -> str | None:
    if Path(file_name).name != file_name:
        return None
    prefix, separator, _ = file_name.partition("_")
    return prefix if prefix and separator else None


def _archive_prefixes(directory: Path) -> set[str]:
    prefixes: set[str] = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            if not entry.name.endswith(".tar.gz"):
                continue
            prefix = _file_prefix(entry.name)
            if prefix is not None and account_file_exists(
                directory, entry.name
            ):
                prefixes.add(prefix)
    return prefixes


def _scan_batch(
    directory: Path,
    archive_files: Sequence[tuple[int, str]],
    prefixes: set[str],
) -> ScanSummary:
    if not directory.is_dir():
        raise NotADirectoryError(
            f"Account archive directory is unavailable: {directory}"
        )
    summary = ScanSummary()
    for _, file_name in archive_files:
        if not file_name:
            continue
        summary.checked += 1
        if not account_file_exists(directory, file_name):
            summary.missing += 1
            if _file_prefix(file_name) in prefixes:
                summary.with_alternatives += 1
    return summary


async def scan_accounts(
    db: AsyncSession,
    directory: Path,
    *,
    progress: Callable[[ScanSummary], None] | None = None,
) -> ScanSummary:
    """Scan every nonempty file_name, counting accounts rather than files."""
    from app.crud.account import account

    prefixes = await asyncio.to_thread(_archive_prefixes, directory)
    summary = ScanSummary()
    before_id = None
    while True:
        archive_files = await account.list_archive_files(
            db, before_id=before_id, limit=SCAN_BATCH_SIZE
        )
        if not archive_files:
            break
        batch = await asyncio.to_thread(
            _scan_batch, directory, archive_files, prefixes
        )
        summary.checked += batch.checked
        summary.missing += batch.missing
        summary.with_alternatives += batch.with_alternatives
        if progress is not None:
            progress(summary)
        before_id = archive_files[-1][0]
        if len(archive_files) < SCAN_BATCH_SIZE:
            break
    return summary


async def run_scan(
    directory: Path,
    *,
    progress: Callable[[ScanSummary], None] | None = None,
) -> ScanSummary:
    """Use the application's DB settings and release resources on failure."""
    from app.adapters.db.session import async_session, engine

    try:
        async with async_session() as db:
            return await scan_accounts(db, directory, progress=progress)
    finally:
        await engine.dispose()


def _count(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _print_progress(summary: ScanSummary) -> None:
    print(
        f"\rПроверено: {_count(summary.checked)} | "
        f"Нет точного файла: {_count(summary.missing)} | "
        f"Есть альтернативы: {_count(summary.with_alternatives)}",
        end="", flush=True,
    )


def _print_summary(summary: ScanSummary) -> None:
    rows = [
        ("Проверено аккаунтов с заполненным file_name", summary.checked),
        ("Точный файл найден", summary.present),
        ("Точный файл отсутствует", summary.missing),
        ("  Есть архив с тем же префиксом", summary.with_alternatives),
        ("  Нет архива с тем же префиксом", summary.without_alternatives),
    ]
    label_width = max(len(label) for label, _ in rows)
    count_width = max(len(_count(value)) for _, value in rows)

    def border(left: str, middle: str, right: str) -> str:
        return (
            left + "─" * (label_width + 2) + middle
            + "─" * (count_width + 2) + right
        )

    print(border("┌", "┬", "┐"))
    for index, (label, value) in enumerate(rows):
        if index == 2:
            print(border("├", "┼", "┤"))
        print(f"│ {label:<{label_width}} │ {_count(value):>{count_width}} │")
    print(border("└", "┴", "┘"))


def main(argv: Sequence[str] | None = None) -> int:
    """Print the report; return 1 on failure and 130 on interruption."""
    parser = argparse.ArgumentParser(
        description="Проверка архивов аккаунтов без изменения БД и файлов.",
    )
    parser.add_argument(
        "--upload-dir", type=Path, default=DEFAULT_UPLOAD_DIR,
        help="Каталог архивов (по умолчанию: app/upload/wa).",
    )
    args = parser.parse_args(argv)
    started = monotonic()
    directory = args.upload_dir
    try:
        directory = directory.expanduser().resolve()
        print("\nПРОВЕРКА АРХИВОВ АККАУНТОВ")
        print(f"Каталог: {directory}")
        print("Поиск альтернатив: <префикс>_*.tar.gz, без вложенных папок.")
        print("Сканирование каталога и проверка аккаунтов...", flush=True)
        summary = asyncio.run(run_scan(
            directory,
            progress=_print_progress if sys.stdout.isatty() else None,
        ))
    except KeyboardInterrupt:
        print("\nПроверка прервана. Итоговый отчёт не сформирован.",
              file=sys.stderr)
        return 130
    except Exception as exc:
        print(
            f"\nНе удалось завершить проверку каталога {directory}: "
            f"{type(exc).__name__}: {exc}\nИтоговый отчёт не сформирован.",
            file=sys.stderr,
        )
        return 1

    print("\nИТОГИ")
    _print_summary(summary)
    print(f"Время проверки: {monotonic() - started:.1f} с.")
    print("Считаются аккаунты, а не файлы. БД и архивы не изменялись.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
