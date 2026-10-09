from pathlib import Path
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from config import REPORT_OUTPUT_DIR
from services.supabase_service import fetch_project_and_files, download_storage_object
from services.pdf_service import extract_pdf_text
from agents.extraction_agent import extract_report_data
from agents.validation_agent import validate_report
from reports.pdf_report import create_pdf_report

class AgentState(TypedDict, total=False):
    project_id: int
    project: dict
    file_row: dict
    document_texts: dict[str, str]
    report_data: object
    output_json: str
    output_pdf: str
    error: str

FILE_FIELDS = [
    ("project_details_file", "project_details"),
    ("energy_record", "energy"),
    ("water_record", "water"),
    ("emission_record", "emissions"),
    ("waste_record", "waste"),
    ("environmental_clearances_assessments", "clearances"),
    ("environmental_compliance_records", "compliance"),
]

def fetch_node(state: AgentState):
    project, file_row = fetch_project_and_files(int(state["project_id"]))
    return {"project": project, "file_row": file_row}

def read_node(state: AgentState):
    texts = {}
    download_dir = REPORT_OUTPUT_DIR / "downloads" / str(state["project_id"])
    for field, label in FILE_FIELDS:
        path = state["project"].get(field) if field == "project_details_file" else state["file_row"].get(field)
        if not path:
            continue
        local_path = download_storage_object(path, download_dir / Path(path).name)
        texts[Path(path).name] = extract_pdf_text(local_path)
    if not texts:
        raise ValueError("No project PDFs could be downloaded and read.")
    return {"document_texts": texts}

def extraction_node(state: AgentState):
    report = extract_report_data(state["project"], state["document_texts"])
    return {"report_data": report}

def validation_node(state: AgentState):
    report = validate_report(state["report_data"], state["document_texts"])
    return {"report_data": report}

def generate_node(state: AgentState):
    report = state["report_data"]
    REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"environmental_report_project_{state['project_id']}"
    json_path = REPORT_OUTPUT_DIR / f"{stem}.json"
    pdf_path = REPORT_OUTPUT_DIR / f"{stem}.pdf"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    create_pdf_report(report, pdf_path)
    return {"output_json": str(json_path.resolve()), "output_pdf": str(pdf_path.resolve())}

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("fetch_project", fetch_node)
    graph.add_node("read_documents", read_node)
    graph.add_node("extract_environmental_data", extraction_node)
    graph.add_node("validate_data", validation_node)
    graph.add_node("generate_report", generate_node)
    graph.add_edge(START, "fetch_project")
    graph.add_edge("fetch_project", "read_documents")
    graph.add_edge("read_documents", "extract_environmental_data")
    graph.add_edge("extract_environmental_data", "validate_data")
    graph.add_edge("validate_data", "generate_report")
    graph.add_edge("generate_report", END)
    return graph.compile()
