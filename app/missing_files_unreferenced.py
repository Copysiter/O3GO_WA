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
    counts = summarize(inventory)

    def row(key: str) -> None:
        value = f"{counts[key]:,}".replace(",", " ")
        print(f"{labels[key].strip()}: {value}")

    print("\n1. ОБЩАЯ КАРТИНА")
    for key in ("disk_files", "checked_accounts", "referenced_files", "unreferenced_files"):
        row(key)
    print("Точная ссылка — полное имя файла равно file_name хотя бы одного аккаунта.")
    print("Регистр и пробелы не нормализуются. Несколько аккаунтов могут ссылаться "
          "на один файл; файл при этом считается один раз.")
    print("Файлы без точной ссылки не указаны в file_name ни одного аккаунта. "
          "Это ещё не означает, что их можно безопасно удалить.")

    print("\n2. ЧТО ТАКОЕ ПРЕТЕНДЕНТ")
    print("Это запись аккаунта, у которой префикс file_name совпадает с префиксом "
          "файла без точной ссылки. Префикс — часть имени до первого '_'.")
    print("Пример: файл 7999_100.tar.gz и file_name аккаунта 7999_200.tar.gz "
          "имеют общий префикс 7999, но разные полные имена.")
    print("Сравнивается префикс file_name, а не поле number и не содержимое архива.")

    print("\n3. РАЗБОР ФАЙЛОВ БЕЗ ТОЧНОЙ ССЫЛКИ")
    row("with_present_candidates")
    print("  Для этих файлов есть аккаунты с тем же префиксом, у которых текущий "
          "файл существует. У аккаунтов уже есть файлы, а эти лежат отдельно.")
    print("  Отчёт не определяет, какой файл старее, и не проверяет его содержимое.")
    row("with_missing_candidates")
    print("  Для этих файлов есть аккаунты с тем же префиксом, но указанный в БД "
          "файл отсутствует. Найденный файл — только возможный вариант замены.")
    if counts["with_missing_candidates"] == 0:
        print("  Вариантов по префиксу среди файлов без ссылок не найдено. "
              "Это НЕ означает, что файлы существуют у всех аккаунтов в БД.")
    row("without_candidates")
    print("  Для этих файлов не найдено аккаунтов с совпадающим префиксом file_name.")
    row("without_prefix")
    print("  Эти файлы входят в число файлов без претендентов: их имена не подходят "
          "для сопоставления по префиксу (например, не содержат '_').")
    print("Категории с существующими и отсутствующими файлами могут пересекаться: "
          "один файл может иметь претендентов обоих типов. Их нельзя просто складывать.")

    print("\n4. АККАУНТЫ И ПАРЫ — РАЗНЫЕ ПОКАЗАТЕЛИ")
    for key in ("missing_accounts", "present_accounts", "missing_pairs", "present_pairs"):
        row(key)
    print("Уникальные аккаунты — разные записи БД, подходящие хотя бы одному файлу "
          "без ссылки. Каждый аккаунт считается один раз.")
    print("Пары — все сочетания 'файл без ссылки + подходящий аккаунт'. "
          "Один аккаунт может подходить нескольким файлам, и наоборот.")
    print("Пример: 2 файла и 1 подходящий аккаунт дают 2 пары; "
          "2 файла и 2 подходящих каждому файлу аккаунта дают 4 пары.")
    print("Разница между числом проверенных аккаунтов и файлов с точной ссылкой "
          "не равна числу отсутствующих файлов: возможны общие ссылки, "
          "файлы во вложенных папках и ограничения выбранного режима сканирования.")

    print("\n5. ВОЗМОЖНЫЕ ПРИЧИНЫ ФАЙЛОВ БЕЗ ССЫЛОК")
    print("Это возможные сценарии из кода приложения, а не установленные причины:")
    print("- Файл загрузили отдельным запросом, но аккаунт не создали.")
    print("- Внешний API записал архив, но последующая запись профиля или операция "
          "с БД завершилась ошибкой; новый файл остался.")
    print("- Аккаунт переключили на новый архив, а очистка старого не завершилась.")
    print("- file_name изменили обычным запросом обновления без удаления старого файла.")
    print("- Аккаунт удалили из БД, несмотря на ошибку удаления его файла.")
    print("- Пользователя удалили вместе с аккаунтами каскадом БД, без очистки файлов.")
    print("Сам бан меняет статус, но не удаляет запись и не убирает ссылку на архив.")
    print("Для установления причины нужно сопоставить имена файлов с аудитом "
          "загрузок, обновлений и удалений. Этот скрипт аудит не анализирует.")
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
    print("\nОГРАНИЧЕНИЯ И БЕЗОПАСНОСТЬ")
    print("Проверены только файлы в корне выбранного каталога. Без --archives-only "
          "в отчёт входят не только *.tar.gz, но и другие файлы.")
    print("Совпадение префикса не гарантирует пригодность файла для замены. "
          "Отсутствие ссылки не является достаточным основанием для удаления.")
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
