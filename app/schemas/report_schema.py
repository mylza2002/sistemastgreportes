from pydantic import BaseModel
from typing import Optional

class ReportRequest(BaseModel):

    reporte: str

    # fecha_inicio: Optional[str] = None
    # fecha_fin: Optional[str] = None

    # modalidad: Optional[str] = None
    # profesor: Optional[int] = None