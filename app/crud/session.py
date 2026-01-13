from app.crud.base import CRUDBase
from app.models.session import Session
from app.schemas.session import SessionCreate, SessionUpdate, SessionFilter


class SessionCRUD(
    CRUDBase[Session, SessionCreate, SessionUpdate, SessionFilter]
):
    """CRUD-репозиторий для Session с поддержкой фильтра SessionFilter."""

    def __init__(self) -> None:
        super().__init__(model=Session, filter_class=SessionFilter)


session = SessionCRUD()
