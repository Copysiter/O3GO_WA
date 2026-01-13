import uuid
import time
import aiofiles

from typing import Any
from pathlib import Path
from urllib.parse import urljoin

from fastapi import (
    Request, APIRouter, Depends, UploadFile, File, HTTPException, status
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger, E

import app.deps as deps
import app.crud as crud
import app.schemas as schemas


UPLOAD_DIR = Path('upload/wa')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_UPLOAD_DIR = Path('upload/wa/profile')
PROFILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()


@router.post(
    '/upload',
    response_model=schemas.Account,
    status_code=status.HTTP_201_CREATED
)
async def upload_archive(
    *,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_user_by_api_key),
    obj_in: schemas.AccountUpload = \
            Depends(deps.as_form(schemas.AccountUpload))
) -> Any:
    """
    Загрузка архива аккаунта.
    
    Принимает файл и все поля AccountCreate для создания записи в БД.
    """
    try:
        # Проверка расширения файла
        if not file.filename.endswith('.tar.gz'):
            logger.warning(
                f'Invalid file extension: {file.filename}',
                event=E.SYSTEM.API.FAILURE,
                extra={'user_id': user.id, 'filename': file.filename}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The file must have a .tar.gz extension"
            )
        
        # Генерация имени файла
        timestamp = int(time.time())
        if obj_in.number:
            file_name = f"{obj_in.number}_{timestamp}.tar.gz"
        else:
            file_name = file.filename
        
        file_path = UPLOAD_DIR / file_name
        
        logger.info(
            f'Uploading account archive',
            event=E.SYSTEM.API.REQUEST,
            extra={
                'user_id': user.id,
                'file_name': file_name,
                'number': obj_in.number
            }
        )
        
        # Сохранение файла
        content = await file.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        # Обновляем данные для создания записи
        account_data = obj_in.model_dump(exclude_unset=True)
        account_data.update({
            'uuid': uuid.uuid4(),
            'user_id': user.id,
            'file_name': file_name
        })
        
        # Создание записи в БД
        account = await crud.account.create(
            db=session,
            obj_in=account_data
        )
        
        logger.info(
            'Account archive uploaded successfully',
            event=E.SYSTEM.API.RESPONSE,
            extra={
                'user_id': user.id,
                'account_id': account.id,
                'account_uuid': str(account.uuid),
                'file_name': file_name
            }
        )
        
        return schemas.Account.model_validate(account)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f'Upload archive error: {type(e).__name__}: {str(e)}',
            event=E.SYSTEM.API.ERROR, extra={
                'user_id': user.id, 'file_name': file.filename,
                'error': {'type': type(e).__name__, 'msg': str(e)}
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {e}"
        )


@router.get(
    '/',
    response_model=schemas.Account,
    status_code=status.HTTP_200_OK
)
async def get_account(
    *,
    session: AsyncSession = Depends(deps.get_db),
    filter: schemas.AccountFilter = Depends(),
    user=Depends(deps.get_user_by_api_key),
    request: Request
) -> Any:
    """
    Получить аккаунт по фильтрам.

    Возвращает первый найденный аккаунт со ссылкой на скачивание архива.
    """
    try:
        # Добавляем фильтр по user_id
        if not filter.user_id:
            filter.user_id = user.id

        # Получаем список аккаунтов с лимитом 1
        accounts = await crud.account.list(
            db=session,
            filter=filter,
            skip=0,
            limit=1
        )

        if not accounts:
            logger.warning(
                'Account not found',
                event=E.SYSTEM.API.NOT_FOUND,
                extra={'user_id': user.id, 'filter': filter.model_dump()}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Account not found'
            )

        account = accounts[0]

        # Формируем URL для скачивания
        base = (
            request.headers.get("x-base-url") or str(request.base_url)
        ).strip()
        download_url = urljoin(
            base if base.endswith('/') else base + '/',
            f'ext/api/v1/account/{account.uuid}?x_api_key={user.ext_api_key}'
        )
        profile_download_url = urljoin(
            base if base.endswith('/') else base + '/',
            f'ext/api/v1/account/profile/{account.uuid}?x_api_key={user.ext_api_key}'
        )

        # Конвертируем ORM объект в схему Account с download_url
        account_dict = schemas.Account.model_validate(account).model_dump()
        if account.file_name:
            account_dict['download_url'] = download_url
        if account.profile_file_name:
            account_dict['profile_download_url'] = profile_download_url

        logger.info(
            'Account retrieved successfully',
            event=E.SYSTEM.API.RESPONSE,
            extra={
                'user_id': user.id,
                'account_id': account.id,
                'account_uuid': str(account.uuid)
            }
        )

        return schemas.Account(**account_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f'Get account error: {type(e).__name__}: {str(e)}',
            event=E.SYSTEM.API.ERROR, extra={
                'user_id': user.id,
                'error': {'type': type(e).__name__, 'msg': str(e)}
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'{type(e).__name__}: {str(e)}'
        )


@router.get("/{uuid}")
async def download_archive(
    *,
    session: AsyncSession = Depends(deps.get_db),
    uuid: str,
    user=Depends(deps.get_user_by_api_key)
):
    """
    Скачивание архива аккаунта по UUID.
    """
    try:
        account = await crud.account.get_by(db=session, uuid=uuid)
        
        if not account:
            logger.warning(
                f'Archive not found by UUID',
                event=E.SYSTEM.API.NOT_FOUND,
                extra={'user_id': user.id, 'uuid': uuid}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Archive with UUID={uuid} not found'
            )
        
        if not account.file_name:
            logger.warning(
                'Archive filename not specified',
                event=E.SYSTEM.API.FAILURE,
                extra={'user_id': user.id, 'account_id': account.id}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Archive filename not specified'
            )
        
        file_path = UPLOAD_DIR / account.file_name
        
        if not file_path.exists():
            logger.error(
                f'Archive file not found on disk',
                event=E.SYSTEM.API.ERROR,
                extra={
                    'user_id': user.id,
                    'account_id': account.id,
                    'file_path': str(file_path)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'File {file_path} not found'
            )
        
        logger.info(
            'Archive download initiated',
            event=E.SYSTEM.API.RESPONSE,
            extra={
                'user_id': user.id,
                'account_id': account.id,
                'file_name': account.file_name
            }
        )
        
        return FileResponse(
            path=file_path,
            filename=account.file_name,
            media_type='application/gzip'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f'Download archive error: {type(e).__name__}: {str(e)}',
            event=E.SYSTEM.API.ERROR, extra={
                'user_id': user.id, 'uuid': uuid,
                'error': {'type': type(e).__name__, 'msg': str(e)}
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'{type(e).__name__}: {str(e)}'
        )


@router.get("/profile/{uuid}")
async def download_archive(
    *,
    session: AsyncSession = Depends(deps.get_db),
    uuid: str,
    user=Depends(deps.get_user_by_api_key)
):
    """
    Скачивание текстового файла профиля по UUID.
    """
    try:
        account = await crud.account.get_by(db=session, uuid=uuid)

        if not account:
            logger.warning(
                f'Profile not found by UUID',
                event=E.SYSTEM.API.NOT_FOUND,
                extra={'user_id': user.id, 'uuid': uuid}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Profile with UUID={uuid} not found'
            )

        if not account.profile_file_name:
            logger.warning(
                'Profile filename not specified',
                event=E.SYSTEM.API.FAILURE,
                extra={'user_id': user.id, 'account_id': account.id}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Profile filename not specified'
            )

        file_path = PROFILE_UPLOAD_DIR / account.profile_file_name

        if not file_path.exists():
            logger.error(
                f'Profile file not found on disk',
                event=E.SYSTEM.API.ERROR,
                extra={
                    'user_id': user.id,
                    'account_id': account.id,
                    'file_path': str(file_path)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'File {file_path} not found'
            )

        logger.info(
            'Profile download initiated',
            event=E.SYSTEM.API.RESPONSE,
            extra={
                'user_id': user.id,
                'account_id': account.id,
                'file_name': account.profile_file_name
            }
        )

        return FileResponse(
            path=file_path,
            filename=account.profile_file_name,
            media_type='application/gzip'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f'Download profile error: {type(e).__name__}: {str(e)}',
            event=E.SYSTEM.API.ERROR, extra={
                'user_id': user.id, 'uuid': uuid,
                'error': {'type': type(e).__name__, 'msg': str(e)}
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'{type(e).__name__}: {str(e)}'
        )
