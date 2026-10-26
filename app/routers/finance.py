# app/routers/finance.py — 관리자 재고·자금: 기간 손익 데이터 · 부대비용
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_admin
from app.models.user import User
from app.schemas.finance import FinanceResponse, ExpenseCreate, ExpenseResponse
from app.crud import finance as finance_crud
from app.crud import inventory as inventory_crud

router = APIRouter()


# 기간(한국 날짜, 양 끝 포함)의 판매 기록 · 부대비용 · 입고 금액 — 손익 합계는 화면에서 계산한다
@router.get("", response_model=FinanceResponse)
def get_finance(
    start: date = Query(..., alias="from"),
    end: date = Query(..., alias="to"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if end < start:
        raise HTTPException(status_code=400, detail="기간이 올바르지 않습니다")
    return {
        "sales": finance_crud.get_sales(db, start, end),
        "expenses": finance_crud.get_expenses(db, start, end),
        "purchases": inventory_crud.get_purchases_total(db, start, end),
    }


@router.post("/expenses", response_model=ExpenseResponse)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    label = payload.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="항목을 입력해주세요")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="금액은 0보다 커야 합니다")
    return finance_crud.create_expense(db, payload.spent_on, label[:100], payload.amount)


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    if not finance_crud.delete_expense(db, expense_id):
        raise HTTPException(status_code=404, detail="부대비용 기록을 찾을 수 없습니다")
