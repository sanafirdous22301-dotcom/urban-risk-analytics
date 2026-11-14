
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from database.session import get_db
from backend.schemas import DatasetCreate


router = APIRouter(
    prefix="/api/datasets",
    tags=["Datasets"]
)


# GET: Retrieve registered datasets
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


# POST: Register a dataset
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
        result = db.execute(query, dataset.model_dump())
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
