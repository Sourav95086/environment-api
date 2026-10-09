import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from config import REPORT_OUTPUT_DIR, validate_config
from graph import build_graph
from services.supabase_service import upload_report_pdf

app = FastAPI(
    title="Environmental ESG Report API",
    description=(
        "Generates an environmental ESG/BRSR draft for a project, "
        "uploads the PDF to Supabase Storage, and returns report JSON "
        "together with a signed PDF URL."
    ),
    version="1.0.0",
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "environmental-esg-report-api"}


@app.post("/api/reports/{project_id}")
def generate_report(project_id: int) -> dict[str, Any]:
    """
    Generate the report for a numeric public.project_details.project_id.
    Response includes the extracted report JSON and a temporary PDF URL.
    """
    if project_id <= 0:
        raise HTTPException(status_code=400, detail="project_id must be positive.")

    try:
        validate_config()
        workflow = build_graph()
        result = workflow.invoke({"project_id": project_id})

        json_path = Path(result["output_json"])
        pdf_path = Path(result["output_pdf"])

        if not json_path.exists():
            raise FileNotFoundError("Workflow completed without producing JSON.")
        if not pdf_path.exists():
            raise FileNotFoundError("Workflow completed without producing a PDF.")

        report_data = json.loads(json_path.read_text(encoding="utf-8"))
        storage_path, pdf_url = upload_report_pdf(pdf_path, project_id)

        return {
            "success": True,
            "project_id": project_id,
            "report": report_data,
            "pdf_url": pdf_url,
            "storage_path": storage_path,
            "pdf_url_expires_in_seconds": __import__("config").SIGNED_URL_SECONDS,
        }

    except ValueError as exc:
        message = str(exc)
        status = 404 if "No project_details row found" in message else 400
        raise HTTPException(status_code=status, detail=message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        # Keep secrets and full internal stack traces out of public responses.
        raise HTTPException(
            status_code=500,
            detail=f"Report generation failed: {type(exc).__name__}: {str(exc)[:500]}",
        ) from exc
