from app.crud.base import CRUDBase
from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate, AccountFilter


class AccountCRUD(
    CRUDBase[Account, AccountCreate, AccountUpdate, AccountFilter]
):
    """CRUD-репозиторий для Account с поддержкой фильтра AccountFilter."""

    def __init__(self) -> None:
        super().__init__(model=Account, filter_class=AccountFilter)


account = AccountCRUD()
