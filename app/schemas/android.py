from typing import List, Dict
from pydantic import BaseModel, Field, ConfigDict, model_serializer
from datetime import datetime

from app.crud.filter.sqlalchemy import Filter
from app.models.android import Android as AndroidModel

from .user import User



class AndroidBase(BaseModel):
    """Базовая схема Android приложения с общими полями"""
    type: str | None = Field(
        None, description="Тип устройства (1 - WhatsApp, 2 - WhatsApp бизнес)"
    )
    device: str | None = Field(
        None, description="Уникальный ID устройства "
    )
    device_origin: str | None = Field(
        None, description="Уникальный ID для данного приложения"
    )
    device_name: str | None = Field(
        None, description="Название устройства"
    )
    manufacturer: str | None = Field(
        None, description="Производитель телефона"
    )
    version: str | None = Field(None, description="Версия приложения")
    android_version: str | None = Field(None, description="Версия Android")
    operator_name: str | None = Field(None, description="Оператор")
    bat: str | None = Field(None, description="Уровень заряда")
    charging: str | None = Field(
        None, description="Статус зарядки (1 - заряжается)"
    )
    push_id: str | None = Field(None, description="Push ID")
    info_data: str | None = Field(None, description="Подробна информация")
    user_id: int | None = Field(None, description="ID учетной записи")
    # auth_code: str | None = Field(None, description="Код авторизации")
    is_active: bool | None = Field(None, description="Активность девайса")
    model_config = ConfigDict(
        json_schema_extra={
            'example': {
                "manufacturer": "Google",
                "device_name": "sdk_gphone64_arm64 [WhatsApp]",
                "dop_name": "",
                "device": "3df3bda5-7fbd-400c-901b-7baccb875bd8-WA",
                "device_origin": "3df3bda5-7fbd-400c-901b-7baccb875bd8",
                "domain": "",
                "version": "1",
                "android_version": "14",
                "operator_name": "WhatsApp",
                "bat": "100",
                "charging": "0",
                "push_id": "cL_yw9zgL9slLrwLocguti",
                "info_data": "",
                "type": "1"
            }
        }
    )


class AndroidCreate(AndroidBase):
    """Схема для создания нового Android приложения"""
    device: str = Field(None, description="Уникальный ID устройства ")
    device_origin: str = Field(
        None, description="Уникальный ID для данного приложения"
    )
    type: str = Field(
        None, description="Тип устройства (1 - WhatsApp, 2 - WhatsApp бизнес)"
    )


class AndroidUpdate(AndroidBase):
    """Схема для обновления существующего Android приложения"""
    pass


class AndroidInDBBase(AndroidBase):
    """Базовая схема Android приложения с ID, используемая при работе с БД"""
    id: int = Field(None, description="Уникальный идентификатор")

    class Config:
        from_attributes = True


class Android(AndroidInDBBase):
    """Схема Android приложения, возвращаемая из API"""
    user: User


class AndroidInDB(AndroidInDBBase):
    """Схема Android приложения, используемая только внутри приложения"""
    pass


class AndroidRows(BaseModel):
    """Схема списка Android приложений с общим количеством записей"""
    data: List[Android]
    total: int = 0


class AndroidFilter(Filter):
    """Фильтр поиска Android приложений по различным полям модели"""
    id: int | None = None
    id__neq: int | None = None
    id__in: list[int] | None = None
    id__gt: int | None = None
    id__lt: int | None = None

    user_id: int | None = None
    user_id__neq: int | None = None
    user_id__in: list[int] | None = None

    device: str | None = None
    device__neq: str | None = None
    device__in: list[str] | None = None
    device__ilike: str | None = None

    device_origin: str | None = None
    device_origin__neq: str | None = None
    device_origin__in: list[str] | None = None
    device_origin__ilike: str | None = None

    device_name: str | None = None
    device_name__neq: str | None = None
    device_name__in: list[str] | None = None
    device_name__ilike: str | None = None

    manufacturer: str | None = None
    manufacturer__neq: str | None = None
    manufacturer__in: list[str] | None = None
    manufacturer__ilike: str | None = None

    version: str | None = None
    version__neq: str | None = None
    version__in: list[str] | None = None
    version__ilike: str | None = None

    android_version: str | None = None
    android_version__neq: str | None = None
    android_version__in: list[str] | None = None
    android_version__ilike: str | None = None

    operator_name: str | None = None
    operator_name__neq: str | None = None
    operator_name__in: list[str] | None = None
    operator_name__ilike: str | None = None

    push_id: str | None = None
    push_id__neq: str | None = None
    push_id__in: list[str] | None = None
    push_id__ilike: str | None = None

    is_active: bool | None = None

    order_by: list[str] | None = None

    class Constants(Filter.Constants):
        model = AndroidModel

        # имя поля сортировки, совпадающий с атрибутом схемы
        ordering_field_name = "order_by"


class AndroidMessage(BaseModel):
    """Базовая схема сообщения в Android приложении"""
    id: int = Field(None, description="Идентификатор сообщения")
    phone: str = Field(None, description="Номер телефона получателя")
    msg: str = Field(None, description="Текст сообщения")
    is_send_to_phone: int | None = Field(0, description="")
    is_deliv: int | None = Field(0, description="")


class AndroidPowerRequest(BaseModel):
    """Схема уведомления о включении/выключении Android приложения"""
    device: str = Field(None, description="Уникальный ID устройства")
    power: int = Field(1, description="Флаг включения")

    model_config = ConfigDict(
        json_schema_extra={
            'example': {
                "device": "3df3bda5-7fbd-400c-901b-7baccb875bd8-WA",
                "power": 1
            }
        }
    )


class AndroidMessageRequest(BaseModel):
    """Схема запроса сообщения Android приложением"""
    device: str = Field("", description="Уникальный ID устройства")
    bat: int | None = Field(1, description="Заряд батареи в процентах")
    charging: int | None = Field(0, description="Признак зарядки устройства")

    model_config = ConfigDict(
        json_schema_extra={
            'example': {
                "device": "23ec1f50-8ad5-47a5-b719-daa6223427c8-WA",
                "bat": 10,
                "charging": 1
            }
        }
    )


class AndroidMessageWebhook(BaseModel):
    """Схема вебхука о статусе сообщения от Android приложения"""
    device: str = Field("", description="Уникальный ID устройства")
    param_json: List[Dict] = Field(0, description="Признак зарядки устройства")  # noqa

    model_config = ConfigDict(
        json_schema_extra = {
            "examples": {
                "example1": {
                    "summary": "Подтверждение получение сообщение",
                    "value": [{
                        "device": "23ec1f50-8ad5-47a5-b719-daa6223427c8-WA",
                        "param_json": '[{"id":85224329}]'
                    }]
                },
                "example2": {
                    "summary": "Изменение статуса сообщения",
                    "value": [
                        {
                            "date_create": "2025-06-10 19:21:43",
                            "date_deliv": "2025-06-10 19:21:51",
                            "date_error": "",
                            "date_send": "2025-06-10 19:21:51",
                            "id": 85224329,
                            "id_from_app": "",
                            "is_deliv": 1,
                            "is_read": False,
                            "msg": "вамвамв",
                            "parts": 1,
                            "phone": "+79204800058",
                            "priority": 0,
                            "slotsim": 1,
                            "status": 2,
                            "status_app": 0,
                            "tip_send": 1
                        }
                    ]
                }
            }
        }
    )

# Response with code
class AndroidCodeResponse(BaseModel):
    """Базовая схема ответа на запрос Android приложения"""
    code: str = Field("0", description="Код успешности операции")
    error: str | None = Field(None, description="Сообщение об ошибке")

    @model_serializer(mode="wrap")
    def exclude_none_error_i(self, handler):
        data = handler(self)
        if data.get("error") is None:
            data.pop("error", None)
        return data

# Response for android device register
class AndroidRegResponse(AndroidCodeResponse):
    """Схема ответа на запрос регистрации Android приложения"""
    auth_code: str = Field("", description="Код привязки устройства")
    is_socket: int = Field(0, description="")
    version: int = Field(1, description="")
    id_device: int = Field(0, description="ID зарегистрированного устройства")
    apk_url: str = Field(None, description="URL для скачивания .apk")


class AndroidMessageResponse(AndroidCodeResponse):
    """Схема сообщения на отправку Android приложением"""
    limit: str = Field("", description="")
    limit_date: datetime | None = Field(None, description="")
    limit_use: int = Field(0, description="")
    is_limit: bool = Field(False, description="")
    ost: int | None = Field(None, description="")
    is_log: int | None = Field(0, description="")
    dop_name: str = Field("", description="")
    is_socket: int = Field(0, description="")
    type: int = Field(1, description="")
    data: List[AndroidMessage]


class AndroidAccountLinkRequest(BaseModel):
    device: str = Field(description='ID девайса')


class AndroidAccountLinkResponse(BaseModel):
    id_task: int = Field(description='ID операции')
    url: str = Field(description='Ссылка на скачивание архива')
    cnt_msg_iteration: int | None = Field(
        -1, description='Лимит отправок сообщений до смены аккаунта'
    )
    status: int = Field(description='Статус задачи / аккаунта')
    code: str = Field('0', description='Код успешности операции')


class AndroidAccountUnlinkRequest(BaseModel):
    id_task: int = Field(description='ID операции')
    device: str | None = Field(None, description='ID девайса,')
    sent: int | None = Field(
        0, description='Количество отправленных сообщений'
    )
