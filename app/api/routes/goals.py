from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, VariableGoal
from app.schemas.goal import GoalCreate, GoalOut, GoalUpdate

router = APIRouter()


@router.get("", response_model=list[GoalOut])
def list_goals(
    db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> list[VariableGoal]:
    return list(
        db.scalars(
            select(VariableGoal).where(VariableGoal.user_id == current.id)
        ).all()
    )


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> VariableGoal:
    goal = VariableGoal(user_id=current.id, **payload.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.put("/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> VariableGoal:
    goal = db.get(VariableGoal, goal_id)
    if not goal or goal.user_id != current.id:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(goal, k, v)
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    goal = db.get(VariableGoal, goal_id)
    if not goal or goal.user_id != current.id:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    db.delete(goal)
    db.commit()
