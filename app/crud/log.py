from app.crud.base import CRUDBase
from app.models.log import Log
from app.schemas.log import LogCreate, LogUpdate, LogFilter


class LogCRUD(CRUDBase[Log, LogCreate, LogUpdate, LogFilter]):
    """CRUD-репозиторий для Log с поддержкой фильтра LogFilter."""

    def __init__(self) -> None:
        super().__init__(model=Log, filter_class=LogFilter)


log = LogCRUD()
