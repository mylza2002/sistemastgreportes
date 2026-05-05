from app.services.report_engine import generate_report

def create_report(db, request):

    return generate_report(
        request.reporte,
        db,
        request.dict()
    )