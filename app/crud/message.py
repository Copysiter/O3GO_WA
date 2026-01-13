from app.crud.base import CRUDBase
from app.models.message import Message
from app.schemas.message import MessageCreate, MessageUpdate, MessageFilter


class MessageCRUD(
    CRUDBase[Message, MessageCreate, MessageUpdate, MessageFilter]
):
    """CRUD-репозиторий для Message с поддержкой фильтра MessageFilter."""

    def __init__(self) -> None:
        super().__init__(model=Message, filter_class=MessageFilter)


message = MessageCRUD()
