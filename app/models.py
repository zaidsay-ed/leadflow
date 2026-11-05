from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ContactCreate(BaseModel):
    name: str
    email: str
    company: Optional[str] = None
    title: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else v


class SequenceStep(BaseModel):
    day: int = Field(ge=0)
    subject: str
    body: str


class SequenceCreate(BaseModel):
    name: str
    steps: list[SequenceStep] = Field(min_length=1)

    @field_validator("steps")
    @classmethod
    def sort_steps(cls, steps):
        return sorted(steps, key=lambda s: s.day)


class EnrollRequest(BaseModel):
    contact_id: str