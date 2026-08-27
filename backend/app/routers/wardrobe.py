from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import crud, models, schemas, database

router = APIRouter(
    prefix="/wardrobe",
    tags=["wardrobe"],
)

@router.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@router.get("/users/{user_id}", response_model=schemas.User)
def read_user(user_id: int, db: Session = Depends(database.get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.post("/users/{user_id}/items/", response_model=schemas.WardrobeItem)
def create_item_for_user(
    user_id: int, item: schemas.WardrobeItemCreate, db: Session = Depends(database.get_db)
):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return crud.create_wardrobe_item(db=db, item=item, user_id=user_id)

@router.get("/users/{user_id}/items/", response_model=List[schemas.WardrobeItem])
def read_items_for_user(
    user_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)
):
    items = crud.get_wardrobe_items(db, user_id=user_id, skip=skip, limit=limit)
    return items
