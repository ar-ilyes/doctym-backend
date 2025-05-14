from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"))
    patient_id = Column(Integer, ForeignKey("users.id"))
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    diagnosis = Column(Text)
    medications = Column(Text)  # JSON string of medications
    instructions = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    doctor = relationship("User", foreign_keys=[doctor_id], back_populates="doctor_prescriptions")
    patient = relationship("User", foreign_keys=[patient_id], back_populates="patient_prescriptions")
    appointment = relationship("Appointment", back_populates="prescription")
    notifications = relationship("Notification", back_populates="prescription") 