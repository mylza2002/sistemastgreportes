from sqlalchemy.orm import Session
from sqlalchemy import text

def test_connection(db: Session):
    result = db.execute(text("SELECT 1"))
    return result.fetchone()