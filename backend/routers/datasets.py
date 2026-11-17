
import csv
import io
import re
import uuid

from datetime import date
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form
)

from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from pydantic import ValidationError

from database.session import get_db
from backend.schemas import DatasetCreate


router = APIRouter(
    prefix="/api/datasets",
    tags=["Datasets"]
)


# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Uploaded CSV storage directory
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"

# Maximum upload size: 50 MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


# =============================================
# GET: RETRIEVE REGISTERED DATASETS
# =============================================

@router.get("/")
def get_datasets(db: Session = Depends(get_db)):

    query = text("""
        SELECT
            dataset_id,
            dataset_name,
            source_name,
            version_label,
            date_range_start,
            date_range_end,
            retrieved_at,
            record_count
        FROM dataset_versions
        ORDER BY retrieved_at DESC
    """)

    result = db.execute(query)

    datasets = [
        dict(row)
        for row in result.mappings().all()
    ]

    return {
        "total": len(datasets),
        "datasets": datasets
    }


# =============================================
# POST: REGISTER DATASET METADATA
# =============================================

@router.post("/", status_code=201)
def register_dataset(
    dataset: DatasetCreate,
    db: Session = Depends(get_db)
):

    query = text("""
        INSERT INTO dataset_versions (
            dataset_name,
            source_name,
            file_path,
            version_label,
            date_range_start,
            date_range_end,
            record_count
        )
        VALUES (
            :dataset_name,
            :source_name,
            :file_path,
            :version_label,
            :date_range_start,
            :date_range_end,
            :record_count
        )
    """)

    try:

        result = db.execute(
            query,
            dataset.model_dump()
        )

        db.commit()

        return {
            "message": "Dataset registered successfully",
            "dataset_id": result.lastrowid,
            "dataset_name": dataset.dataset_name
        }

    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Dataset with this name and version already exists"
        )

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Dataset registration failed"
        )


# =============================================
# CSV VALIDATION HELPER
# =============================================

def validate_csv_content(content: bytes):

    # Check text encoding
    try:

        csv_text = content.decode("utf-8-sig")

    except UnicodeDecodeError:

        raise HTTPException(
            status_code=400,
            detail="CSV must use UTF-8 encoding."
        )


    # Read CSV structure
    try:

        reader = csv.reader(
            io.StringIO(csv_text, newline=""),
            strict=True
        )

        headers = next(reader, None)

        if not headers:

            raise HTTPException(
                status_code=400,
                detail="CSV file is empty or has no header row."
            )


        headers = [
            header.strip()
            for header in headers
        ]


        # Check column names
        if any(not header for header in headers):

            raise HTTPException(
                status_code=400,
                detail="CSV contains an empty column name."
            )


        # Check duplicate column names
        normalized_headers = [
            header.casefold()
            for header in headers
        ]

        if len(normalized_headers) != len(set(normalized_headers)):

            raise HTTPException(
                status_code=400,
                detail="CSV contains duplicate column names."
            )


        # Count and validate data rows
        record_count = 0

        for row_number, row in enumerate(reader, start=2):

            # Skip completely blank rows
            if not row or all(not value.strip() for value in row):
                continue

            if len(row) != len(headers):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid CSV structure at row {row_number}. "
                        "The number of fields does not match the header."
                    )
                )

            record_count += 1


    except csv.Error:

        raise HTTPException(
            status_code=400,
            detail="Unable to parse the CSV file."
        )


    if record_count == 0:

        raise HTTPException(
            status_code=400,
            detail="CSV contains no data records."
        )


    return headers, record_count


# =============================================
# POST: UPLOAD AND REGISTER CSV DATASET
# =============================================

@router.post("/upload", status_code=201)
async def upload_dataset(

    file: UploadFile = File(...),

    dataset_name: str = Form(..., min_length=1, max_length=150),

    source_name: str = Form(..., min_length=1, max_length=200),

    version_label: str | None = Form(default=None, max_length=100),

    date_range_start: date | None = Form(default=None),

    date_range_end: date | None = Form(default=None),

    db: Session = Depends(get_db)

):

    saved_file = None

    try:

        # =====================================
        # 1. CHECK FILE NAME AND EXTENSION
        # =====================================

        original_filename = file.filename or ""

        if not original_filename.lower().endswith(".csv"):

            raise HTTPException(
                status_code=415,
                detail="Only CSV files are currently supported."
            )


        # =====================================
        # 2. READ FILE WITH SIZE LIMIT
        # =====================================

        content = await file.read(
            MAX_UPLOAD_BYTES + 1
        )

        if len(content) > MAX_UPLOAD_BYTES:

            raise HTTPException(
                status_code=413,
                detail="File exceeds the 50 MB upload limit."
            )


        if not content:

            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty."
            )


        # =====================================
        # 3. VALIDATE CSV CONTENT
        # =====================================

        headers, record_count = validate_csv_content(
            content
        )


        # =====================================
        # 4. VALIDATE DATASET METADATA
        # =====================================

        # Generate a safe, unique file name
        original_stem = Path(original_filename).stem

        safe_stem = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            original_stem
        ).strip("_")

        if not safe_stem:
            safe_stem = "dataset"


        unique_filename = (
            uuid.uuid4().hex[:12]
            + "_"
            + safe_stem
            + ".csv"
        )


        # Store a relative path in MySQL
        relative_path = (
            Path("data") /
            "uploads" /
            unique_filename
        ).as_posix()


        dataset = DatasetCreate(

            dataset_name=dataset_name.strip(),

            source_name=source_name.strip(),

            file_path=relative_path,

            version_label=(
                version_label.strip()
                if version_label and version_label.strip()
                else None
            ),

            date_range_start=date_range_start,

            date_range_end=date_range_end,

            record_count=record_count

        )


        # =====================================
        # 5. STORE THE REAL CSV FILE
        # =====================================

        UPLOAD_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        saved_file = UPLOAD_DIR / unique_filename

        saved_file.write_bytes(content)


        # =====================================
        # 6. REGISTER FILE IN MYSQL
        # =====================================

        query = text("""
            INSERT INTO dataset_versions (
                dataset_name,
                source_name,
                file_path,
                version_label,
                date_range_start,
                date_range_end,
                record_count
            )
            VALUES (
                :dataset_name,
                :source_name,
                :file_path,
                :version_label,
                :date_range_start,
                :date_range_end,
                :record_count
            )
        """)


        result = db.execute(
            query,
            dataset.model_dump()
        )

        db.commit()


        # =====================================
        # 7. RETURN SUCCESS RESPONSE
        # =====================================

        return {

            "message": "CSV uploaded and registered successfully",

            "dataset_id": result.lastrowid,

            "dataset_name": dataset.dataset_name,

            "file_path": relative_path,

            "record_count": record_count,

            "columns": headers

        }


    except ValidationError as error:

        db.rollback()

        if saved_file and saved_file.exists():
            saved_file.unlink()

        raise HTTPException(
            status_code=422,
            detail=error.errors()
        )


    except IntegrityError:

        db.rollback()

        if saved_file and saved_file.exists():
            saved_file.unlink()

        raise HTTPException(
            status_code=409,
            detail="Dataset with this name and version already exists."
        )


    except HTTPException:

        db.rollback()

        if saved_file and saved_file.exists():
            saved_file.unlink()

        raise


    except Exception:

        db.rollback()

        if saved_file and saved_file.exists():
            saved_file.unlink()

        raise HTTPException(
            status_code=500,
            detail="CSV upload and registration failed."
        )


    finally:

        await file.close()
