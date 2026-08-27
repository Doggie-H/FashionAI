from sqlalchemy.orm import Session
from . import models, schemas

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(
        username=user.username,
        email=user.email,
        height_cm=user.height_cm,
        weight_kg=user.weight_kg
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_wardrobe_items(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.WardrobeItem).filter(models.WardrobeItem.owner_id == user_id).offset(skip).limit(limit).all()

def create_wardrobe_item(db: Session, item: schemas.WardrobeItemCreate, user_id: int):
    db_item = models.WardrobeItem(**item.model_dump(), owner_id=user_id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item
