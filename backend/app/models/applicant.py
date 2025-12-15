from sqlmodel import SQLModel, Field, Column
from sqlalchemy import String
from typing import Optional
import os


class Applicant(SQLModel, table=True):
    """
    지원자 모델 (읽기 전용)
    PostgreSQL의 applicant_info 테이블과 매핑됨
    """
    __tablename__ = "applicant_info"
    __table_args__ = {"schema": os.getenv("DB_SCHEMA", "public")}

    id: Optional[int] = Field(default=None, primary_key=True)
    reason: Optional[str] = Field(default=None, sa_column=Column(String(4000)))  # 지원 동기
    experience: Optional[str] = Field(default=None, sa_column=Column(String(4000)))  # 경력 및 경험
    skill: Optional[str] = Field(default=None, sa_column=Column(String(4000)))  # 기술 스택 및 역량


class ApplicantRead(SQLModel):
    """지원자 조회 응답 모델"""
    id: int
    reason: Optional[str] = None
    experience: Optional[str] = None
    skill: Optional[str] = None
