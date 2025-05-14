from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.notification import Notification

scheduler = BackgroundScheduler()

def create_appointment_notification(db: Session, appointment: Appointment, notification_type: str):
    if notification_type == "reminder":
        title = "Appointment Reminder"
        message = f"Your appointment with Dr. {appointment.doctor.full_name} is scheduled for {appointment.start_time.strftime('%Y-%m-%d %H:%M')}"
    elif notification_type == "confirmation":
        title = "Appointment Confirmed"
        message = f"Your appointment with Dr. {appointment.doctor.full_name} has been confirmed for {appointment.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    notification = Notification(
        user_id=appointment.patient_id,
        title=title,
        message=message,
        type="appointment",
        appointment_id=appointment.id
    )
    db.add(notification)
    db.commit()

def check_upcoming_appointments():
    db = SessionLocal()
    try:
        # Get appointments scheduled for the next 24 hours
        tomorrow = datetime.now() + timedelta(days=1)
        appointments = db.query(Appointment).filter(
            Appointment.start_time <= tomorrow,
            Appointment.start_time > datetime.now(),
            Appointment.status == AppointmentStatus.SCHEDULED
        ).all()
        
        for appointment in appointments:
            # Create reminder notification
            create_appointment_notification(db, appointment, "reminder")
    finally:
        db.close()

def start_scheduler():
    # Schedule appointment reminder check every hour
    scheduler.add_job(
        check_upcoming_appointments,
        trigger=IntervalTrigger(hours=1),
        id='check_appointments',
        replace_existing=True
    )
    scheduler.start() 