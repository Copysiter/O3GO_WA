import random
import string
import logging
import aiofiles
import uuid
import time

from typing import Any, Union
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

from fastapi import (
    Request, APIRouter, Depends, UploadFile, File, Form, HTTPException, status
)
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy import select, update, func, or_
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger, E

import app.deps as deps
import app.crud as crud
import app.models as models
import app.schemas as schemas

from app.models.session import AccountStatus, SessionStatus

def generate_auth_code(length=6):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))


UPLOAD_DIR = Path('upload/wa')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()


async def _unlink_with_status(
    session: AsyncSession,
    obj_in: schemas.AndroidAccountUnlinkRequest,
    user: schemas.User,
    status: int
) -> schemas.AndroidCodeResponse:
    try:
        async with session.begin():
            statement = (
                update(models.Android)
                .where (
                    models.Android.device == obj_in.device,
                    models.Android.user_id == user.id
                )
                .values(account_id=None)
                .returning(models.Android)
            )

            row = (await session.execute(statement)).first()
            if row is None:
                return {'code': '100', 'error': 'Device not found'}

            statement = (
                update(models.Account)
                .where(models.Account.id == int(obj_in.id_task))
                .values(
                    status=status,
                    sent=func.coalesce(models.Account.sent, 0) + (obj_in.sent or 0)  # noqa
                )
                .returning(models.Account)
            )

            row = (await session.execute(statement)).first()
            # if row is None:
            #     return {'code': '100', 'error': 'Task not found'}
            return {'code': '0'}
    except Exception as e:
        logging.exception(
            'Unlink account error'
            f'{type(e).__name__}: {str(e)}'
        )
        return {'code': '100', 'error': f'{type(e).__name__}: {e}'}


@router.post(
    '/',
    response_model = Union[
        schemas.AndroidAccountLinkResponse, schemas.AndroidCodeResponse
    ],
    status_code = status.HTTP_200_OK
)
async def link_account(
    *,
    session: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.AndroidAccountLinkRequest = \
            Depends(deps.as_form(schemas.AndroidAccountLinkRequest)),
    user = Depends(deps.get_user_by_api_key),
    request: Request
) -> Any:
    try:
        async with session.begin():
            row = await session.execute(
                select(models.Android)
                .where(
                    models.Android.device == obj_in.device,
                    models.Android.user_id == user.id
                )
                .with_for_update(of=models.Android)
            )
            android = row.scalars().first()
            if android is None:
                return {'code': '100', 'error': 'Device not found'}
            account = android.account
            if not account or account.status != AccountStatus.ACTIVE:
                A = aliased(models.Account)

                locked = (
                    select(A.id)
                    .where(
                        A.status == AccountStatus.AVAILABLE,
                        A.user_id == user.id,
                        or_(
                            A.update_ts.is_(None), A.cooldown.is_(None),
                            datetime.utcnow() > (
                                A.update_ts + func.make_interval(
                                    0, 0, 0, 0, 0, A.cooldown, 0
                                )
                            )
                        ),
                    )
                    .order_by(A.update_ts.asc().nullsfirst(), A.id.asc())
                    .limit(1)
                    .with_for_update(skip_locked=True)
                    .cte('locked')
                )

                statement = (
                    update(models.Account)
                    .where(
                        models.Account.id == select(locked.c.id).scalar_subquery()  # noqa
                    )
                    .values(
                        status=AccountStatus.ACTIVE,
                        update_ts=datetime.utcnow()
                    )
                    .returning(models.Account)
                )

                row = (await session.execute(statement)).first()
                if row is None:
                    return {'code': '100', 'error': 'Account not found'}
                account = row[0]

            android.account_id = account.id
            await session.flush()

            base = (
                request.headers.get("x-base-url") or str(request.base_url)
            ).strip()
            url = urljoin(
                base if base.endswith('/') else base + '/',
                f'ext/api/v1/account/{account.uuid}?x_api_key={user.ext_api_key}'  # noqa
            )

            return {
                'id_task': account.id,
                'cnt_msg_iteration': account.limit,
                'status': account.status,
                'url': url,
                'code': '0'
            }
    except Exception as e:
        logging.exception(
            'Link account error'
            f'{type(e).__name__}: {str(e)}'
        )
        return {'code': '100', 'error': f'{type(e).__name__}: {e}'}


@router.post(
    '/finish',
    response_model=schemas.AndroidCodeResponse,
    status_code=status.HTTP_200_OK
)
async def unlink_account(
    *,
    session: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.AndroidAccountUnlinkRequest = \
            Depends(deps.as_form(schemas.AndroidAccountUnlinkRequest)),
    user = Depends(deps.get_user_by_api_key),
) -> Any:
    return await _unlink_with_status(
        session, obj_in, user, AccountStatus.AVAILABLE
    )


@router.post(
    '/ban',
    response_model=schemas.AndroidCodeResponse,
    status_code=status.HTTP_200_OK
)
async def ban_account(
    *,
    session: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.AndroidAccountUnlinkRequest = \
            Depends(deps.as_form(schemas.AndroidAccountUnlinkRequest)),
    user = Depends(deps.get_user_by_api_key),
) -> Any:
    return await _unlink_with_status(
        session, obj_in, user, AccountStatus.BANNED
    )


@router.post("/upload")
async def upload_archive(
    *,
    file: UploadFile = File(...),
    phone: str | None = Form(None),
    task_id: str | None = Form(None),
    db: AsyncSession = Depends(deps.get_db),
    user = Depends(deps.get_user_by_api_key)
):
    """
    Upload Account Archive.
    """
    result = {"code": 0, "error": ""}

    if not file.filename.endswith('.tar.gz'):
        result = {
            "code": 1, "error": "The file must have a .tar.gz extension"
        }

    timestamp = int(time.time())
    if phone:
        file_name = f"{phone}_{timestamp}.tar.gz"
    else:
        # Используем исходное имя файла, если phone не передан
        file_name = file.filename
    
    file_path = UPLOAD_DIR / file_name

    # Сохранение файла
    try:
        content = await file.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
    except Exception as e:
        result = {"code": 1, "error": f"Failed to save file: {e}"}

    # Добавление записи в БД
    await crud.account.create(
        db=db, obj_in=schemas.AccountCreate(
            uuid=str(uuid.uuid4()), user_id=user.id, file_name=file_name
        ).model_dump(exclude_unset=False)
    )

    return JSONResponse(result)


@router.get("/{uuid}")
async def download_archive(
    *,
    db: AsyncSession = Depends(deps.get_db), uuid: str,
    _ = Depends(deps.get_user_by_api_key)
):
    account = await crud.account.get_by(db=db, uuid=uuid)
    if not account:
        return {'code': '100','error': f'Archive with UUID={uuid} not found'}
    if not account.file_name:
        return {'code': '100', 'error': 'Archive filename not specified'}

    file_path = UPLOAD_DIR / account.file_name

    if not file_path.exists():
        return {'code': '100', 'error': f'Filen {file_path} not found'}

    return FileResponse(
        path=file_path, filename=account.file_name,
        media_type='application/gzip'
    )
