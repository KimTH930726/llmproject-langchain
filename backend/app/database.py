from sqlmodel import create_engine, SQLModel, Session
import os
from dotenv import load_dotenv

load_dotenv()

# 데이터베이스 URL
# PostgreSQL 연결 문자열 형식: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@localhost:5432/applicants_db")

# 엔진 생성
# PostgreSQL 사용 시 echo=True는 개발 환경에서만 권장 (SQL 쿼리 로깅)
engine = create_engine(DATABASE_URL, echo=True)


def get_session():
    """세션 생성 (의존성 주입용)"""
    with Session(engine) as session:
        yield session
