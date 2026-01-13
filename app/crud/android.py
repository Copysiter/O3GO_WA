from app.crud.base import CRUDBase
from app.models.android import Android
from app.schemas.android import AndroidCreate, AndroidUpdate, AndroidFilter


class CRUDAndroid(
    CRUDBase[Android, AndroidCreate, AndroidUpdate, AndroidFilter]
):
    """CRUD-репозиторий для Android с поддержкой фильтра AndroidFilter."""

    def __init__(self) -> None:
        super().__init__(model=Android, filter_class=AndroidFilter)


android = CRUDAndroid()
