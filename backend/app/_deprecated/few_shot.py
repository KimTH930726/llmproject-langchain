"""Few-shot and Intent models for database tables."""
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, Column, String, DateTime, Boolean, Integer, Text, JSON, BigInteger
from sqlalchemy import text
import os


# Intent 모델 (키워드-의도 매핑)
class Intent(SQLModel, table=True):
    """키워드와 의도 타입 매핑 테이블."""
    __tablename__ = "intents"
    __table_args__ = {"schema": os.getenv("DB_SCHEMA", "public")}

    id: Optional[int] = Field(default=None, primary_key=True)
    keyword: str = Field(sa_column=Column(String(200), nullable=False))
    intent_type: str = Field(sa_column=Column(String(100), nullable=False))  # rag_search, sql_query, general
    priority: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default=text("0")))
    description: Optional[str] = Field(default=None, sa_column=Column(String(500)))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))
    )


# Few-shot 모델
class FewShot(SQLModel, table=True):
    """Few-shot 예제 관리 테이블 - 승격된 예제만 저장."""
    __tablename__ = "few_shots"
    __table_args__ = {"schema": os.getenv("DB_SCHEMA", "public")}

    id: Optional[int] = Field(default=None, primary_key=True)
    source_query_log_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True))  # query_logs.id 참조
    intent_type: Optional[str] = Field(default=None, sa_column=Column(String(100)))  # rag_search, sql_query, general
    user_query: str = Field(sa_column=Column(Text, nullable=False))
    expected_response: Optional[str] = Field(default=None, sa_column=Column(Text))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default=text("true")))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))
    )


# Few-shot Audit 모델
class FewShotAudit(SQLModel, table=True):
    """Few-shot 변경 이력 테이블."""
    __tablename__ = "few_shot_audit"
    __table_args__ = {"schema": os.getenv("DB_SCHEMA", "public")}

    id: Optional[int] = Field(default=None, primary_key=True)
    few_shot_id: int = Field(foreign_key="few_shots.id", nullable=False)
    action: str = Field(sa_column=Column(String(20), nullable=False))  # INSERT, UPDATE, DELETE
    old_value: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    new_value: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    changed_by: Optional[str] = Field(default="system", sa_column=Column(String(100)))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    )


# Pydantic response models for API

class IntentResponse(SQLModel):
    """Intent API 응답 모델."""
    id: int
    keyword: str
    intent_type: str
    priority: int
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class IntentCreate(SQLModel):
    """Intent 생성 요청 모델."""
    keyword: str
    intent_type: str  # rag_search, sql_query, general
    priority: int = 0
    description: Optional[str] = None


class IntentUpdate(SQLModel):
    """Intent 수정 요청 모델."""
    keyword: Optional[str] = None
    intent_type: Optional[str] = None
    priority: Optional[int] = None
    description: Optional[str] = None


class FewShotResponse(SQLModel):
    """Few-shot API 응답 모델."""
    id: int
    source_query_log_id: Optional[int]
    intent_type: Optional[str]
    user_query: str
    expected_response: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FewShotCreate(SQLModel):
    """Few-shot 생성 요청 모델."""
    source_query_log_id: Optional[int] = None  # query_logs.id 참조
    intent_type: Optional[str] = None  # rag_search, sql_query, general
    user_query: str
    expected_response: Optional[str] = None
    is_active: bool = True


class FewShotUpdate(SQLModel):
    """Few-shot 수정 요청 모델."""
    intent_type: Optional[str] = None
    user_query: Optional[str] = None
    expected_response: Optional[str] = None
    is_active: Optional[bool] = None


class FewShotAuditResponse(SQLModel):
    """Few-shot Audit API 응답 모델."""
    id: int
    few_shot_id: int
    action: str
    old_value: Optional[dict]
    new_value: Optional[dict]
    changed_by: Optional[str]
    created_at: datetime
