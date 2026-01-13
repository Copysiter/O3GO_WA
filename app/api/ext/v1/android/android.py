import json
import random
import string

from datetime import datetime
from typing import Any
from pathlib import Path
from urllib.parse import urljoin

from fastapi import (
    Request, APIRouter, Depends, Form, HTTPException, status
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger, E
from app.services.message import MessageService

import app.deps as deps
import app.crud as crud
import app.schemas as schemas


def generate_auth_code(length=6):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))


UPLOAD_DIR = Path('upload/apk')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()


@router.post(
    '/reg',
    response_model=schemas.AndroidRegResponse,
    status_code=status.HTTP_200_OK
)
async def reg_device(
    *,
    db: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.AndroidCreate = \
            Depends(deps.as_form(schemas.AndroidCreate)),
    user = Depends(deps.get_user_by_api_key),
    request: Request
) -> Any:
    """
    Register new Device.
    """
    db_obj = await crud.android.get_by(db=db, device=obj_in.device)
    if not db_obj:
        obj_in.user_id = user.id
        db_obj = await crud.android.create(db=db, obj_in=obj_in)
    version = await crud.version.get_last(db=db)
    response = schemas.AndroidRegResponse(id_device=db_obj.id)
    if version:
        response.version = version.id
        base = (
            request.headers.get("x-base-url") or str(request.base_url)
        ).strip()
        response.apk_url = urljoin(
            base if base.endswith('/') else base + '/',
            f'ext/api/v1/android/apk?x_api_key={user.ext_api_key}'
        )
    return response


@router.post(
    '/power',
    response_model=schemas.AndroidCodeResponse,
    status_code=status.HTTP_200_OK
)
async def power_device(
    *,
    db: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.AndroidPowerRequest = \
        Depends(deps.as_form(schemas.AndroidPowerRequest)),
    _ = Depends(deps.get_user_by_api_key),
) -> Any:
    """
    Power Device.
    """
    db_obj = await crud.android.get_by(db=db, device=obj_in.device)
    if not db_obj:
        raise HTTPException(
            status_code=404, detail='Android Device not found'
        )
    _ = await crud.android.update(
        db=db, db_obj=db_obj, obj_in={
            'is_active': bool(obj_in.power)
        }
    )
    return schemas.AndroidCodeResponse(code='0')


@router.post(
    '/messages',
    response_model=schemas.AndroidMessageResponse,
    status_code=status.HTTP_200_OK
)
async def get_messages(
    *,
    db: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.AndroidMessageRequest = \
            Depends(deps.as_form(schemas.AndroidMessageRequest)),
    user = Depends(deps.get_user_by_api_key),
) -> Any:
    """
    Get Messages.
    """
    try:
        db_obj = await crud.android.get_by(db=db, device=obj_in.device)
        if not db_obj:
            raise HTTPException(
                status_code=404, detail='Android Device not found'
            )
        
        # Call external message API
        message_service = MessageService()
        message = await message_service.get_next_message(
            device=obj_in.device,
            api_key=user.ext_api_key,
            status="sent"
        )
        
        # Transform response to required format
        if message:
            return schemas.AndroidMessageResponse(
                **db_obj.to_dict(),
                data=[schemas.AndroidMessage(
                    id=message.id,
                    phone=message.phone,
                    msg=message.text,
                    is_send_to_phone=0,
                    is_deliv=0
                )]
            )
        else:
            return schemas.AndroidMessageResponse(data=[])
            
    except Exception as e:
        logger.exception(
            f'Android get_messages error: {e}',
            event=E.EXTERNAL.SERVICE.ERROR
        )
        return schemas.AndroidMessageResponse(data=[])


@router.post(
    '/message/confirm',
    response_model=schemas.AndroidCodeResponse,
    status_code=status.HTTP_200_OK
)
async def confirm_message(
    *,
    db: AsyncSession = Depends(deps.get_db),
    device: str = Form(...),
    param_json: str = Form(...),
    _ = Depends(deps.get_user_by_api_key),
) -> Any:
    """
    Confirm message receive.
    """
    if False:
        for obj in json.loads(param_json):
            campaign_dst = \
                await crud.campaign_dst.get(db=db, id=obj.get('id'))
            if not campaign_dst:
                raise HTTPException(
                    status_code=404, detail='Message not found'
                )
            _ = await crud.campaign_dst.update(
                db=db, db_obj=campaign_dst, obj_in={
                    'status': schemas.CampaignDstStatus.SENT,
                    'sent_ts': datetime.utcnow()
                }
            )
    return schemas.AndroidCodeResponse(code='0')


@router.post(
    '/message/status',
    response_model=schemas.AndroidCodeResponse,
    status_code=status.HTTP_200_OK
)
async def set_message_status(
    *,
    device: str = Form(...),
    param_json: str = Form(...),
    user = Depends(deps.get_user_by_api_key)
) -> Any:
    """
    Set message status.
    """
    try:
        items = json.loads(param_json)
        message_service = MessageService()
        
        for obj in items:
            message_id = obj.get('id')
            if not message_id:
                continue
            
            # Determine status based on fields
            status = None
            if obj.get('date_deliv'):
                status = 'delivered'
            elif obj.get('date_error'):
                status = 'failed'
            elif obj.get('date_send'):
                status = 'sent'
            
            if not status:
                continue
            
            # Call external API to update message status
            result = await message_service.set_message_status(
                message_id=message_id,
                status=status,
                api_key=user.ext_api_key,
                src_addr=None
            )
            
            if not result:
                logger.warning(
                    f'Failed to update message {message_id} status to {status}',
                    event=E.EXTERNAL.SERVICE.FAILURE
                )
        
        return schemas.AndroidCodeResponse(code='0')
        
    except Exception as e:
        error = f'{type(e).__name__}: {e}'
        logger.exception(
            f'Android set status error - {error}',
            event=E.EXTERNAL.SERVICE.ERROR
        )
        return schemas.AndroidCodeResponse(code='100', error=error)


@router.get("/apk")
async def download_apk(
    *,
    db: AsyncSession = Depends(deps.get_db),
    _ = Depends(deps.get_user_by_api_key)
):
    version = await crud.version.get_last(db=db)
    if not version:
        raise HTTPException(status_code=404, detail="Apk Version not found")
    if not version.file_name:
        raise HTTPException(
            status_code=404, detail="Apk filename not specified"
        )

    file_path = UPLOAD_DIR / version.file_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Apk File not found")

    return FileResponse(
        path=file_path,
        filename=version.file_name,
        media_type="application/vnd.android.package-archive"
    )