"""
Database models for the Barcode API application.

This module contains SQLAlchemy ORM models for the PostgreSQL database,
including User management, Authentication tokens, Usage tracking, and MCP client authentication.
"""
from datetime import datetime
from typing import Optional, Union
import pytz

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, Index, Boolean, Text, JSON, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, validates
from enum import Enum

from app.database import Base

import logging

logger = logging.getLogger(__name__)

class UserTier(str, Enum):
    """
    User tier enumeration for access control and rate limiting.

    Attributes:
        UNAUTHENTICATED: Free tier with basic rate limits
        BASIC: Registered users with enhanced limits
        PREMIUM: Premium users with highest rate limits and priority processing
    """
    UNAUTHENTICATED = "unauthenticated"
    BASIC = "basic"
    PREMIUM = "premium"

class User(Base):
    """
    User model for authentication and account management.

    Represents both authenticated users and tracks unauthenticated usage by IP.
    Includes comprehensive rate limiting and usage tracking capabilities.

    Attributes:
        id: Unique user identifier (nanoid)
        username: Unique username for authentication
        hashed_password: Bcrypt hashed password (nullable for IP-based users)
        tier: User access tier determining rate limits and features
        ip_address: Client IP address for tracking and fallback identification
        remaining_requests: Current remaining API requests for rate limiting
        requests_today: Number of requests made today for analytics
        last_request: Timestamp of most recent API request
        last_reset: Timestamp of last daily limit reset
        created_at: Account creation timestamp
        updated_at: Last account modification timestamp
    """
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, unique=True,
                doc="Unique user identifier generated using nanoid")
    username = Column(String, unique=True, index=True, nullable=False,
                     doc="Unique username for authentication")
    hashed_password = Column(String, nullable=True,
                           doc="Bcrypt hashed password (null for IP-based users)")

    tier = Column(String, nullable=False, default=UserTier.UNAUTHENTICATED,
                 doc="User tier determining rate limits and feature access")

    ip_address = Column(String, nullable=True, index=True,
                       doc="Client IP address for tracking and identification")

    remaining_requests = Column(Integer, default=0, nullable=False,
                              doc="Current remaining API requests for rate limiting")
    requests_today = Column(Integer, default=0, nullable=False,
                          doc="Number of requests made today for analytics")

    last_request = Column(DateTime(timezone=True), nullable=True,
                         doc="Timestamp of most recent API request")
    last_reset = Column(DateTime(timezone=True), nullable=True,
                       doc="Timestamp of last daily limit reset")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                       doc="Account creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                       onupdate=func.now(), nullable=False,
                       doc="Last account modification timestamp")

    __table_args__ = (
        UniqueConstraint('username', name='uq_users_username'),
        UniqueConstraint('id', name='uq_users_id'),
        Index('ix_users_tier', 'tier'),
        Index('ix_users_last_request', 'last_request'),
        Index('ix_users_created_at', 'created_at'),
        Index('ix_users_ip_tier', 'ip_address', 'tier'),
    )

    active_token = relationship("ActiveToken", back_populates="user", uselist=False,
                              cascade="all, delete-orphan")
    usage = relationship("Usage", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

    @validates('tier')
    def validate_tier(self, key, tier):
        """Validate that tier is a valid UserTier value."""
        if tier not in [t.value for t in UserTier]:
            raise ValueError(f"Invalid tier: {tier}. Must be one of {[t.value for t in UserTier]}")
        return tier

    @validates('username')
    def validate_username(self, key, username):
        """Validate username format and length."""
        if username and len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if username and len(username) > 50:
            raise ValueError("Username must be at most 50 characters long")
        return username

    def is_authenticated(self) -> bool:
        """Check if user is authenticated (has username and password)."""
        return self.username is not None and self.hashed_password is not None

    def get_rate_limit(self) -> int:
        """Get the rate limit for this user's tier."""
        from app.config import settings
        return settings.RateLimit.get_limit(str(self.tier))

    @classmethod
    async def update_request_count(cls, db: AsyncSession):
        current_time = datetime.now(pytz.utc)
        cls.requests_today += 1
        cls.last_request = current_time
        current_remaining = cls.remaining_requests if isinstance(cls.remaining_requests, int) else 0
        cls.remaining_requests = max(0, current_remaining - 1)
        await db.commit()

    @classmethod
    async def reset_daily_counts(cls, db: AsyncSession):
        current_time = datetime.now(pytz.utc)
        cls.requests_today = 0
        cls.last_reset = current_time
        await db.commit()

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
    """
    Active JWT token tracking for authentication and session management.

    Tracks currently valid JWT tokens to enable token blacklisting and
    single-session enforcement. Used for secure logout and token revocation.

    Attributes:
        id: Primary key for token record
        user_id: Foreign key reference to the owning user
        token: The actual JWT token string (hashed for security)
        created_at: Token creation timestamp
        expires_at: Token expiration timestamp
        is_revoked: Flag indicating if token has been manually revoked
        last_used: Timestamp of last token usage for activity tracking
    """
    __tablename__ = "active_tokens"

    id = Column(Integer, primary_key=True, index=True,
               doc="Primary key for token record")
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False,
                    doc="Foreign key reference to the owning user")
    token = Column(String, unique=True, nullable=False,
                  doc="JWT token string (should be hashed for security)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                       doc="Token creation timestamp")
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True,
                       doc="Token expiration timestamp")
    is_revoked = Column(Boolean, default=False, nullable=False, index=True,
                       doc="Flag indicating if token has been manually revoked")
    last_used = Column(DateTime(timezone=True), nullable=True,
                      doc="Timestamp of last token usage for activity tracking")

    __table_args__ = (
        Index('ix_active_tokens_expires_revoked', 'expires_at', 'is_revoked'),
        Index('ix_active_tokens_user_active', 'user_id', 'is_revoked'),
    )

    user = relationship("User", back_populates="active_token")

    @validates('token')
    def validate_token(self, key, token):
        """Validate token format and length."""
        if not token or len(token) < 10:
            raise ValueError("Token must be at least 10 characters long")
        return token

    def is_valid(self) -> bool:
        """Check if token is currently valid (not expired or revoked)."""
        now = datetime.now(pytz.utc)
        is_not_revoked = getattr(self, 'is_revoked', False) is False
        is_not_expired = self.expires_at and self.expires_at > now
        return is_not_revoked and bool(is_not_expired)

    def revoke(self):
        """Mark token as revoked."""
        object.__setattr__(self, 'is_revoked', True)

    def update_last_used(self):
        """Update the last used timestamp."""
        self.last_used = datetime.now(pytz.utc)

class Usage(Base):
    """
    Usage tracking model for API analytics and rate limiting.

    Tracks API usage patterns for both authenticated users and IP addresses.
    Provides detailed analytics and supports dynamic rate limiting based on usage patterns.

    Attributes:
        id: Primary key for usage record
        user_id: Foreign key to user (nullable for IP-only tracking)
        tier: User tier for rate limiting (cached for performance)
        ip_address: Client IP address for tracking and identification
        requests_today: Count of requests made today
        remaining_requests: Remaining requests for current period
        last_request: Timestamp of most recent request
        last_reset: Timestamp of last daily limit reset
        created_at: Record creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "usage"

    id = Column(Integer, primary_key=True, index=True,
               doc="Primary key for usage record")
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True,
                    doc="Foreign key to user (nullable for IP-only tracking)")
    tier = Column(String, nullable=True, default='unauthenticated',
                 doc="User tier for rate limiting (cached for performance)")
    ip_address = Column(String, index=True, nullable=True,
                       doc="Client IP address for tracking and identification")
    requests_today = Column(Integer, default=0, nullable=False,
                          doc="Count of requests made today")
    remaining_requests = Column(Integer, default=0, nullable=False,
                              doc="Remaining requests for current period")
    last_request = Column(DateTime(timezone=True), server_default=func.now(), index=True,
                         doc="Timestamp of most recent request")
    last_reset = Column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                       doc="Timestamp of last daily limit reset")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                       doc="Record creation timestamp")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                       onupdate=func.now(), nullable=False,
                       doc="Last update timestamp")

    __table_args__ = (
        Index('ix_usage_user_ip', 'user_id', 'ip_address'),
        Index('ix_usage_ip_tier', 'ip_address', 'tier'),
        Index('ix_usage_last_reset', 'last_reset'),
        Index('ix_usage_tier_requests', 'tier', 'requests_today'),
    )

    user = relationship("User", back_populates="usage")

    @validates('tier')
    def validate_tier(self, key, tier):
        """Validate that tier is a valid value."""
        valid_tiers = [t.value for t in UserTier] + [None]
        if tier not in valid_tiers:
            raise ValueError(f"Invalid tier: {tier}. Must be one of {valid_tiers}")
        return tier

    @validates('requests_today', 'remaining_requests')
    def validate_non_negative_integers(self, key, value):
        """Validate that numeric fields are non-negative."""
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value

    def needs_reset(self) -> bool:
        """Check if usage needs to be reset for a new day."""
        if self.last_reset is None:
            return True

        current_time_utc = datetime.now(pytz.utc)
        pst_tz = pytz.timezone('America/Los_Angeles')
        current_time_pst = current_time_utc.astimezone(pst_tz)
        start_of_day_pst = current_time_pst.replace(hour=0, minute=0, second=0, microsecond=0)

        return self.last_reset < start_of_day_pst  # type: ignore

    def get_rate_limit(self) -> int:
        """Get the rate limit for this usage record's tier."""
        from app.config import settings
        tier_value = str(self.tier) if self.tier is not None else "unauthenticated"
        return settings.RateLimit.get_limit(tier_value)

    @classmethod
    async def check_and_reset_usage(cls, db: AsyncSession, usage: 'Usage') -> 'Usage':
        current_time_utc = datetime.now(pytz.utc)
        pst_tz = pytz.timezone('America/Los_Angeles')
        current_time_pst = current_time_utc.astimezone(pst_tz)
        start_of_day_pst = current_time_pst.replace(hour=0, minute=0, second=0, microsecond=0)

        if usage.last_reset is None:
            # No previous reset, so reset is needed
            should_reset = True
        else:
            should_reset = usage.last_reset < start_of_day_pst  # type: ignore

        if should_reset:  # type: ignore
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
    async def get_usage(
        cls,
        db: AsyncSession,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Union['Usage', None]:
        if user_id:
            stmt = select(cls).filter(cls.user_id == user_id)
        elif ip_address:
            stmt = select(cls).filter(cls.ip_address == ip_address)
        else:
            return None

        result = await db.execute(stmt)
        return result.scalar()

    @classmethod
    async def get_usage_by_id(cls, db: AsyncSession, usage_id: int) -> 'Usage | None':
        result = await db.execute(select(cls).filter(cls.id == usage_id))
        return result.scalar_one_or_none()

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    details = Column(JSON, nullable=True)

    user = relationship("User", back_populates="audit_logs")

class MCPClientAuthRequest(Base):
    """
    Model for MCP (Model Context Protocol) client authentication requests.

    Tracks requests for MCP client authentication to enable rate limiting
    and audit logging of authentication attempts.

    Attributes:
        id: Primary key for the request record
        client_name: Optional name/identifier for the requesting client
        requested_scopes: JSON array of requested permission scopes
        ip_address: IP address of the requesting client
        user_agent: User agent string from the request headers
        timestamp: When the authentication request was made
        success: Whether the authentication request was successful
        client_id_generated: The client ID that was generated (if successful)
        rate_limit_exceeded: Whether the request was denied due to rate limiting
    """
    __tablename__ = "mcp_client_auth_requests"

    id = Column(Integer, primary_key=True, index=True,
               doc="Primary key for the authentication request record")
    client_name = Column(String(255), nullable=True,
                        doc="Optional name/identifier for the requesting client")
    requested_scopes = Column(JSON, nullable=True, default=list,
                            doc="JSON array of requested permission scopes")
    ip_address = Column(String(45), nullable=False, index=True,
                       doc="IP address of the requesting client (supports IPv6)")
    user_agent = Column(Text, nullable=True,
                       doc="User agent string from the request headers")
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
                      doc="When the authentication request was made")
    success = Column(Boolean, default=False, nullable=False, index=True,
                    doc="Whether the authentication request was successful")
    client_id_generated = Column(String(36), nullable=True, index=True,
                               doc="The client ID that was generated (if successful)")
    rate_limit_exceeded = Column(Boolean, default=False, nullable=False,
                               doc="Whether the request was denied due to rate limiting")

    __table_args__ = (
        Index('ix_mcp_auth_requests_ip_timestamp', 'ip_address', 'timestamp'),
        Index('ix_mcp_auth_requests_success_timestamp', 'success', 'timestamp'),
        Index('ix_mcp_auth_requests_rate_limit', 'ip_address', 'rate_limit_exceeded', 'timestamp'),
    )

    @validates('ip_address')
    def validate_ip_address(self, key, ip_address):
        """Validate IP address format."""
        import ipaddress
        try:
            ipaddress.ip_address(ip_address)
            return ip_address
        except ValueError:
            raise ValueError(f"Invalid IP address format: {ip_address}")

    @validates('client_name')
    def validate_client_name(self, key, client_name):
        """Validate client name length."""
        if client_name and len(client_name) > 255:
            raise ValueError("Client name must be at most 255 characters long")
        return client_name

class MCPClientAuthResponse(Base):
    """
    Model for MCP client authentication responses and active sessions.

    Tracks generated client IDs, their expiration, and session information
    for MCP WebSocket connections. Used for validation and cleanup.

    Attributes:
        id: Primary key for the response record
        client_id: The generated client ID (UUID format)
        ip_address: IP address of the client that requested authentication
        expires_at: When the client ID expires
        websocket_url: The WebSocket URL provided to the client
        created_at: When the client ID was generated
        first_connection_at: When the client first connected via WebSocket
        last_activity_at: Last activity timestamp for session tracking
        connection_count: Number of times this client ID has been used to connect
        is_active: Whether the client ID is currently active/valid
        revoked_at: When the client ID was revoked (if applicable)
        revocation_reason: Reason for revoking the client ID
    """
    __tablename__ = "mcp_client_auth_responses"

    id = Column(Integer, primary_key=True, index=True,
               doc="Primary key for the response record")
    client_id = Column(String(36), unique=True, nullable=False, index=True,
                      doc="The generated client ID (UUID format)")
    ip_address = Column(String(45), nullable=False, index=True,
                       doc="IP address of the client that requested authentication")
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True,
                       doc="When the client ID expires")
    websocket_url = Column(String(500), nullable=False,
                          doc="The WebSocket URL provided to the client")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                       doc="When the client ID was generated")
    first_connection_at = Column(DateTime(timezone=True), nullable=True,
                               doc="When the client first connected via WebSocket")
    last_activity_at = Column(DateTime(timezone=True), nullable=True, index=True,
                            doc="Last activity timestamp for session tracking")
    connection_count = Column(Integer, default=0, nullable=False,
                            doc="Number of times this client ID has been used to connect")
    is_active = Column(Boolean, default=True, nullable=False, index=True,
                      doc="Whether the client ID is currently active/valid")
    revoked_at = Column(DateTime(timezone=True), nullable=True,
                       doc="When the client ID was revoked (if applicable)")
    revocation_reason = Column(String(255), nullable=True,
                             doc="Reason for revoking the client ID")

    __table_args__ = (
        Index('ix_mcp_auth_responses_client_active', 'client_id', 'is_active'),
        Index('ix_mcp_auth_responses_ip_active', 'ip_address', 'is_active'),
        Index('ix_mcp_auth_responses_expires_active', 'expires_at', 'is_active'),
        Index('ix_mcp_auth_responses_activity', 'last_activity_at', 'is_active'),
    )

    @validates('client_id')
    def validate_client_id(self, key, client_id):
        """Validate client ID format (should be UUID)."""
        import uuid
        try:
            uuid.UUID(client_id)
            return client_id
        except ValueError:
            raise ValueError(f"Invalid client ID format: {client_id}")

    @validates('websocket_url')
    def validate_websocket_url(self, key, websocket_url):
        """Validate WebSocket URL format."""
        if not websocket_url.startswith(('ws://', 'wss://')):
            raise ValueError("WebSocket URL must start with ws:// or wss://")
        if len(websocket_url) > 500:
            raise ValueError("WebSocket URL must be at most 500 characters long")
        return websocket_url

    @validates('connection_count')
    def validate_connection_count(self, key, connection_count):
        """Validate connection count is non-negative."""
        if connection_count < 0:
            raise ValueError("Connection count must be non-negative")
        return connection_count

    def is_expired(self) -> bool:
        """Check if the client ID has expired."""
        if self.expires_at is None:
            return True
        return datetime.now(pytz.utc) > self.expires_at  # type: ignore

    def is_valid(self) -> bool:
        """Check if the client ID is valid (active and not expired)."""
        return bool(self.is_active) and not self.is_expired()

    def revoke(self, reason: Optional[str] = None):
        """Revoke the client ID."""
        self.is_active = False
        self.revoked_at = datetime.now(pytz.utc)
        if reason:
            self.revocation_reason = reason

    def update_activity(self):
        """Update the last activity timestamp."""
        self.last_activity_at = datetime.now(pytz.utc)

    def increment_connection_count(self):
        """Increment the connection count and update activity."""
        self.connection_count += 1
        self.update_activity()
        if self.first_connection_at is None:
            self.first_connection_at = datetime.now(pytz.utc)

    @classmethod
    async def get_by_client_id(cls, db: AsyncSession, client_id: str) -> Optional['MCPClientAuthResponse']:
        """Get an MCP client auth response by client ID."""
        result = await db.execute(select(cls).filter(cls.client_id == client_id))
        return result.scalar_one_or_none()

    @classmethod
    async def get_active_by_client_id(cls, db: AsyncSession, client_id: str) -> Optional['MCPClientAuthResponse']:
        """Get an active MCP client auth response by client ID."""
        result = await db.execute(
            select(cls).filter(
                cls.client_id == client_id,
                cls.is_active.is_(True),  # type: ignore
                cls.expires_at > func.now()
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def cleanup_expired(cls, db: AsyncSession) -> int:
        """Clean up expired client IDs and return the count of cleaned up records."""
        current_time = datetime.now(pytz.utc)
        stmt = (
            update(cls)
            .where(
                cls.expires_at <= current_time,
                cls.is_active.is_(True)  # type: ignore
            )
            .values(
                is_active=False,
                revoked_at=current_time,
                revocation_reason="Expired"
            )
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
