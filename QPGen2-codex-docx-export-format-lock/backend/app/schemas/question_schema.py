from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

class QuestionDTO(BaseModel):
    """
    Universal Data Transfer Object representing a Question across the business logic layer.
    Allows standard attribute-style access and arbitrary extra metadata fields to be set safely.
    """
    model_config = ConfigDict(
        from_attributes=True,
        extra="allow",  # Safely permits dynamic runtime metadata attributes
    )

    id: Optional[int] = None
    module_number: int = Field(..., alias="module")
    text: str = Field(..., alias="question_text")
    marks: int
    course_outcome: str = Field(..., alias="co")
    bloom_level: str = Field(..., alias="rbt_level")
    topic: Optional[str] = None
    image_path: Optional[str] = None

    # Common optional fields with defaults to prevent AttributeError
    difficulty: str = "balanced"
    tags: list[str] = Field(default_factory=list)
    is_verified: bool = False
    source_doc_id: Optional[int] = None
    source_documents: list[str] = Field(default_factory=list)
    figure_image_paths: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)

    # Standard getter for dictionary-like operations
    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item, None)
