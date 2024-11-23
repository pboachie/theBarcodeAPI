# app/models.py
from datetime import datetime
import pytz

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils import IDGenerator

import logging

logger = logging.getLogger(__name__)

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, unique=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)
    tier = Column(String, nullable=False, default='unauthenticated')
    ip_address = Column(String, nullable=True)
    remaining_requests = Column(Integer, default=0)
    requests_today = Column(Integer, default=0)
    last_request = Column(DateTime(timezone=True), nullable=True)
    last_reset = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('username', name='uq_users_username'),
        UniqueConstraint('id', name='uq_users_id'),
    )

    # Relationships
    active_token = relationship("ActiveToken", back_populates="user", uselist=False)
    usage = relationship("Usage", back_populates="user", uselist=False)


    @classmethod
    async def get_user_by_id(cls, db: AsyncSession, user_id: str):
        result = await db.execute(select(cls).filter(cls.id == user_id))
        return result.scalar_one_or_none()

    @classmethod
    async def update_remaining_requests(cls, db: AsyncSession, user_id: str, new_remaining_requests: int):
        stmt = (
            update(cls)
            .where(cls.id == user_id)
            .values(remaining_requests=new_remaining_requests)
        )
        await db.execute(stmt)

class ActiveToken(Base):
    __tablename__ = "active_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True)
    token = Column(String, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Relationship
    user = relationship("User", back_populates="active_token")

class Usage(Base):
    __tablename__ = "usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    tier = Column(String, nullable=True, default='unauthenticated')
    ip_address = Column(String, index=True, nullable=True)
    requests_today = Column(Integer, default=0)
    remaining_requests = Column(Integer, default=0)
    last_request = Column(DateTime(timezone=True), server_default=func.now())
    last_reset = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="usage")

    @classmethod
    async def check_and_reset_usage(cls, db: AsyncSession, usage: 'Usage') -> 'Usage':
        current_time_utc = datetime.now(pytz.utc)
        pst_tz = pytz.timezone('America/Los_Angeles')
        current_time_pst = current_time_utc.astimezone(pst_tz)
        start_of_day_pst = current_time_pst.replace(hour=0, minute=0, second=0, microsecond=0)

        if usage.last_reset is None or usage.last_reset < start_of_day_pst:
            stmt = (
                update(cls)
                .where(cls.id == usage.id)
                .values(
                    requests_today=0,
                    last_reset=current_time_utc,
                    remaining_requests=0
                )
            )
            await db.execute(stmt)
            await db.refresh(usage)

        return usage

    @classmethod
    async def increment_usage(cls, db: AsyncSession, usage: 'Usage') -> 'Usage':
        stmt = (
            update(cls)
            .where(cls.id == usage.id)
            .values(
                requests_today=cls.requests_today + 1,
                remaining_requests=cls.remaining_requests - 1,
                last_request=datetime.now(pytz.utc)
            )
        )
        await db.execute(stmt)
        await db.refresh(usage)
        return usage

    @classmethod
    async def get_usage(cls, db: AsyncSession, user_id: str = None, ip_address: str = None) -> 'Usage':
        if user_id:
            stmt = select(cls).filter(cls.user_id == user_id)
        elif ip_address:
            stmt = select(cls).filter(cls.ip_address == ip_address)
        else:
            return None

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_usage_by_id(cls, db: AsyncSession, usage_id: int) -> 'Usage':
        result = await db.execute(select(cls).filter(cls.id == usage_id))
        return result.scalar_one_or_none()
