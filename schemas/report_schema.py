from typing import Any, Literal
from pydantic import BaseModel, Field

class EnvironmentalMetric(BaseModel):
    name: str
    value: str | float | int | None = None
    unit: str | None = None
    status: Literal[
        "reported", "calculated", "partial", "unavailable",
        "not_applicable", "not_verified", "unknown"
    ] = "unknown"
    source_document: str | None = None
    notes: str | None = None

class EnvironmentalReportData(BaseModel):
    project_id: int
    project_name: str
    reporting_period: str = "Not stated"
    project_overview: str = ""
    energy_metrics: list[EnvironmentalMetric] = Field(default_factory=list)
    water_metrics: list[EnvironmentalMetric] = Field(default_factory=list)
    emissions_metrics: list[EnvironmentalMetric] = Field(default_factory=list)
    waste_metrics: list[EnvironmentalMetric] = Field(default_factory=list)
    clearances_assessments: list[EnvironmentalMetric] = Field(default_factory=list)
    compliance_metrics: list[EnvironmentalMetric] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    source_documents: list[str] = Field(default_factory=list)
    draft_report_text: str = ""
    synthetic_data: bool = False
