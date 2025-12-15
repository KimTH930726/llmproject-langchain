"""질의 로그 모델 - 모든 사용자 질의 자동 저장"""
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, Column, String, Text, BigInteger
from sqlalchemy import text
import os


class QueryLog(SQLModel, table=True):
    """질의 로그 테이블 - 모든 사용자 질의 자동 저장"""
    __tablename__ = "query_logs"
    __table_args__ = {"schema": os.getenv("DB_SCHEMA", "public")}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    query_text: str = Field(sa_column=Column(Text, nullable=False))
    detected_intent: Optional[str] = Field(default=None, sa_column=Column(String(100)))
    response: Optional[str] = Field(default=None, sa_column=Column(Text))
    is_converted_to_fewshot: bool = Field(default=False, sa_column=Column("is_converted_to_fewshot", nullable=False, server_default=text("false")))
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(nullable=False, server_default=text("CURRENT_TIMESTAMP")))


# API 요청/응답 모델

class QueryLogCreate(SQLModel):
    """질의 로그 생성 요청"""
    query_text: str
    detected_intent: Optional[str] = None
    response: Optional[str] = None


class QueryLogResponse(SQLModel):
    """질의 로그 응답"""
    id: int
    query_text: str
    detected_intent: Optional[str]
    response: Optional[str]
    is_converted_to_fewshot: bool
    created_at: datetime


class QueryLogListResponse(SQLModel):
    """질의 로그 목록 응답"""
    total: int
    items: list[QueryLogResponse]


class ConvertToFewShotRequest(SQLModel):
    """Few-shot으로 승격 요청"""
    query_log_id: int
    intent_type: Optional[str] = None
    expected_response: Optional[str] = None
    is_active: bool = True
