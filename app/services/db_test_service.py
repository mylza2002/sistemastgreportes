from sqlalchemy.orm import Session
from app.repositories.db_test_repository import test_connection

def check_database(db: Session):
    result = test_connection(db)

    if result:
        return {"status": "success", "message": "Conexión a BD exitosa"}
    
    return {"status": "error", "message": "No se pudo conectar a la BD"}