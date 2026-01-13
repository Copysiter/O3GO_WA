from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.version import Version
from app.schemas.version import VersionCreate, VersionUpdate, VersionFilter


class CRUDVersion(
    CRUDBase[Version, VersionCreate, VersionUpdate, VersionFilter]
):
    """CRUD-репозиторий для Version с поддержкой фильтра VersionFilter."""

    def __init__(self) -> None:
        super().__init__(model=Version, filter_class=VersionFilter)

    async def get_last(self, db: AsyncSession) -> Version | None:
        statement = select(self.model).order_by(self.model.id.desc()).limit(1)
        result = await db.execute(statement=statement)
        return result.unique().scalar_one_or_none()


version = CRUDVersion()
