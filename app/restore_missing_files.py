"""Restore missing account archive references, without changing any files.

Preview in the application environment:
    docker compose exec api python /app/restore_missing_files.py --dry-run

The same command without --dry-run updates the database. Run only after a
backup and with other archive-reference writers stopped. Each account has its
own transaction; a failure stops the run but does not undo earlier commits.
No archive contents are read and no application lifespan or jobs are started.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, TextIO

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import missing_files as base  # noqa: E402
from app.missing_files_alt import _index_archives  # noqa: E402
from app.utils.account_files import account_file_exists  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


SCAN_BATCH_SIZE = base.SCAN_BATCH_SIZE


@dataclass(frozen=True, slots=True)
class RestoreAssignment:
    account_id: int
    old_file_name: str
    new_file_name: str
    dry_run: bool


@dataclass(frozen=True, slots=True)
class RestoreIssue:
    stage: str
    error_type: str
    account_id: int | None = None
    old_file_name: str | None = None
    new_file_name: str | None = None
    db_outcome: str = "not_committed"


@dataclass
class RestoreSummary:
    checked: int = 0
    missing: int = 0
    restored: int = 0
    planned: int = 0
    no_candidate: int = 0
    changed: int = 0
    unavailable_files: int = 0
    errors: int = 0
    unknown_commits: int = 0
    failure: RestoreIssue | None = None
    cleanup_errors: list[str] = field(default_factory=list)

    @property
    def present(self) -> int:
        return self.checked - self.missing


def _ensure_directory(directory: Path) -> None:
    if not directory.is_dir():
        raise NotADirectoryError("Account archive storage is unavailable")


def _index_restore_archives(directory: Path) -> dict[str, list[str]]:
    """Index safe root files once and order candidates by numeric timestamp."""
    from app.missing_files_full import parse_archive_timestamp

    result: dict[str, list[str]] = {}
    for number, names in _index_archives(directory).items():
        candidates = []
        for name in names:
            timestamp = parse_archive_timestamp(name)
            if timestamp is not None:
                candidates.append((timestamp, name))
        if candidates:
            result[number] = [name for _, name in sorted(candidates)]
    return result


def _missing_file_ids(
    directory: Path, rows: Sequence[tuple[int, str | None, str]],
) -> set[int]:
    _ensure_directory(directory)
    return {
        account_id for account_id, _, file_name in rows
        if file_name and not account_file_exists(directory, file_name)
    }


def _check_file_pair(
    directory: Path, old_file_name: str, new_file_name: str,
) -> tuple[bool, bool]:
    _ensure_directory(directory)
    return (
        account_file_exists(directory, old_file_name),
        account_file_exists(directory, new_file_name),
    )


def _record_failure(
    summary: RestoreSummary,
    error: BaseException,
    *,
    stage: str,
    account_id: int | None = None,
    old_file_name: str | None = None,
    new_file_name: str | None = None,
    db_outcome: str = "not_committed",
) -> None:
    """Retain the first failure without exception messages or DB parameters."""
    if summary.failure is None:
        summary.errors += 1
        summary.unknown_commits += int(db_outcome == "unknown")
        summary.failure = RestoreIssue(
            stage=stage, error_type=type(error).__name__,
            account_id=account_id, old_file_name=old_file_name,
            new_file_name=new_file_name, db_outcome=db_outcome,
        )


async def _await_cleanup(
    operation: Callable[[], Awaitable[None]],
    summary: RestoreSummary,
    *,
    stage: str,
) -> BaseException | None:
    """Finish cleanup despite repeated caller cancellation; retain first error.

    Keep a strong task reference and rejoin it after every cancelled shield.
    The caller decides whether to propagate this error or its original one.
    """
    first_error = None

    def remember(error: BaseException) -> None:
        nonlocal first_error
        summary.cleanup_errors.append(f"{stage}: {type(error).__name__}")
        if first_error is None:
            first_error = error
        _record_failure(
            summary, error, stage=stage,
            db_outcome="committed" if summary.restored else "not_committed",
        )

    async def finish() -> None:
        try:
            await operation()
        except (Exception, asyncio.CancelledError, KeyboardInterrupt) as error:
            remember(error)

    task = asyncio.create_task(finish())
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            remember(error)
    task.result()
    return first_error


async def restore_accounts(
    db: AsyncSession,
    directory: Path,
    *,
    dry_run: bool = False,
    summary: RestoreSummary | None = None,
    on_assignment: Callable[[RestoreAssignment], None] | None = None,
) -> RestoreSummary:
    """Restore sequentially; reserve candidates only after confirmed commit."""
    from app.crud.account import account

    summary = summary if summary is not None else RestoreSummary()
    stage = "storage"
    account_id = None
    old_file_name = None
    new_file_name = None
    db_outcome = "not_committed"
    try:
        await asyncio.to_thread(_ensure_directory, directory)
        used_names: set[str] = set()
        before_id = None
        stage = "read_references"
        while True:
            await db.begin()
            references = await account.list_archive_files(
                db, before_id=before_id, limit=SCAN_BATCH_SIZE
            )
            await db.commit()
            used_names.update(name for _, name in references if name)
            if len(references) < SCAN_BATCH_SIZE:
                break
            before_id = references[-1][0]

        stage = "index"
        archives = await asyncio.to_thread(_index_restore_archives, directory)
        before_id = None
        while True:
            stage = "read_accounts"
            account_id = old_file_name = new_file_name = None
            db_outcome = "not_committed"
            await db.begin()
            rows = await account.list_archive_restore_candidates(
                db, before_id=before_id, limit=SCAN_BATCH_SIZE
            )
            await db.commit()
            if not rows:
                break
            stage = "check_files"
            missing_ids = await asyncio.to_thread(
                _missing_file_ids, directory, rows
            )

            for account_id, number, old_file_name in rows:
                new_file_name = None
                db_outcome = "not_committed"
                if not old_file_name:
                    continue
                summary.checked += 1
                if account_id not in missing_ids:
                    continue
                summary.missing += 1
                if not number or base._file_prefix(old_file_name) != number:
                    summary.no_candidate += 1
                    continue

                choices = archives.get(number, [])
                while choices:
                    new_file_name = choices[-1]
                    if new_file_name in used_names:
                        choices.pop()
                        continue
                    stage = "check_candidate"
                    old_exists, new_exists = await asyncio.to_thread(
                        _check_file_pair, directory,
                        old_file_name, new_file_name,
                    )
                    if old_exists:
                        summary.changed += 1
                        break
                    if not new_exists:
                        summary.unavailable_files += 1
                        choices.pop()
                        continue

                    stage = "verify_reference"
                    await db.begin()
                    current = await account.get_archive_file_name(
                        db, account_id=account_id
                    )
                    if current != old_file_name:
                        await db.commit()
                        summary.changed += 1
                        break
                    referenced = await account.is_file_referenced(
                        db, file_name=new_file_name
                    )
                    if referenced:
                        await db.commit()
                        used_names.add(new_file_name)
                        choices.pop()
                        continue

                    if dry_run:
                        await db.commit()
                        summary.planned += 1
                    else:
                        stage = "update"
                        returned = await account.restore_archive_file(
                            db, account_id=account_id,
                            old_file_name=old_file_name,
                            new_file_name=new_file_name,
                        )
                        if returned is None:
                            await db.rollback()
                            summary.changed += 1
                            break
                        stage = "verify_returning"
                        if returned != (account_id, new_file_name):
                            raise RuntimeError("Unexpected restore result")
                        stage = "commit"
                        db_outcome = "unknown"
                        await db.commit()
                        db_outcome = "committed"
                        summary.restored += 1

                    used_names.add(new_file_name)
                    choices.pop()
                    stage = "report"
                    if on_assignment is not None:
                        await asyncio.to_thread(
                            on_assignment,
                            RestoreAssignment(
                                account_id, old_file_name,
                                new_file_name, dry_run,
                            ),
                        )
                    break
                else:
                    summary.no_candidate += 1

            before_id = rows[-1][0]
            if len(rows) < SCAN_BATCH_SIZE:
                break
        stage = "storage_final_check"
        account_id = old_file_name = new_file_name = None
        db_outcome = "not_committed"
        await asyncio.to_thread(_ensure_directory, directory)
        return summary
    except (Exception, asyncio.CancelledError, KeyboardInterrupt) as error:
        _record_failure(
            summary, error, stage=stage, account_id=account_id,
            old_file_name=old_file_name, new_file_name=new_file_name,
            db_outcome=db_outcome,
        )
        if db.in_transaction():
            await _await_cleanup(db.rollback, summary, stage="rollback")
        raise


async def run_restore(
    directory: Path,
    *,
    dry_run: bool = False,
    summary: RestoreSummary | None = None,
    on_assignment: Callable[[RestoreAssignment], None] | None = None,
) -> RestoreSummary:
    """Own the session and engine cleanup without masking the primary error."""
    from app.adapters.db.session import async_session, engine

    summary = summary if summary is not None else RestoreSummary()
    db = None
    primary_error = None
    stage = "open_session"
    try:
        db = async_session()
        stage = "restore"
        return await restore_accounts(
            db, directory, dry_run=dry_run, summary=summary,
            on_assignment=on_assignment,
        )
    except BaseException as error:
        primary_error = error
        _record_failure(summary, error, stage=stage)
        raise
    finally:
        cleanup_error = None
        for label, resource in (("close", db), ("dispose", engine)):
            if resource is None:
                continue
            error = await _await_cleanup(
                getattr(resource, label), summary, stage=label,
            )
            if cleanup_error is None:
                cleanup_error = error
        if primary_error is None and cleanup_error is not None:
            raise cleanup_error


class _RestoreArgumentParser(argparse.ArgumentParser):
    """Keep argparse exit statuses even when its output stream fails."""

    def print_help(self, file: TextIO | None = None) -> None:
        stream = sys.stdout if file is None else file
        try:
            # argparse can swallow write errors, including unbuffered EPIPE.
            stream.write(self.format_help())
            stream.flush()
        except OSError:
            raise SystemExit(1) from None

    def error(self, message: str) -> None:
        try:
            super().error(message)
        except OSError:
            # A usage write may fail before argparse gets to exit(2).
            raise SystemExit(2) from None


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = _RestoreArgumentParser(
        description="Восстановление отсутствующих файловых ссылок аккаунтов.",
        epilog=(
            "Без --dry-run изменяет БД. Требуются резервная копия "
            "и отсутствие параллельных изменений ссылок. "
            "Архивы не изменяются."
        ),
    )
    parser.add_argument(
        "--upload-dir", type=Path, default=base.DEFAULT_UPLOAD_DIR,
        help="Каталог архивов (по умолчанию: app/upload/wa).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Показать назначения без изменения БД.",
    )
    return parser.parse_args(argv)


def _print_assignment(assignment: RestoreAssignment) -> None:
    print(json.dumps(asdict(assignment), ensure_ascii=True), flush=True)


def _print_summary(
    summary: RestoreSummary,
    *,
    partial: bool = False,
    stream: TextIO | None = None,
) -> None:
    stream = sys.stdout if stream is None else stream
    print("\nЧАСТИЧНЫЙ ИТОГ" if partial else "\nИТОГИ", file=stream)
    for label, value in (
        ("Проверено аккаунтов с file_name", summary.checked),
        ("Точный файл существует", summary.present),
        ("Точный файл отсутствует", summary.missing),
        ("Восстановлено (commit подтверждён)", summary.restored),
        ("Запланировано без записи", summary.planned),
        ("Нет свободной подходящей альтернативы", summary.no_candidate),
        ("Пропущено изменившихся аккаунтов/файлов", summary.changed),
        ("Кандидатов исчезло до назначения", summary.unavailable_files),
        ("Ошибок", summary.errors),
        ("Неподтверждённых commit", summary.unknown_commits),
    ):
        print(f"{label}: {base._count(value)}", file=stream)
    if summary.failure is not None:
        issue_json = json.dumps(asdict(summary.failure), ensure_ascii=True)
        print(
            "Ошибка: " + issue_json,
            file=stream,
        )
    for error in summary.cleanup_errors:
        print(f"Дополнительная ошибка: {error}", file=stream)


def _print_report(
    summary: RestoreSummary,
    *,
    stream: TextIO,
    exit_code: int,
    dry_run: bool,
    started: float,
) -> None:
    _print_summary(summary, partial=exit_code != 0, stream=stream)
    print(f"Время выполнения: {monotonic() - started:.1f} с.", file=stream)
    if exit_code:
        print(
            "Проход остановлен. Ранее подтверждённые изменения не отменены.",
            file=stream,
        )
        print("Тексты исключений и параметры подключения не выводятся.",
              file=stream)
    if dry_run:
        print("Предпросмотр: записывающий SQL не выполнялся.", file=stream)
    print(
        "Файлы архивов не изменялись. Проверка не является атомарным снимком.",
        file=stream,
    )
    stream.flush()


def _finalize_output(
    summary: RestoreSummary,
    *,
    exit_code: int,
    dry_run: bool,
    started: float,
    stdout_failed: bool,
) -> int:
    """Flush the report, falling back once to stderr without masking errors."""
    streams = [("stdout", sys.stdout), ("stderr", sys.stderr)]
    for stage, stream in streams[1:] if stdout_failed else streams:
        try:
            _print_report(
                summary, stream=stream, exit_code=exit_code,
                dry_run=dry_run, started=started,
            )
            return exit_code
        except (Exception, asyncio.CancelledError, KeyboardInterrupt) as error:
            if summary.failure is not None:
                summary.cleanup_errors.append(
                    f"{stage}: {type(error).__name__}",
                )
            _record_failure(
                summary, error, stage=stage,
                db_outcome=(
                    "committed" if summary.restored else "not_committed"
                ),
            )
            if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)):
                exit_code = 130
            elif exit_code == 0:
                exit_code = 1
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 on success, 1 on failure, 2 for arguments or 130 on abort."""
    args = _parse_args(argv)
    started = monotonic()
    summary = RestoreSummary()
    exit_code = 0
    stdout_failed = False
    stage = "initialization"

    def on_assignment(assignment: RestoreAssignment) -> None:
        nonlocal stdout_failed
        try:
            _print_assignment(assignment)
        except (Exception, asyncio.CancelledError, KeyboardInterrupt):
            stdout_failed = True
            raise

    try:
        directory = args.upload_dir.expanduser().resolve()
        stage = "stdout"
        print("\nВОССТАНОВЛЕНИЕ ФАЙЛОВЫХ ССЫЛОК АККАУНТОВ")
        print(f"Каталог: {directory}")
        print("Режим: ПРЕДПРОСМОТР, БД не изменяется" if args.dry_run else (
            "Режим: ЗАПИСЬ В БД, отдельный commit для каждого аккаунта"
        ))
        print("Выбор: максимальный timestamp среди файлов без ссылок в БД.")
        print(
            "Обход: id DESC; архивы не читаются, не удаляются и не меняются."
        )
        stage = "restore"
        asyncio.run(run_restore(
            directory, dry_run=args.dry_run, summary=summary,
            on_assignment=on_assignment,
        ))
    except (KeyboardInterrupt, asyncio.CancelledError) as error:
        _record_failure(summary, error, stage="interrupted")
        exit_code = 130
    except Exception as error:
        _record_failure(
            summary, error, stage=stage,
            db_outcome="committed" if summary.restored else "not_committed",
        )
        exit_code = 1

    return _finalize_output(
        summary, exit_code=exit_code, dry_run=args.dry_run, started=started,
        stdout_failed=stdout_failed or stage == "stdout",
    )


def _entrypoint() -> int:
    """Prevent shutdown flush errors from replacing the CLI status with 120.

    Only the executable entrypoint redirects broken OS descriptors. Embedding
    callers of main retain their streams, including custom in-memory streams.
    """
    try:
        exit_code = main()
    except SystemExit as error:
        if error.code is None:
            exit_code = 0
        elif isinstance(error.code, int):
            exit_code = error.code
        else:
            exit_code = 1
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except OSError:
            # main/argparse already attempted output. Do not print another
            # error to a failed stream or expose the exception's message.
            if exit_code == 0:
                exit_code = 1
            null_fd = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(null_fd, stream.fileno())
            finally:
                os.close(null_fd)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(_entrypoint())
