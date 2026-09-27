"""Read-only aggregated account archive diagnostics.

Recommended server invocation:
    docker compose exec api python /app/missing_files_full.py

From the project root, with a POSTGRES_DSN reachable from the host:
    python app/missing_files_full.py
    python -m app.missing_files_full --upload-dir /path/to/archives

Uses application settings (environment / .env in the working directory).
The default storage directory is upload/wa next to this script, not relative
to the working directory. No database records or archives are modified.

Account counts, unique alternative file counts and duplicate number groups
are reported separately. Timestamps are integer seconds from filenames, not
filesystem times or evidence that an archive is a suitable replacement.
Owners refer to the union of exact DB references to all alternatives of an
account. Duplicate numbers are checked independently using only exact files.

Memory grows with indexed filenames, distinct numbers, reference owners and
missing accounts; individual comparison pairs are not retained. The live scan
is not an atomic database/filesystem snapshot. No content validation is done.
Exit codes: 0 success, 1 failure, 2 invalid arguments, 130 interruption.
"""

import argparse
import asyncio
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from time import monotonic
from typing import NamedTuple, Sequence


DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parent / "upload" / "wa"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Агрегированный анализ отсутствующих архивов аккаунтов.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Только чтение: БД и архивы не изменяются.\n"
            "Подключение: POSTGRES_DSN из окружения или .env.\n"
            "Рекомендуемый запуск на сервере:\n"
            "  docker compose exec api python /app/missing_files_full.py"
        ),
    )
    parser.add_argument(
        "--upload-dir", type=Path, default=DEFAULT_UPLOAD_DIR, metavar="PATH",
        help="Каталог архивов (по умолчанию: app/upload/wa).",
    )
    return parser.parse_args(argv)


# Help and argument validation must work before loading application settings.
_cli_args = _parse_args() if __name__ == "__main__" else None

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app import missing_files as base
    from app.crud.account import AccountCRUD
    from app.missing_files_alt import _index_archives
    from app.models.account import Account
    from app.utils.account_files import account_file_exists
except Exception as exc:
    if __name__ != "__main__":
        raise
    print(
        "Не удалось загрузить зависимости или настройки: "
        f"{type(exc).__name__}."
        "\nПроверьте окружение приложения. Параметры подключения не выводятся."
        "\nИтоговый отчёт не сформирован.", file=sys.stderr,
    )
    raise SystemExit(1) from None


SCAN_BATCH_SIZE = 1000


class AccountFileAuditRow(NamedTuple):
    """Account fields needed by the standalone audit, without ORM relations."""

    id: int
    number: str | None
    user_id: int
    file_name: str | None


class FileAuditRepository(AccountCRUD):
    """Keep the audit's read query local to this script."""

    async def list_file_audit_rows(
        self,
        db: AsyncSession,
        *,
        before_id: int | None = None,
        limit: int = 1000,
    ) -> Sequence[AccountFileAuditRow]:
        """Read all accounts in ID-descending batches, including NULL names."""
        stmt = select(
            Account.id, Account.number, Account.user_id, Account.file_name
        )
        if before_id is not None:
            stmt = stmt.where(Account.id < before_id)
        stmt = stmt.order_by(Account.id.desc()).limit(limit)

        result = await db.execute(stmt)
        return [
            AccountFileAuditRow(row[0], row[1], row[2], row[3])
            for row in result.all()
        ]


class TimestampCategory(str, Enum):
    NEWER_ONLY = "newer_only"
    OLDER_ONLY = "older_only"
    BOTH = "both"
    EQUAL_ONLY = "equal_only"
    UNAVAILABLE = "unavailable"


class OwnerCategory(str, Enum):
    UNREFERENCED = "unreferenced"
    SAME_USER = "same_user"
    OTHER_USERS = "other_users"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class PrefixAlternatives:
    """Reusable statistics for one prefix, not account/file pairs."""

    file_count: int = 0
    referenced_files: int = 0
    min_timestamp: int | None = None
    max_timestamp: int | None = None
    has_invalid_timestamp: bool = False
    owner_ids: frozenset[int] = frozenset()

    @property
    def unreferenced_files(self) -> int:
        return self.file_count - self.referenced_files


@dataclass
class AlternativeReport:
    """Keep account counts separate from unique alternative file counts."""

    missing_accounts: int = 0
    without_alternatives: int = 0
    alternative_files: int = 0
    referenced_files: int = 0
    accounts_with_unreferenced: int = 0
    accounts_with_invalid_timestamp: int = 0
    matrix: Counter[tuple[TimestampCategory, OwnerCategory]] = field(
        default_factory=Counter
    )

    @property
    def with_alternatives(self) -> int:
        return self.missing_accounts - self.without_alternatives

    @property
    def unreferenced_files(self) -> int:
        return self.alternative_files - self.referenced_files

    def timestamp_count(self, category: TimestampCategory) -> int:
        return sum(self.matrix[category, owner] for owner in OwnerCategory)

    @property
    def with_newer(self) -> int:
        return (
            self.timestamp_count(TimestampCategory.NEWER_ONLY)
            + self.timestamp_count(TimestampCategory.BOTH)
        )

    @property
    def with_older(self) -> int:
        return (
            self.timestamp_count(TimestampCategory.OLDER_ONLY)
            + self.timestamp_count(TimestampCategory.BOTH)
        )


def parse_archive_timestamp(file_name: str | None) -> int | None:
    """Parse nonnegative ASCII seconds; return None for malformed names."""
    if (
        not file_name or not file_name.endswith(".tar.gz")
        or base._file_prefix(file_name) is None
    ):
        return None
    timestamp = file_name.partition("_")[2][:-len(".tar.gz")]
    if not timestamp.isascii() or not timestamp.isdecimal():
        return None
    try:
        return int(timestamp)
    except ValueError:
        # Python 3.11 limits the length of decimal integer conversions.
        return None


def summarize_alternatives(
    file_names: Iterable[str],
    owners_by_file: Mapping[str, Set[int]],
) -> PrefixAlternatives:
    """Summarize one prefix's prevalidated disk names without any I/O."""
    unique_names = set(file_names)
    referenced_files = 0
    owner_ids: set[int] = set()
    min_timestamp = None
    max_timestamp = None
    has_invalid_timestamp = False
    for file_name in unique_names:
        owners = owners_by_file.get(file_name)
        if owners:
            referenced_files += 1
            owner_ids.update(owners)
        timestamp = parse_archive_timestamp(file_name)
        if timestamp is None:
            has_invalid_timestamp = True
        else:
            if min_timestamp is None or timestamp < min_timestamp:
                min_timestamp = timestamp
            if max_timestamp is None or timestamp > max_timestamp:
                max_timestamp = timestamp
    return PrefixAlternatives(
        file_count=len(unique_names),
        referenced_files=referenced_files,
        min_timestamp=min_timestamp,
        max_timestamp=max_timestamp,
        has_invalid_timestamp=has_invalid_timestamp,
        owner_ids=frozenset(owner_ids),
    )


def classify_timestamp(
    source_timestamp: int | None,
    alternatives: PrefixAlternatives,
) -> TimestampCategory:
    """Classify all alternatives of an account using cached extrema."""
    if alternatives.file_count == 0:
        raise ValueError("Timestamp classification requires alternatives")
    if (
        source_timestamp is None or alternatives.min_timestamp is None
        or alternatives.max_timestamp is None
    ):
        return TimestampCategory.UNAVAILABLE
    has_older = alternatives.min_timestamp < source_timestamp
    has_newer = alternatives.max_timestamp > source_timestamp
    if has_older and has_newer:
        return TimestampCategory.BOTH
    if has_newer:
        return TimestampCategory.NEWER_ONLY
    if has_older:
        return TimestampCategory.OLDER_ONLY
    return TimestampCategory.EQUAL_ONLY


def classify_owner(user_id: int, owner_ids: Set[int]) -> OwnerCategory:
    """Compare the source owner with the union of exact-reference owners."""
    if not owner_ids:
        return OwnerCategory.UNREFERENCED
    if user_id not in owner_ids:
        return OwnerCategory.OTHER_USERS
    if len(owner_ids) == 1:
        return OwnerCategory.SAME_USER
    return OwnerCategory.MIXED


def analyze_missing_accounts(
    accounts: Iterable[AccountFileAuditRow],
    archives: Mapping[str, Sequence[str]],
    owners_by_file: Mapping[str, Set[int]],
) -> AlternativeReport:
    """Aggregate already missing rows and a safe disk index, without I/O.

    Each input row represents a distinct account with a nonempty filename.
    References must come from the completed DB scan. Ownership describes the
    entire set of alternatives, not the file that establishes a time relation.
    """
    report = AlternativeReport()
    prefix_summaries: dict[str, PrefixAlternatives] = {}
    for account in accounts:
        if not account.file_name:
            raise ValueError(
                f"Missing-file analysis requires file_name: id={account.id}"
            )
        report.missing_accounts += 1
        prefix = base._file_prefix(account.file_name)
        if prefix is None or not archives.get(prefix):
            report.without_alternatives += 1
            continue
        if prefix not in prefix_summaries:
            alternatives = summarize_alternatives(
                archives[prefix], owners_by_file
            )
            prefix_summaries[prefix] = alternatives
            report.alternative_files += alternatives.file_count
            report.referenced_files += alternatives.referenced_files
        alternatives = prefix_summaries[prefix]
        timestamp = parse_archive_timestamp(account.file_name)
        timestamp_category = classify_timestamp(timestamp, alternatives)
        owner_category = classify_owner(
            account.user_id, alternatives.owner_ids
        )
        report.matrix[timestamp_category, owner_category] += 1
        if alternatives.unreferenced_files:
            report.accounts_with_unreferenced += 1
        if timestamp is None or alternatives.has_invalid_timestamp:
            report.accounts_with_invalid_timestamp += 1
    return report


class AuditScanError(RuntimeError):
    """A failed scan stage with safe context and the original cause."""


@dataclass(frozen=True, slots=True)
class FileScanCounts:
    total_accounts: int = 0
    empty_file_names: int = 0
    missing_files: int = 0

    @property
    def configured_files(self) -> int:
        return self.total_accounts - self.empty_file_names

    @property
    def present_files(self) -> int:
        return self.configured_files - self.missing_files


class DuplicateGroupSummary(NamedTuple):
    size: int
    groups: int
    missing_files: int

    @property
    def accounts(self) -> int:
        return self.size * self.groups


@dataclass(frozen=True, slots=True)
class DuplicateReport:
    rows: tuple[DuplicateGroupSummary, ...] = ()
    empty_numbers: int = 0

    @property
    def groups(self) -> int:
        return sum(row.groups for row in self.rows)

    @property
    def accounts(self) -> int:
        return sum(row.accounts for row in self.rows)

    @property
    def missing_files(self) -> int:
        return sum(row.missing_files for row in self.rows)


@dataclass(frozen=True, slots=True)
class FileAuditReport:
    accounts: FileScanCounts
    alternatives: AlternativeReport
    duplicates: DuplicateReport


def summarize_duplicates(
    number_counts: Mapping[str, int],
    missing_by_number: Mapping[str, int],
    empty_numbers: int,
) -> DuplicateReport:
    """Group nonempty raw numbers by size, independently of alternatives."""
    groups_by_size: Counter[int] = Counter()
    missing_by_size: Counter[int] = Counter()
    for number, size in number_counts.items():
        if size >= 2:
            groups_by_size[size] += 1
            missing_by_size[size] += missing_by_number.get(number, 0)
    return DuplicateReport(
        rows=tuple(
            DuplicateGroupSummary(size, groups, missing_by_size[size])
            for size, groups in sorted(groups_by_size.items())
        ),
        empty_numbers=empty_numbers,
    )


def _ensure_archive_directory(directory: Path) -> None:
    if not directory.is_dir():
        raise NotADirectoryError(
            f"Account archive directory is unavailable: {directory}"
        )


def _missing_file_ids(
    directory: Path,
    rows: Sequence[AccountFileAuditRow],
) -> set[int]:
    _ensure_archive_directory(directory)
    return {
        row.id for row in rows
        if row.file_name and not account_file_exists(directory, row.file_name)
    }


async def scan_accounts(
    db: AsyncSession,
    directory: Path,
    *,
    progress: Callable[[FileScanCounts], None] | None = None,
) -> FileAuditReport:
    """Read all accounts once, check exact files and aggregate diagnostics."""
    try:
        archives = await asyncio.to_thread(_index_archives, directory)
    except (OSError, RuntimeError) as exc:
        raise AuditScanError(
            f"Archive indexing failed: directory={directory}, "
            f"error={type(exc).__name__}"
        ) from exc
    indexed_names = {name for names in archives.values() for name in names}
    owners_by_file: dict[str, set[int]] = {}
    missing_accounts: list[AccountFileAuditRow] = []
    number_counts: Counter[str] = Counter()
    missing_by_number: Counter[str] = Counter()
    empty_numbers = 0
    counts = FileScanCounts()
    repository = FileAuditRepository()
    before_id = None

    while True:
        try:
            rows = await repository.list_file_audit_rows(
                db, before_id=before_id, limit=SCAN_BATCH_SIZE
            )
        except Exception as exc:
            raise AuditScanError(
                f"Account query failed: before_id={before_id}, "
                f"limit={SCAN_BATCH_SIZE}, error={type(exc).__name__}"
            ) from exc
        if not rows:
            break
        try:
            missing_ids = await asyncio.to_thread(
                _missing_file_ids, directory, rows
            )
        except (OSError, RuntimeError) as exc:
            raise AuditScanError(
                f"Archive check failed: directory={directory}, "
                f"before_id={before_id}, error={type(exc).__name__}"
            ) from exc

        empty_file_names = 0
        for row in rows:
            missing = row.id in missing_ids
            if not row.file_name:
                empty_file_names += 1
            elif row.file_name in indexed_names:
                owners = owners_by_file.setdefault(row.file_name, set())
                owners.add(row.user_id)
            if missing:
                missing_accounts.append(row)
            if row.number is None or not row.number.strip():
                empty_numbers += 1
            else:
                number_counts[row.number] += 1
                if missing:
                    missing_by_number[row.number] += 1

        counts = FileScanCounts(
            total_accounts=counts.total_accounts + len(rows),
            empty_file_names=counts.empty_file_names + empty_file_names,
            missing_files=counts.missing_files + len(missing_ids),
        )
        if progress is not None:
            progress(counts)
        before_id = rows[-1].id
        if len(rows) < SCAN_BATCH_SIZE:
            break

    try:
        await asyncio.to_thread(_ensure_archive_directory, directory)
    except (OSError, RuntimeError) as exc:
        raise AuditScanError(
            f"Archive storage became unavailable: directory={directory}, "
            f"error={type(exc).__name__}"
        ) from exc
    alternatives = await asyncio.to_thread(
        analyze_missing_accounts, missing_accounts, archives, owners_by_file
    )
    duplicates = summarize_duplicates(
        number_counts, missing_by_number, empty_numbers
    )
    return FileAuditReport(counts, alternatives, duplicates)


async def run_scan(
    directory: Path,
    *,
    progress: Callable[[FileScanCounts], None] | None = None,
) -> FileAuditReport:
    """Release DB resources on success, failure or cancellation."""
    from app.adapters.db.session import async_session, engine

    try:
        async with async_session() as db:
            return await scan_accounts(db, directory, progress=progress)
    finally:
        await engine.dispose()


TIMESTAMP_LABELS = {
    TimestampCategory.NEWER_ONLY: "Есть новее, нет старее",
    TimestampCategory.OLDER_ONLY: "Есть старее, нет новее",
    TimestampCategory.BOTH: "Есть и новее, и старее",
    TimestampCategory.EQUAL_ONLY: "Равные, без старее/новее",
    TimestampCategory.UNAVAILABLE: "Нет доступных сравнений",
}


def _print_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str | int]],
) -> None:
    cells = [list(headers)] + [
        [base._count(value) if isinstance(value, int) else value
         for value in row]
        for row in rows
    ]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]

    def border(left: str, middle: str, right: str) -> str:
        segments = middle.join("─" * (width + 2) for width in widths)
        return left + segments + right

    print(border("┌", "┬", "┐"))
    for index, row in enumerate(cells):
        if index == 1 or (index > 1 and row[0] == "Итого"):
            print(border("├", "┼", "┤"))
        print("│ " + " │ ".join(
            value.ljust(width) if column == 0 else value.rjust(width)
            for column, (value, width) in enumerate(zip(row, widths))
        ) + " │")
    print(border("└", "┴", "┘"))


def print_report(report: FileAuditReport) -> None:
    """Print aggregate counts and explanations, never individual records."""
    counts = report.accounts
    alternatives = report.alternatives
    duplicates = report.duplicates

    print("\n1. ОБЩАЯ ПРОВЕРКА АККАУНТОВ")
    _print_table(("Показатель", "Аккаунтов"), [
        ("Всего в БД", counts.total_accounts),
        ("Без file_name (NULL или пустая строка)", counts.empty_file_names),
        ("С заполненным file_name", counts.configured_files),
        ("Точный файл существует", counts.present_files),
        ("Точный файл отсутствует", counts.missing_files),
    ])
    print("Пустой file_name — отсутствие имени, а не указанного архива.")
    print("Существование проверяется только для допустимого файла "
          "внутри хранилища.")

    print("\n2. АЛЬТЕРНАТИВЫ И TIMESTAMP (АККАУНТЫ)")
    timestamp_rows: list[tuple[str, int]] = [
        ("Альтернативы не найдены", alternatives.without_alternatives),
        ("Альтернативы найдены", alternatives.with_alternatives),
    ]
    timestamp_rows.extend(
        ("  " + TIMESTAMP_LABELS[category],
         alternatives.timestamp_count(category))
        for category in TimestampCategory
    )
    _print_table(("Показатель", "Аккаунтов"), timestamp_rows)
    print("Только аккаунты с заполненным, но отсутствующим точным файлом.")
    print("Новее/старее: timestamp альтернативы больше/меньше значения "
          "в имени из БД.")
    print("Пять категорий не пересекаются. Направления определяются "
          "по разобранным именам.")
    print("Равные: есть совпавший timestamp, более старых/новых не найдено.")
    print("Нет сравнений: не разобрано исходное имя "
          "или все имена альтернатив.")
    _print_table(("Пересекающиеся показатели", "Аккаунтов"), [
        ("Хотя бы одна более новая альтернатива", alternatives.with_newer),
        ("Хотя бы одна более старая альтернатива", alternatives.with_older),
        ("И те, и другие (пересечение)",
         alternatives.timestamp_count(TimestampCategory.BOTH)),
        ("Есть неразбираемый timestamp в именах",
         alternatives.accounts_with_invalid_timestamp),
    ])
    print("Показатели выше нельзя складывать: один аккаунт может "
          "попасть в несколько строк.")
    print("Неразбираемые имена учитываются "
          "и при частично успешных сравнениях;")
    print("этот показатель относится только к аккаунтам с альтернативами.")

    print("\n3. УНИКАЛЬНЫЕ АЛЬТЕРНАТИВНЫЕ ФАЙЛЫ")
    _print_table(("Показатель", "Файлов"), [
        ("Уникальных альтернативных архивов", alternatives.alternative_files),
        ("Есть точное совпадение file_name в БД",
         alternatives.referenced_files),
        ("Нет точного совпадения file_name в БД",
         alternatives.unreferenced_files),
    ])
    print("Один файл считается один раз, даже если подходит "
          "нескольким аккаунтам.")
    print("Ссылка — буквальное совпадение полного имени "
          "с file_name любой записи БД.")

    print("\n4. TIMESTAMP И ВЛАДЕЛЬЦЫ ССЫЛОК (АККАУНТЫ)")
    matrix_rows: list[list[str | int]] = []
    for category in TimestampCategory:
        matrix_rows.append([
            TIMESTAMP_LABELS[category],
            *(alternatives.matrix[category, owner] for owner in OwnerCategory),
            alternatives.timestamp_count(category),
        ])
    matrix_rows.append([
        "Итого",
        *(sum(alternatives.matrix[category, owner]
              for category in TimestampCategory) for owner in OwnerCategory),
        alternatives.with_alternatives,
    ])
    _print_table(
        ("Категория timestamp", "Без ссылок", "Свой", "Другие",
         "Свой+другие", "Всего"), matrix_rows,
    )
    print("Каждый аккаунт с альтернативами попадает ровно в одну ячейку.")
    print("Без ссылок: ни одна альтернатива не указана в БД.")
    print("Свой: все найденные ссылки имеют user_id исходного аккаунта.")
    print("Другие: ссылки есть только у иных user_id. "
          "Свой+другие: встречаются оба варианта.")
    print("Владельцы относятся ко ВСЕМ альтернативам аккаунта, "
          "а не только к более новым.")
    print("Признак времени и ссылка могут относиться к разным файлам; "
          "таблица не выбирает замену.")
    print("Аккаунтов хотя бы с одной альтернативой без ссылки в БД: "
          f"{base._count(alternatives.accounts_with_unreferenced)}.")
    print("Этот показатель может пересекаться с колонками, "
          "где ссылки присутствуют.")

    print("\n5. ДУБЛИКАТЫ ACCOUNT.NUMBER")
    duplicate_rows: list[tuple[str, int, int, int]] = [
        (f"По {base._count(row.size)}", row.groups,
         row.accounts, row.missing_files)
        for row in duplicates.rows
    ]
    duplicate_rows.append((
        "Итого", duplicates.groups, duplicates.accounts,
        duplicates.missing_files,
    ))
    _print_table(
        ("Размер группы", "Групп", "Аккаунтов", "Файл отсутствует"),
        duplicate_rows,
    )
    if not duplicates.rows:
        print("Повторяющиеся непустые номера не найдены.")
    print("Аккаунтов с пустым number: "
          f"{base._count(duplicates.empty_numbers)}.")
    print("NULL, пустые строки и строки из пробелов не образуют "
          "группу дубликатов.")
    print("Группы найдены по всей БД, независимо от пользователя "
          "и заполненности file_name.")
    print("Последняя колонка считает аккаунты с заполненным, "
          "но отсутствующим точным файлом.")
    print("Они уже входят в общий счётчик отсутствующих файлов "
          "и не прибавляются повторно.")
    print("В этом блоке альтернативы, timestamp и владельцы не сравниваются.")


def _print_progress(counts: FileScanCounts) -> None:
    print(
        f"\rПроверено: {base._count(counts.total_accounts)} | "
        f"Нет точного файла: {base._count(counts.missing_files)} | "
        f"Без file_name: {base._count(counts.empty_file_names)}",
        end="", flush=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run diagnostics; report failures without exposing connection details."""
    if argv is None and _cli_args is not None:
        args = _cli_args
    else:
        args = _parse_args(argv)
    started = monotonic()
    try:
        directory = args.upload_dir.expanduser().resolve()
        print("\nПОЛНЫЙ АНАЛИЗ АРХИВОВ АККАУНТОВ")
        print(f"Каталог: {directory}")
        print("Альтернативы: <префикс>_*.tar.gz, без вложенных папок.")
        print("Индексация каталога и проверка аккаунтов...", flush=True)
        report = asyncio.run(run_scan(
            directory,
            progress=_print_progress if sys.stdout.isatty() else None,
        ))
        print("\nИТОГИ")
        print_report(report)
        print(f"\nВремя проверки: {monotonic() - started:.1f} с.")
        print("БД и архивы не изменялись. Проверка не является "
              "атомарным снимком БД и диска.")
        print("Timestamp отражает имя, не пригодность содержимого архива. "
              "Замена не выполняется.")
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nПроверка прервана. Итоговый отчёт не сформирован.",
              file=sys.stderr)
        return 130
    except AuditScanError as exc:
        print(f"\nОшибка проверки: {exc}\nИтоговый отчёт не сформирован.",
              file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"\nОшибка проверки: {type(exc).__name__}. "
            "Проверьте настройки и доступность БД и хранилища.\n"
            "Подробности исключения скрыты "
            "для защиты параметров подключения.\n"
            "Итоговый отчёт не сформирован.", file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
