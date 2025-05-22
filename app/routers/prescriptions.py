from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import json
from datetime import datetime
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.database import get_db
from app.models.user import User
from app.models.prescription import Prescription
from pydantic import BaseModel

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])

class Medication(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str
    instructions: str = None

class PrescriptionCreate(BaseModel):
    patient_id: int
    appointment_id: int = None
    diagnosis: str
    medications: List[Medication]
    instructions: str

class PrescriptionResponse(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    appointment_id: int = None
    diagnosis: str
    medications: List[Medication]
    instructions: str
    created_at: datetime

    class Config:
        orm_mode = True



@router.post("/bulk", status_code=status.HTTP_200_OK)
async def create_prescriptions_bulk(
    prescriptions: List[PrescriptionCreate],
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_active_user)
):
    # Track how many were created and how many already existed
    created_count = 0
    existing_count = 0
    
    for prescription_data in prescriptions:
        # Check if prescription already exists
        existing_prescription = db.query(Prescription).filter(
            Prescription.appointment_id == prescription_data.appointment_id,
            Prescription.patient_id == prescription_data.patient_id,
            Prescription.diagnosis == prescription_data.diagnosis
        ).first()
        
        if existing_prescription:
            existing_count += 1
            continue
        
        # Convert medications to JSON string
        medications_json = json.dumps([med.dict() for med in prescription_data.medications])
        
        # Create new prescription
        new_prescription = Prescription(
            patient_id=prescription_data.patient_id,
            appointment_id=prescription_data.appointment_id,
            doctor_id=2,  # You may want to get this from authentication or pass it in
            diagnosis=prescription_data.diagnosis,
            medications=medications_json,  # Store as JSON string
            instructions=prescription_data.instructions
        )
        
        db.add(new_prescription)
        created_count += 1
    
    # Commit all changes at once
    db.commit()
    
    return {
        "status": "success",
        "message": f"Processed {len(prescriptions)} prescriptions. Created: {created_count}, Already existed: {existing_count}"
    }

@router.post("", response_model=PrescriptionResponse)
async def create_prescription(
    prescription: PrescriptionCreate,
    db: Session = Depends(get_db)
):
    # Convert medications list to JSON string
    medications_json = json.dumps([med.dict() for med in prescription.medications])
    
    # Create prescription
    db_prescription = Prescription(
        doctor_id=2,#TODO: change to current user
        patient_id=prescription.patient_id,
        appointment_id=prescription.appointment_id,
        diagnosis=prescription.diagnosis,
        medications=medications_json,  # Store as JSON string
        instructions=prescription.instructions
    )
    
    db.add(db_prescription)
    db.commit()
    db.refresh(db_prescription)
    
    # Convert medications back to list for response
    db_prescription.medications = prescription.medications
    return db_prescription

@router.get("/{prescription_id}", response_model=PrescriptionResponse)
async def get_prescription(
    prescription_id: int,
    db: Session = Depends(get_db)
):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found"
        )
    
    return prescription

@router.get("/patient/{patient_id}", response_model=List[PrescriptionResponse])
async def get_patient_prescriptions(
    patient_id: int,
    db: Session = Depends(get_db)
):
    prescriptions = db.query(Prescription).filter(Prescription.patient_id == patient_id).all()
    for prescription in prescriptions:
        prescription.medications = json.loads(prescription.medications)
    return prescriptions

@router.get("/doctor/{doctor_id}", response_model=List[PrescriptionResponse])
async def get_doctor_prescriptions(
    doctor_id: int,
    db: Session = Depends(get_db)
):
    prescriptions = db.query(Prescription).filter(Prescription.doctor_id == doctor_id).all()
    for prescription in prescriptions:
        prescription.medications = json.loads(prescription.medications)
    return prescriptions

@router.post("/{prescription_id}/download")
async def download_prescription(
    prescription_id: int,
    db: Session = Depends(get_db)
):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found"
        )
    
    # Get doctor and patient details
    doctor = db.query(User).filter(User.id == prescription.doctor_id).first()
    patient = db.query(User).filter(User.id == prescription.patient_id).first()
    
    # Create HTML content for PDF
    medications = json.loads(prescription.medications)
    html_content = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .section {{ margin-bottom: 20px; }}
                .medication {{ margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Medical Prescription</h1>
                <p>Date: {prescription.created_at.strftime('%Y-%m-%d')}</p>
            </div>
            
            <div class="section">
                <h2>Doctor Information</h2>
                <p>Name: {doctor.full_name}</p>
                <p>License: {doctor.license_number}</p>
                <p>Clinic: {doctor.clinic_name}</p>
            </div>
            
            <div class="section">
                <h2>Patient Information</h2>
                <p>Name: {patient.full_name}</p>
                <p>ID: {patient.id}</p>
            </div>
            
            <div class="section">
                <h2>Diagnosis</h2>
                <p>{prescription.diagnosis}</p>
            </div>
            
            <div class="section">
                <h2>Medications</h2>
                {''.join(f'''
                <div class="medication">
                    <h3>{med['name']}</h3>
                    <p>Dosage: {med['dosage']}</p>
                    <p>Frequency: {med['frequency']}</p>
                    <p>Duration: {med['duration']}</p>
                    {f"<p>Additional Instructions: {med['instructions']}</p>" if med.get('instructions') else ""}
                </div>
                ''' for med in medications)}
            </div>
            
            <div class="section">
                <h2>Additional Instructions</h2>
                <p>{prescription.instructions}</p>
            </div>
            
            <div class="section">
                <p>Doctor's Signature: _________________</p>
                <p>Date: _________________</p>
            </div>
        </body>
    </html>
    """
    
    # Convert HTML to PDF
    pdf = pdfkit.from_string(html_content, False)
    
    return {
        "pdf_content": pdf,
        "filename": f"prescription_{prescription_id}.pdf"
    }

@router.get("/{prescription_id}/pdf")
async def get_prescription_pdf(
    prescription_id: int,
    db: Session = Depends(get_db)
):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found"
        )
    
    # Get doctor and patient details
    doctor = db.query(User).filter(User.id == prescription.doctor_id).first()
    patient = db.query(User).filter(User.id == prescription.patient_id).first()
    
    # Create PDF
    filename = f"prescription_{prescription_id}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    story.append(Paragraph("Medical Prescription", title_style))
    
    # Doctor Information
    story.append(Paragraph("Doctor Information:", styles['Heading2']))
    story.append(Paragraph(f"Name: {doctor.full_name}", styles['Normal']))
    story.append(Paragraph(f"License Number: {doctor.license_number}", styles['Normal']))
    story.append(Paragraph(f"Clinic: {doctor.clinic_name}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Patient Information
    story.append(Paragraph("Patient Information:", styles['Heading2']))
    story.append(Paragraph(f"Name: {patient.full_name}", styles['Normal']))
    story.append(Paragraph(f"Phone: {patient.phone_number}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Diagnosis
    story.append(Paragraph("Diagnosis:", styles['Heading2']))
    story.append(Paragraph(prescription.diagnosis, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Medications
    story.append(Paragraph("Medications:", styles['Heading2']))
    medications = json.loads(prescription.medications)
    med_data = [["Medication", "Dosage", "Frequency", "Duration"]]
    for med in medications:
        med_data.append([
            med['name'],
            med['dosage'],
            med['frequency'],
            med['duration']
        ])
    
    med_table = Table(med_data)
    med_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(med_table)
    story.append(Spacer(1, 20))
    
    # Instructions
    story.append(Paragraph("Instructions:", styles['Heading2']))
    story.append(Paragraph(prescription.instructions, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Date
    story.append(Paragraph(f"Date: {prescription.created_at.strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    
    # Build PDF
    doc.build(story)
    
    # Return PDF file
    return FileResponse(
        filename,
        media_type='application/pdf',
        filename=f"prescription_{prescription_id}.pdf"
    )

@router.get("/appointment/{appointment_id}", response_model=PrescriptionResponse)
async def get_prescription_by_appointment(
    appointment_id: int,
    db: Session = Depends(get_db)
):
    prescription = db.query(Prescription).filter(Prescription.appointment_id == appointment_id).first()
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No prescription found for this appointment"
        )
    
    prescription.medications = json.loads(prescription.medications)
    return prescription 


