from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.user import User
# from app.core.security import get_current_active_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/doctors", tags=["doctors"])

class DoctorResponse(BaseModel):
    id: int
    full_name: str
    specialty: Optional[str]
    license_number: Optional[str]
    clinic_name: Optional[str]
    clinic_address: Optional[str]
    bio: Optional[str]
    profile_picture: Optional[str]
    social_media: Optional[str]
    phone_number: str
    email: str

    class Config:
        orm_mode = True

class PatientResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone_number: str
    address: str
    created_at: datetime

    class Config:
        orm_mode = True

@router.get("", response_model=List[DoctorResponse])
async def list_doctors(
    specialty: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(User).filter(User.is_doctor == True)
    
    if specialty:
        query = query.filter(User.specialty.ilike(f"%{specialty}%"))
    
    doctors = query.all()
    return doctors

@router.get("/patients", response_model=List[PatientResponse])
async def list_patients(
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_active_user)
):
    # Verify the current user is a doctor
    # if not current_user.is_doctor:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Only doctors can view all patients"
    #     )
    
    patients = db.query(User).filter(User.is_doctor == False).all()
    return patients

@router.get("/{doctor_id}", response_model=DoctorResponse)
async def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db)
):
    doctor = db.query(User).filter(
        User.id == doctor_id,
        User.is_doctor == True
    ).first()
    
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    return doctor

