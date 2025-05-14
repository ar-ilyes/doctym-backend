from sqlalchemy import Column, Integer, String, ForeignKey, Time, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class WorkingHours(Base):
    __tablename__ = "working_hours"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"))
    day_of_week = Column(Integer)  # 0-6 (Monday-Sunday)
    start_time = Column(Time)
    end_time = Column(Time)
    has_break = Column(Boolean, default=False)
    break_start = Column(Time, nullable=True)
    break_end = Column(Time, nullable=True)
    is_available = Column(Boolean, default=True)

    # Relationships
    doctor = relationship("User", back_populates="working_hours") 