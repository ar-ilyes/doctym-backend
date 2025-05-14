from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine
from app.models.user import Base as UserBase
from app.models.working_hours import Base as WorkingHoursBase
from app.models.appointment import Base as AppointmentBase
from app.models.prescription import Base as PrescriptionBase
from app.models.notification import Base as NotificationBase
from app.routers import auth, working_hours, appointments, prescriptions, doctors, notifications
from app.core.scheduler import start_scheduler

# Create database tables
UserBase.metadata.create_all(bind=engine)
WorkingHoursBase.metadata.create_all(bind=engine)
AppointmentBase.metadata.create_all(bind=engine)
PrescriptionBase.metadata.create_all(bind=engine)
NotificationBase.metadata.create_all(bind=engine)

app = FastAPI(title="Doctor Appointment API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(doctors.router)
app.include_router(working_hours.router)
app.include_router(appointments.router)
app.include_router(prescriptions.router)
app.include_router(notifications.router)

# Start the scheduler
@app.on_event("startup")
async def startup_event():
    start_scheduler()

@app.get("/")
async def root():
    return {"message": "Welcome to Doctor Appointment API"} 