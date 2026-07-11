import os
import random
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

# Load environment variables securely
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./reports.db")

# SQLAlchemy Setup
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} # Required for SQLite
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Database Model ---
class DBReport(Base):
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    reporter_name = Column(String, index=True)
    incident_description = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)

# Create tables on startup
Base.metadata.create_all(bind=engine)

# --- Pydantic Models (Strict Validation) ---
class ReportCreate(BaseModel):
    reporter_name: str = Field(..., min_length=1, max_length=100, description="Alias or name of the reporter")
    incident_description: str = Field(..., min_length=10, max_length=5000, description="Detailed description of the incident")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Geographic latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Geographic longitude")

class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    reporter_name: str
    incident_description: str
    latitude: float
    longitude: float

# --- Dependencies ---
def get_db():
    """Dependency to manage database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Cybersecurity Feature: Spatial Obfuscation ---
def obfuscate_coordinates(lat: float, lon: float) -> tuple[float, float]:
    """
    Applies spatial obfuscation to protect whistleblower privacy.
    Adds a random mathematical offset of up to 0.02 degrees (approx 2.2km) 
    to both latitude and longitude.
    """
    # Generate random noise between -0.02 and +0.02
    noise_lat = random.uniform(-0.02, 0.02)
    noise_lon = random.uniform(-0.02, 0.02)
    
    # Apply noise
    obf_lat = lat + noise_lat
    obf_lon = lon + noise_lon
    
    # Clamp values to ensure they remain within valid global geographical bounds
    obf_lat = max(-90.0, min(90.0, obf_lat))
    obf_lon = max(-180.0, min(180.0, obf_lon))
    
    return obf_lat, obf_lon

# --- FastAPI Application ---
app = FastAPI(
    title="Secure GIS Whistleblower Portal",
    description="Phase 1: Privacy-first environmental incident reporting.",
    version="1.0.0"
)

# --- CORS Configuration ---
# Allows the frontend to communicate with the backend securely.
# In a production environment, replace "*" with your specific frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Endpoints ---

@app.post("/api/report", response_model=ReportResponse, status_code=201)
def create_report(report: ReportCreate, db: Session = Depends(get_db)):
    """
    Receives a whistleblower report, obfuscates the exact coordinates 
    to protect the user's identity, and saves it to the database.
    """
    # 1. Obfuscate coordinates BEFORE saving
    obf_lat, obf_lon = obfuscate_coordinates(report.latitude, report.longitude)
    
    # 2. Create database record with obfuscated data
    db_report = DBReport(
        reporter_name=report.reporter_name,
        incident_description=report.incident_description,
        latitude=obf_lat,
        longitude=obf_lon
    )
    
    # 3. Save to database
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    
    return db_report

@app.get("/api/reports", response_model=list[ReportResponse])
def get_reports(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieves all stored reports. Note: All coordinates returned 
    are already obfuscated.
    """
    reports = db.query(DBReport).offset(skip).limit(limit).all()
    return reports

# --- Serve Frontend ---
@app.get("/")
async def serve_frontend():
    """
    Serves the index.html file at the root URL.
    """
    return FileResponse("index.html")