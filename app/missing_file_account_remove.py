"""Find accounts with missing archives and optionally delete their DB rows.

Run on the server:
    docker compose exec api python /app/missing_file_account_remove.py

Or from the project root with a reachable POSTGRES_DSN:
    python app/missing_file_account_remove.py
    python -m app.missing_file_account_remove --upload-dir /path/to/archives

Uses application settings from the environment / .env. Only nonempty
account.file_name references are checked, as in missing_files_full.py.
Profiles and alternative archives are not checked; disk files are never
modified. Database FK cascades still apply. Any answer other than y cancels.
Run with account writers and archive maintenance paused: the database and
filesystem cannot be checked as one atomic snapshot.

Exit codes: 0 success/declined, 1 failure, 2 invalid arguments, 130 interrupt.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import NamedTuple, Sequence


DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parent / "upload" / "wa"
BATCH_SIZE = 1000


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Поиск аккаунтов без точного файла архива и удаление их записей "
            "из БД только после подтверждения y."
        ),
    )
    parser.add_argument(
        "--upload-dir", type=Path, default=DEFAULT_UPLOAD_DIR, metavar="PATH",
        help="Каталог архивов (по умолчанию: app/upload/wa).",
    )
    return parser.parse_args(argv)


# Argument validation and help must work without application dependencies.
_cli_args = _parse_args() if __name__ == "__main__" else None

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from sqlalchemy import delete, select
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.account import Account
    from app.utils.account_files import account_file_exists
except Exception as exc:
    if __name__ != "__main__":
        raise
    print(
        f"Не удалось загрузить зависимости: {type(exc).__name__}. "
        "Проверьте окружение приложения. БД не изменялась.",
        file=sys.stderr,
    )
    raise SystemExit(1) from None


class ArchiveReference(NamedTuple):
    id: int
    file_name: str


class AccountFileRepository:
    """Keep maintenance queries local without loading ORM relationships."""

    async def list_references(
        self, db: AsyncSession, before_id: int | None = None,
    ) -> list[ArchiveReference]:
        columns = Account.__table__.c
        stmt = select(columns.id, columns.file_name).where(
            columns.file_name.is_not(None), columns.file_name != "",
        )
        if before_id is not None:
            stmt = stmt.where(columns.id < before_id)
        result = await db.execute(stmt.order_by(columns.id.desc()).limit(
            BATCH_SIZE,
        ))
        return [ArchiveReference(*row) for row in result.all()]

    async def lock_references(
        self, db: AsyncSession, ids: Sequence[int],
    ) -> list[ArchiveReference]:
        columns = Account.__table__.c
        result = await db.execute(
            select(columns.id, columns.file_name)
            .where(columns.id.in_(ids), columns.file_name.is_not(None),
                   columns.file_name != "")
            .order_by(columns.id.desc()).with_for_update(),
        )
        return [ArchiveReference(*row) for row in result.all()]

    async def delete_accounts(
        self, db: AsyncSession, ids: Sequence[int],
    ) -> int:
        table = Account.__table__
        result = await db.execute(
            delete(table).where(table.c.id.in_(ids)).returning(table.c.id),
        )
        return len(result.all())


def _ensure_archive_directory(directory: Path) -> None:
    # Opening storage explicitly prevents an inaccessible root being counted
    # as a collection of missing files. An empty but readable root is valid.
    if not directory.is_dir():
        raise NotADirectoryError(f"Archive directory unavailable: {directory}")
    with os.scandir(directory) as entries:
        next(entries, None)


def _missing_references(
    directory: Path, rows: Sequence[ArchiveReference],
) -> list[ArchiveReference]:
    _ensure_archive_directory(directory)
    return [
        row for row in rows
        if row.file_name and not account_file_exists(directory, row.file_name)
    ]


async def scan_accounts(
    db: AsyncSession, directory: Path,
) -> list[ArchiveReference]:
    """Collect only exact missing references, using descending ID batches."""
    await asyncio.to_thread(_ensure_archive_directory, directory)
    repository = AccountFileRepository()
    missing: list[ArchiveReference] = []
    before_id = None
    while True:
        rows = await repository.list_references(db, before_id)
        if not rows:
            break
        missing.extend(await asyncio.to_thread(
            _missing_references, directory, rows,
        ))
        before_id = rows[-1].id
        if len(rows) < BATCH_SIZE:
            break
    await asyncio.to_thread(_ensure_archive_directory, directory)
    return missing


async def delete_missing_accounts(
    db: AsyncSession, directory: Path, candidates: Sequence[ArchiveReference],
) -> int:
    """Recheck approved references under locks; caller owns the transaction."""
    repository = AccountFileRepository()
    deleted = 0
    for offset in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[offset:offset + BATCH_SIZE]
        original_names = dict(batch)
        current = await repository.lock_references(
            db, [row.id for row in batch],
        )
        unchanged = [
            row for row in current
            if row.file_name == original_names[row.id]
        ]
        missing = await asyncio.to_thread(
            _missing_references, directory, unchanged,
        )
        if missing:
            deleted += await repository.delete_accounts(
                db, [row.id for row in missing],
            )
    await asyncio.to_thread(_ensure_archive_directory, directory)
    return deleted


async def run_scan(directory: Path) -> list[ArchiveReference]:
    from app.adapters.db.session import async_session, engine

    try:
        async with async_session() as db:
            return await scan_accounts(db, directory)
    finally:
        await engine.dispose()


async def run_deletion(
    directory: Path, candidates: Sequence[ArchiveReference],
) -> int:
    from app.adapters.db.session import async_session, engine

    try:
        async with async_session() as db:
            # One transaction for all batches: any failed deletion rolls back
            # earlier batches as well. No transaction is held during input.
            async with db.begin():
                deleted = await delete_missing_accounts(
                    db, directory, candidates,
                )
            return deleted
    finally:
        await engine.dispose()


def confirm_deletion(count: int) -> bool:
    try:
        answer = input(f"Удалить эти аккаунты из БД ({count})? [y/N]: ")
    except EOFError:
        return False
    return answer.strip().lower() == "y"


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None and _cli_args is not None:
        args = _cli_args
    else:
        args = _parse_args(argv)
    stage = "проверка"
    try:
        directory = args.upload_dir.expanduser().resolve()
        print(f"Каталог архивов: {directory}")
        print("Проверка аккаунтов всех пользователей...", flush=True)
        candidates = asyncio.run(run_scan(directory))
        print(f"Аккаунтов с отсутствующим точным файлом: {len(candidates)}")
        print("Пустой file_name исключён. "
              "Профили и альтернативы не проверяются.")
        if not candidates:
            print("Удалять нечего. БД не изменялась.")
            return 0
        print("ВНИМАНИЕ: удаляются записи аккаунтов, а не файлы на диске.")
        print("Каскады БД также удаляют связанные сессии, сообщения и логи.")
        print("Ссылки Android-устройств могут заблокировать всю операцию.")
        print("Проверьте каталог и остановите параллельные изменения "
              "аккаунтов и архивов перед подтверждением.")
        if not confirm_deletion(len(candidates)):
            print("Удаление отменено. БД не изменялась.")
            return 0
        stage = "удаление"
        deleted = asyncio.run(run_deletion(directory, candidates))
        print(f"Удалено аккаунтов из БД: {deleted}")
        skipped = len(candidates) - deleted
        print(f"Пропущено после повторной проверки: {skipped}")
        print("Файлы на диске не изменялись.")
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        print(f"\nОперация прервана: {stage}. При прерывании удаления "
              "проверьте итоговое состояние БД.", file=sys.stderr)
        return 130
    except IntegrityError:
        print(
            "\nУдаление заблокировано ограничениями целостности БД. "
            "Транзакция отменена. Проверьте ссылки на аккаунты, "
            "в том числе android.account_id.", file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            f"\nОшибка на этапе «{stage}»: {type(exc).__name__}. "
            "Проверьте настройки, доступность БД "
            "и права доступа к каталогу. "
            "Подробности исключения скрыты для защиты параметров подключения. "
            "Если удаление было подтверждено, "
            "проверьте итоговое состояние БД.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
