from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
import json
from app.database import get_db
from app.models.user import User
from app.models.appointment import Appointment, AppointmentStatus
from app.models.working_hours import WorkingHours
from app.models.notification import Notification
from app.core.security import get_current_active_user
from pydantic import BaseModel

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

class AppointmentCreate(BaseModel):
    doctor_id: int
    start_time: datetime

class AppointmentResponse(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    qr_code: str
    notes: str = None

    class Config:
        orm_mode = True

def generate_qr_code(appointment_id: int, db: Session) -> str:
    # Get appointment details
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Create verification data
    verification_data = {
        "appointment_id": appointment_id,
        "patient_id": appointment.patient_id,
        "patient_name": appointment.patient.full_name,
        "appointment_time": appointment.start_time.isoformat(),
        "status": appointment.status.value
    }
    
    # Convert to JSON string
    qr_data = json.dumps(verification_data)
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def is_time_slot_available(
    db: Session,
    doctor_id: int,
    start_time: datetime,
    end_time: datetime
) -> bool:
    # Check if there's any overlapping appointment
    overlapping_appointment = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status != AppointmentStatus.CANCELLED,
        (
            (Appointment.start_time <= start_time) & (Appointment.end_time > start_time) |
            (Appointment.start_time < end_time) & (Appointment.end_time >= end_time) |
            (Appointment.start_time >= start_time) & (Appointment.end_time <= end_time)
        )
    ).first()
    
    if overlapping_appointment:
        return False
    
    # Check if the time slot is within doctor's working hours
    day_of_week = start_time.weekday()
    working_hours = db.query(WorkingHours).filter(
        WorkingHours.doctor_id == doctor_id,
        WorkingHours.day_of_week == day_of_week,
        WorkingHours.is_available == True
    ).first()
    
    if not working_hours:
        return False
    
    appointment_start_time = start_time.time()
    appointment_end_time = end_time.time()
    
    if appointment_start_time < working_hours.start_time or appointment_end_time > working_hours.end_time:
        return False
    
    if working_hours.has_break:
        if (working_hours.break_start <= appointment_start_time <= working_hours.break_end or
            working_hours.break_start <= appointment_end_time <= working_hours.break_end):
            return False
    
    return True

@router.post("", response_model=AppointmentResponse)
async def create_appointment(
    appointment: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify the current user is a patient
    if current_user.is_doctor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctors cannot create appointments"
        )
    
    # Calculate end time (1 hour duration)
    end_time = appointment.start_time + timedelta(hours=1)
    
    # Check if the time slot is available
    if not is_time_slot_available(db, appointment.doctor_id, appointment.start_time, end_time):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Time slot is not available"
        )
    
    # Create appointment
    db_appointment = Appointment(
        doctor_id=appointment.doctor_id,
        patient_id=current_user.id,
        start_time=appointment.start_time,
        end_time=end_time,
        status=AppointmentStatus.SCHEDULED
    )
    
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    
    # Generate QR code with verification data
    qr_code = generate_qr_code(db_appointment.id, db)
    db_appointment.qr_code = qr_code
    db.commit()
    db.refresh(db_appointment)
    
    # Create confirmation notification
    notification = Notification(
        user_id=current_user.id,
        title="Appointment Confirmed",
        message=f"Your appointment with Dr. {db_appointment.doctor.full_name} has been confirmed for {db_appointment.start_time.strftime('%Y-%m-%d %H:%M')}",
        type="appointment",
        appointment_id=db_appointment.id
    )
    db.add(notification)
    db.commit()
    
    return db_appointment

@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Verify the current user is either the doctor or the patient
    if current_user.id not in [appointment.doctor_id, appointment.patient_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this appointment"
        )
    
    return appointment

@router.get("/doctor/{doctor_id}", response_model=List[AppointmentResponse])
async def get_doctor_appointments(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify the current user is the doctor
    if current_user.id != doctor_id or not current_user.is_doctor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view these appointments"
        )
    
    appointments = db.query(Appointment).filter(Appointment.doctor_id == doctor_id).all()
    return appointments

@router.get("/patient/{patient_id}", response_model=List[AppointmentResponse])
async def get_patient_appointments(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify the current user is the patient
    if current_user.id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view these appointments"
        )
    
    appointments = db.query(Appointment).filter(Appointment.patient_id == patient_id).all()
    return appointments

@router.put("/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: int,
    status: AppointmentStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Verify the current user is the doctor
    if current_user.id != appointment.doctor_id or not current_user.is_doctor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update appointment status"
        )
    
    appointment.status = status
    db.commit()
    db.refresh(appointment)
    return {"message": "Appointment status updated successfully"}

@router.post("/{appointment_id}/check-in")
async def check_in_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Verify the current user is the doctor
    if current_user.id != appointment.doctor_id or not current_user.is_doctor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to check in appointments"
        )
    
    # Update appointment status
    appointment.status = AppointmentStatus.IN_PROGRESS
    db.commit()
    db.refresh(appointment)
    return {"message": "Appointment checked in successfully"}

@router.get("/{appointment_id}/qr-code")
async def get_appointment_qr_code(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Verify the current user is either the doctor or the patient
    if current_user.id not in [appointment.doctor_id, appointment.patient_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this QR code"
        )
    
    # Generate QR code with verification data
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    verification_data = {
        "appointment_id": appointment_id,
        "patient_id": appointment.patient_id,
        "patient_name": appointment.patient.full_name,
        "appointment_time": appointment.start_time.isoformat(),
        "status": appointment.status.value
    }
    qr.add_data(json.dumps(verification_data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    
    return Response(content=img_bytes, media_type="image/png") 