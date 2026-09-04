from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.admin_user import AdminUser
from app.models.expense import Expense
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseUpdate

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _get_scoped_expense(
    expense_id: int, current_admin: AdminUser, db: Session
) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.event_id != current_admin.event_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Despesa nao encontrada"
        )
    return expense


@router.get("/", response_model=list[ExpenseResponse])
def list_expenses(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> list[Expense]:
    return (
        db.query(Expense)
        .filter(Expense.event_id == current_admin.event_id)
        .order_by(Expense.created_at.desc())
        .all()
    )


@router.post("/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> Expense:
    expense = Expense(event_id=current_admin.event_id, **payload.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> Expense:
    expense = _get_scoped_expense(expense_id, current_admin, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)

    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_user),
) -> None:
    expense = _get_scoped_expense(expense_id, current_admin, db)
    db.delete(expense)
    db.commit()
