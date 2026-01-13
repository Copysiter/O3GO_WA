from sqlalchemy import Column, BigInteger, String

from app.adapters.db.base_class import Base


class Version(Base):
    id = Column(
        BigInteger, primary_key=True, index=True,
        autoincrement=True, unique=True
    )
    file_name = Column(String, index=True)
    description = Column(String)

