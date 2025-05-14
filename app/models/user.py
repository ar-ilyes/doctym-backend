from sqlalchemy import Boolean, Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    phone_number = Column(String)
    address = Column(String)
    is_active = Column(Boolean, default=True)
    is_doctor = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Doctor specific fields
    specialty = Column(String, nullable=True)
    license_number = Column(String, nullable=True)
    clinic_name = Column(String, nullable=True)
    clinic_address = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    profile_picture = Column(String, nullable=True)
    social_media = Column(String, nullable=True)  # JSON string of social media links

    # Relationships
    notifications = relationship("Notification", back_populates="user")
    working_hours = relationship("WorkingHours", back_populates="doctor")
    doctor_appointments = relationship("Appointment", foreign_keys="Appointment.doctor_id", back_populates="doctor")
    patient_appointments = relationship("Appointment", foreign_keys="Appointment.patient_id", back_populates="patient")
    doctor_prescriptions = relationship("Prescription", foreign_keys="Prescription.doctor_id", back_populates="doctor")
    patient_prescriptions = relationship("Prescription", foreign_keys="Prescription.patient_id", back_populates="patient") 