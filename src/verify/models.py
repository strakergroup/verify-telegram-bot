from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Language(BaseModel):
    """A supported language from the Verify API."""

    id: str
    code: str
    name: str


class ProjectStatus(str, Enum):
    ARCHIVED = "ARCHIVED"
    ANALYZING = "ANALYZING"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    UNSUCCESSFUL = "UNSUCCESSFUL"
    COMPLETED = "COMPLETED"


STATUS_EMOJI = {
    ProjectStatus.ANALYZING: "\u23f3",
    ProjectStatus.PENDING_PAYMENT: "\U0001f4b3",
    ProjectStatus.IN_PROGRESS: "\u2699\ufe0f",
    ProjectStatus.COMPLETED: "\u2705",
    ProjectStatus.UNSUCCESSFUL: "\u274c",
    ProjectStatus.ARCHIVED: "\U0001f4e6",
}


class TargetLanguage(BaseModel):
    uuid: str
    code: str
    label: str
    name: str
    site_shortname: str = ""


class TargetFile(BaseModel):
    language_uuid: str
    status: str
    target_file_uuid: str
    url: str = ""


class ProjectReport(BaseModel):
    language_uuid: str
    word_count: int = 0
    char_count: int = 0
    total_word_count: int = 0


class SourceFile(BaseModel):
    file_uuid: str
    filename: str
    report: ProjectReport | None = None
    target_files: list[TargetFile] | None = None
    url: str = ""


class Project(BaseModel):
    uuid: str
    client_uuid: str = ""
    title: str | None = None
    status: ProjectStatus
    target_languages: list[TargetLanguage] = []
    source_files: list[SourceFile] = []
    archived: bool = False
    callback_uri: str | None = None
    due_date: datetime | None = None
    created_at: datetime
    modified_at: datetime


class CreateProjectResponse(BaseModel):
    project_id: str
    message: str | None = None


class GetLanguagesResponse(BaseModel):
    data: list[Language]


class GetProjectResponse(BaseModel):
    data: Project


class GetProjectsResponse(BaseModel):
    data: list[Project]


class GetTokenBalanceResponse(BaseModel):
    balance: int


class GetProjectWithCostResponse(BaseModel):
    data: Project
    token_cost: int = 0
