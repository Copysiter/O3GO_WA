"""Read-only inventory of disk files without exact account.file_name references.

    docker compose exec api python /app/missing_files_unreferenced.py
    python -m app.missing_files_unreferenced --archives-only --details

All regular root files are included by default; subdirectories are not scanned.
Exact references are case/whitespace sensitive. Candidates are DB rows whose
file_name has the same prefix before the first underscore (not Account.number).
Distinct candidate accounts and file/account pairs are reported separately.
This is a live scan, not an atomic DB/filesystem snapshot. Archive contents are
not validated, and prefix equality does not establish suitability for restore.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.missing_files import DEFAULT_UPLOAD_DIR, SCAN_BATCH_SIZE, _file_prefix
from app.utils.account_files import account_file_exists


@dataclass
class Inventory:
    disk_names: set[str]
    referenced_names: set[str] = field(default_factory=set)
    missing_candidates: Counter = field(default_factory=Counter)
    present_candidates: Counter = field(default_factory=Counter)
    checked_accounts: int = 0

    @property
    def unreferenced_names(self) -> list[str]:
        return sorted(self.disk_names - self.referenced_names)


def index_files(directory: Path, archives_only: bool = False) -> set[str]:
    names = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            if archives_only and not entry.name.endswith(".tar.gz"):
                continue
            if account_file_exists(directory, entry.name):
                names.add(entry.name)
    return names


def add_batch(inventory: Inventory, directory: Path, rows) -> None:
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    for _, name in rows:
        if not name:
            continue
        inventory.checked_accounts += 1
        if name in inventory.disk_names:
            inventory.referenced_names.add(name)
        prefix = _file_prefix(name)
        if prefix is None:
            continue
        counts = (inventory.present_candidates if account_file_exists(directory, name)
                  else inventory.missing_candidates)
        counts[prefix] += 1


async def scan_accounts(db, directory: Path, *, archives_only: bool = False) -> Inventory:
    from app.crud.account import account

    inventory = Inventory(await asyncio.to_thread(index_files, directory, archives_only))
    before_id = None
    while True:
        rows = await account.list_archive_files(
            db, before_id=before_id, limit=SCAN_BATCH_SIZE,
        )
        if not rows:
            break
        await asyncio.to_thread(add_batch, inventory, directory, rows)
        before_id = rows[-1][0]
        if len(rows) < SCAN_BATCH_SIZE:
            break
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    return inventory


async def run_scan(directory: Path, *, archives_only: bool = False) -> Inventory:
    from app.adapters.db.session import async_session, engine

    try:
        async with async_session() as db:
            return await scan_accounts(db, directory, archives_only=archives_only)
    finally:
        await engine.dispose()


def summarize(inventory: Inventory) -> dict[str, int]:
    names = inventory.unreferenced_names
    prefixes = Counter(_file_prefix(name) for name in names)
    prefixes.pop(None, None)
    missing = inventory.missing_candidates
    present = inventory.present_candidates
    return {
        "disk_files": len(inventory.disk_names),
        "checked_accounts": inventory.checked_accounts,
        "referenced_files": len(inventory.referenced_names),
        "unreferenced_files": len(names),
        "without_prefix": sum(_file_prefix(name) is None for name in names),
        "with_missing_candidates": sum(n for p, n in prefixes.items() if missing[p]),
        "with_present_candidates": sum(n for p, n in prefixes.items() if present[p]),
        "without_candidates": sum(
            _file_prefix(name) is None or not (
                missing[_file_prefix(name)] or present[_file_prefix(name)]
            ) for name in names
        ),
        "missing_accounts": sum(missing[p] for p in prefixes),
        "present_accounts": sum(present[p] for p in prefixes),
        "missing_pairs": sum(n * missing[p] for p, n in prefixes.items()),
        "present_pairs": sum(n * present[p] for p, n in prefixes.items()),
    }


def print_report(inventory: Inventory, *, details: bool = False) -> None:
    labels = {
        "disk_files": "Файлов на диске",
        "checked_accounts": "Проверено аккаунтов с непустым file_name",
        "referenced_files": "Файлов с точной ссылкой в БД",
        "unreferenced_files": "Файлов без точной ссылки в БД",
        "without_prefix": "  Из них без допустимого префикса",
        "with_missing_candidates": "  С претендентами с отсутствующим файлом",
        "with_present_candidates": "  С претендентами с существующим другим файлом",
        "without_candidates": "  Без претендентов",
        "missing_accounts": "Уникальных аккаунтов-претендентов без файла",
        "present_accounts": "Уникальных аккаунтов-претендентов с другим файлом",
        "missing_pairs": "Пар файл–претендент без файла",
        "present_pairs": "Пар файл–претендент с другим файлом",
    }
    for key, value in summarize(inventory).items():
        print(f"{labels[key]}: {value}")
    if details:
        print("\nДетали файлов без точной ссылки (JSON):")
        for name in inventory.unreferenced_names:
            prefix = _file_prefix(name)
            print(json.dumps({
                "file_name": name,
                "prefix": prefix,
                "missing_candidates": inventory.missing_candidates[prefix],
                "present_candidates": inventory.present_candidates[prefix],
            }, ensure_ascii=True))
    print("Категории файлов с претендентами могут пересекаться.")
    print("Аккаунт считается один раз в уникальных аккаунтах, но может быть "
          "претендентом для нескольких файлов в счётчике пар.")
    print("Совпадение префикса не гарантирует пригодность файла для замены.")
    print("БД и файлы не изменялись. Проверка не является атомарным снимком.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Файлы без точных ссылок в БД и претенденты.")
    parser.add_argument("--upload-dir", type=Path, default=DEFAULT_UPLOAD_DIR)
    parser.add_argument("--archives-only", action="store_true", help="Только *.tar.gz.")
    parser.add_argument("--details", action="store_true", help="Счётчики для каждого файла.")
    args = parser.parse_args(argv)
    try:
        directory = args.upload_dir.expanduser().resolve()
        print(f"Каталог: {directory}")
        print("Файлы: " + ("*.tar.gz" if args.archives_only else "все") + "; без вложенных папок.")
        inventory = asyncio.run(run_scan(directory, archives_only=args.archives_only))
        print_report(inventory, details=args.details)
        return 0
    except KeyboardInterrupt:
        print("Проверка прервана. Итоговый отчёт не сформирован.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Ошибка проверки: {type(exc).__name__}. Итоговый отчёт не сформирован.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
