
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# Locate the project's root .env file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Read database configuration
db_url = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME")
)

# Create SQLAlchemy engine
engine = create_engine(
    db_url,
    pool_pre_ping=True,
    echo=False
)

# Test database connection
if __name__ == "__main__":
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT DATABASE(), VERSION()")
            )

            database_name, mysql_version = result.fetchone()

            print("========== DATABASE CONNECTION ==========")
            print("Connection: Successful")
            print("Database:", database_name)
            print("MySQL Version:", mysql_version)

    except Exception as error:
        print("Database connection failed.")
        print("Error:", error)
