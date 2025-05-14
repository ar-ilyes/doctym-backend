from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import enum
from app.database import Base
from sqlalchemy.sql import func

class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"))
    patient_id = Column(Integer, ForeignKey("users.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    qr_code = Column(String, unique=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    doctor = relationship("User", foreign_keys=[doctor_id], back_populates="doctor_appointments")
    patient = relationship("User", foreign_keys=[patient_id], back_populates="patient_appointments")
    prescription = relationship("Prescription", back_populates="appointment", uselist=False)
    notifications = relationship("Notification", back_populates="appointment") 