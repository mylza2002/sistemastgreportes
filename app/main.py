from fastapi import FastAPI
from app.api.v1 import report_routes

app = FastAPI(
    title="Sistema de Reportes TG",
    version="1.0"
)

app.include_router(report_routes.router)


# Para ejecutar desde laravel
# En el controller
""" $response = Http::withHeaders([
    'x-api-key' => 'super_secret_key'
])->get('http://127.0.0.1:8000/api/v1/reports/generate'); """


from app.api import test_db

app.include_router(test_db.router, prefix="/api")