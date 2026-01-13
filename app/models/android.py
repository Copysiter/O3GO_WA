from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.adapters.db.base_class import Base


class Android(Base):
    id = Column(
        Integer, primary_key=True, index=True,
        autoincrement=True, unique=True
    )
    user_id = Column(
        Integer, ForeignKey('user.id', ondelete='CASCADE'), index=True
    )
    account_id = Column(Integer, ForeignKey('account.id'), index=True)
    auth_code = Column(String, index=True)
    device = Column(String, index=True, unique=True)
    device_origin = Column(String, index=True)
    device_name = Column(String, index=True)
    manufacturer = Column(String, index=True)
    version = Column(String, index=True)
    android_version = Column(String, index=True)
    operator_name = Column(String, index=True)
    bat = Column(String, index=True)
    charging = Column(String, index=True)
    push_id = Column(String)
    info_data = Column(String)
    type = Column(String, index=True)
    is_active = Column(Boolean, default=True, index=True)
    user = relationship('User', lazy='joined')
    account = relationship('Account', lazy='joined')
