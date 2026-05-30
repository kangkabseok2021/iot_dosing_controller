from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import require_dispatcher
from app.db.base import get_db
from app.db.models import Delivery

router = APIRouter(prefix="/api/v1/deliveries", tags=["deliveries"])


class DeliveryCreate(BaseModel):
    description: str
    vehicle_id: int


class DeliveryRead(BaseModel):
    id: int
    description: str | None
    vehicle_id: int
    status: str | None

    model_config = {"from_attributes": True}


@router.post(
    "",
    response_model=DeliveryRead,
    status_code=201,
    dependencies=[Depends(require_dispatcher)],
)
def create_delivery(body: DeliveryCreate, db: Session = Depends(get_db)) -> Delivery:
    delivery = Delivery(description=body.description, vehicle_id=body.vehicle_id)
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


@router.get(
    "/{delivery_id}",
    response_model=DeliveryRead,
    dependencies=[Depends(require_dispatcher)],
)
def get_delivery(delivery_id: int, db: Session = Depends(get_db)) -> Delivery:
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery
