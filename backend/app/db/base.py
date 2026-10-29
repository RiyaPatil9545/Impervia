from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models so that Base.metadata has the complete schema definition
import app.models  # noqa: F401
