from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from app.database import get_db
from app.services.report_service import create_report
from app.schemas.report_schema import ReportRequest

router = APIRouter(prefix="/reports")

@router.post("/generate")
def generate(request: ReportRequest, db: Session = Depends(get_db)):

    file_path = create_report(db, request)

    filename = os.path.basename(file_path)

    return FileResponse(
        path=file_path,
        filename=filename,  # 👈 nombre del archivo al descargar
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )