
from datetime import date
from pydantic import BaseModel, Field, model_validator


class DatasetCreate(BaseModel):
    dataset_name: str = Field(min_length=1, max_length=150)
    source_name: str = Field(min_length=1, max_length=200)
    file_path: str | None = None
    version_label: str | None = Field(default=None, max_length=100)
    date_range_start: date | None = None
    date_range_end: date | None = None
    record_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_date_range(self):
        if (
            self.date_range_start
            and self.date_range_end
            and self.date_range_start > self.date_range_end
        ):
            raise ValueError("Start date cannot be after end date")

        return self
