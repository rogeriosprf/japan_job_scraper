from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Salary(BaseModel):
    min: Optional[int] = None
    max: Optional[int] = None
    currency: str = "JPY"
    text: Optional[str] = None


class Company(BaseModel):
    name: str
    slug: Optional[str] = None


class Location(BaseModel):
    city: Optional[str] = None
    country: str = "Japan"

    remote_policy: Optional[str] = None
    candidate_location: Optional[str] = None


class Requirements(BaseModel):
    japanese_level: Optional[str] = None
    english_level: Optional[str] = None
    seniority: Optional[str] = None


class Job(BaseModel):
    # identificação
    job_key: str
    source: str

    # vaga
    title: str

    company: Company

    location: Location

    # remuneração
    salary: Optional[Salary] = None

    # tecnologias / categorias
    skills: List[str] = Field(default_factory=list)

    # requisitos
    requirements: Requirements = Field(
        default_factory=Requirements
    )

    # contratação
    employment_type: Optional[str] = None

    # imigração
    # None = desconhecido
    # True = suporta visto
    # False = não suporta visto
    visa_sponsorship: Optional[bool] = None

    # idioma principal da vaga
    # exemplos:
    # English only
    # Japanese required
    # Japanese preferred
    job_language: Optional[str] = None

    # status da vaga
    # None = não sabemos
    active: Optional[bool] = None

    # conteúdo
    description: Optional[str] = None

    # candidatura
    application_url: Optional[str] = None

    # datas
    published_at: Optional[str] = None
    extracted_at: Optional[str] = None

    # debug / origem
    raw_payload: Optional[Dict[str, Any]] = None