from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import time, datetime, timedelta, date
from app.database import get_db
from app.models.user import User
from app.models.working_hours import WorkingHours
from app.core.security import get_current_active_user
from pydantic import BaseModel
from app.models.user import Base as UserBase
from app.models.working_hours import Base as WorkingHoursBase
from app.models.appointment import Base as AppointmentBase
from app.models.prescription import Base as PrescriptionBase

router = APIRouter(prefix="/api/doctors", tags=["working-hours"])

class WorkingHoursCreate(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time
    has_break: bool = False
    break_start: time = None
    break_end: time = None

class WorkingHoursResponse(WorkingHoursCreate):
    id: int
    doctor_id: int
    is_available: bool

    class Config:
        orm_mode = True

@router.post("/{doctor_id}/working-hours", response_model=WorkingHoursResponse)
async def create_working_hours(
    doctor_id: int,
    working_hours: WorkingHoursCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify the current user is the doctor
    if current_user.id != doctor_id or not current_user.is_doctor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to set working hours"
        )
    
    # Validate time slots
    if working_hours.start_time >= working_hours.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time"
        )
    
    if working_hours.has_break:
        if not working_hours.break_start or not working_hours.break_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Break start and end times are required when has_break is True"
            )
        if working_hours.break_start >= working_hours.break_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Break start time must be before break end time"
            )
    
    # Create working hours
    db_working_hours = WorkingHours(
        doctor_id=doctor_id,
        **working_hours.dict()
    )
    
    db.add(db_working_hours)
    db.commit()
    db.refresh(db_working_hours)
    return db_working_hours

@router.get("/{doctor_id}/working-hours", response_model=List[WorkingHoursResponse])
async def get_working_hours(
    doctor_id: int,
    db: Session = Depends(get_db)
):
    working_hours = db.query(WorkingHours).filter(WorkingHours.doctor_id == doctor_id).all()
    return working_hours

@router.put("/{doctor_id}/working-hours/{working_hours_id}", response_model=WorkingHoursResponse)
async def update_working_hours(
    doctor_id: int,
    working_hours_id: int,
    working_hours: WorkingHoursCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify the current user is the doctor
    if current_user.id != doctor_id or not current_user.is_doctor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update working hours"
        )
    
    # Get existing working hours
    db_working_hours = db.query(WorkingHours).filter(
        WorkingHours.id == working_hours_id,
        WorkingHours.doctor_id == doctor_id
    ).first()
    
    if not db_working_hours:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Working hours not found"
        )
    
    # Update working hours
    for key, value in working_hours.dict().items():
        setattr(db_working_hours, key, value)
    
    db.commit()
    db.refresh(db_working_hours)
    return db_working_hours

@router.delete("/{doctor_id}/working-hours/{working_hours_id}")
async def delete_working_hours(
    doctor_id: int,
    working_hours_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify the current user is the doctor
    if current_user.id != doctor_id or not current_user.is_doctor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete working hours"
        )
    
    # Get existing working hours
    db_working_hours = db.query(WorkingHours).filter(
        WorkingHours.id == working_hours_id,
        WorkingHours.doctor_id == doctor_id
    ).first()
    
    if not db_working_hours:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Working hours not found"
        )
    
    db.delete(db_working_hours)
    db.commit()
    return {"message": "Working hours deleted successfully"}

@router.get("/{doctor_id}/available-slots")
async def get_available_slots(
    doctor_id: int,
    date_str: str = Query(..., alias="date"),
    db: Session = Depends(get_db)
):
    """
    Returns available 1-hour slots for a doctor on a specific date.
    """
    # Parse date
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    day_of_week = target_date.weekday()  # 0=Monday

    # Get working hours for that day
    working_hours = db.query(WorkingHours).filter(
        WorkingHours.doctor_id == doctor_id,
        WorkingHours.day_of_week == day_of_week,
        WorkingHours.is_available == True
    ).first()
    if not working_hours:
        return []

    # Get all appointments for that doctor on that date
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)
    from app.models.appointment import Appointment
    appointments = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.start_time >= start_of_day,
        Appointment.start_time < end_of_day
    ).all()
    booked_slots = set()
    for appt in appointments:
        booked_slots.add((appt.start_time.time(), appt.end_time.time()))

    # Generate all possible 1-hour slots within working hours, excluding breaks
    slots = []
    slot_start = datetime.combine(target_date, working_hours.start_time)
    slot_end = datetime.combine(target_date, working_hours.end_time)
    break_start = working_hours.break_start
    break_end = working_hours.break_end
    has_break = working_hours.has_break

    while slot_start + timedelta(hours=1) <= slot_end:
        slot_tuple = (slot_start.time(), (slot_start + timedelta(hours=1)).time())
        # Exclude if overlaps with break
        if has_break and break_start and break_end:
            if (slot_tuple[0] < break_end and slot_tuple[1] > break_start):
                slot_start += timedelta(hours=1)
                continue
        # Exclude if overlaps with any appointment
        overlap = False
        for booked in booked_slots:
            if (slot_tuple[0] < booked[1] and slot_tuple[1] > booked[0]):
                overlap = True
                break
        if not overlap:
            slots.append({
                "start_time": slot_tuple[0].strftime("%H:%M"),
                "end_time": slot_tuple[1].strftime("%H:%M")
            })
        slot_start += timedelta(hours=1)
    return slots 