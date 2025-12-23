"""Intent CRUD API endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.few_shot import (
    Intent,
    IntentResponse,
    IntentCreate,
    IntentUpdate
)

router = APIRouter(prefix="/api/intent", tags=["Intent Management"])


@router.get("/", response_model=List[IntentResponse])
async def get_all_intents(session: Session = Depends(get_session)):
    """모든 Intent 목록 조회 (우선순위 순)."""
    statement = select(Intent).order_by(Intent.priority.desc(), Intent.created_at.desc())
    intents = session.exec(statement).all()
    return intents


@router.get("/{intent_id}", response_model=IntentResponse)
async def get_intent(intent_id: int, session: Session = Depends(get_session)):
    """특정 Intent 조회."""
    intent = session.get(Intent, intent_id)
    if not intent:
        raise HTTPException(status_code=404, detail=f"Intent with id {intent_id} not found")
    return intent


@router.post("/", response_model=IntentResponse, status_code=201)
async def create_intent(intent_data: IntentCreate, session: Session = Depends(get_session)):
    """Intent 생성 (키워드-의도 매핑)."""
    intent = Intent(**intent_data.model_dump())
    session.add(intent)
    session.commit()
    session.refresh(intent)
    return intent


@router.put("/{intent_id}", response_model=IntentResponse)
async def update_intent(
    intent_id: int,
    intent_data: IntentUpdate,
    session: Session = Depends(get_session)
):
    """Intent 수정."""
    intent = session.get(Intent, intent_id)
    if not intent:
        raise HTTPException(status_code=404, detail=f"Intent with id {intent_id} not found")

    update_data = intent_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(intent, key, value)

    session.add(intent)
    session.commit()
    session.refresh(intent)
    return intent


@router.delete("/{intent_id}", status_code=204)
async def delete_intent(intent_id: int, session: Session = Depends(get_session)):
    """Intent 삭제."""
    intent = session.get(Intent, intent_id)
    if not intent:
        raise HTTPException(status_code=404, detail=f"Intent with id {intent_id} not found")

    session.delete(intent)
    session.commit()
    return None
