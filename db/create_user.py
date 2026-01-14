from models.models import User
from .database import engine, SessionLocal, Base
from .security import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

db.add(
    User(
        username="admin",
        password_hash=hash_password("1234")
    )
)

db.commit()
db.close()

print("User created")
