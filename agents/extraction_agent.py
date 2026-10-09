
import json

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from config import GROQ_API_KEY, GROQ_MODEL
from schemas.report_schema import EnvironmentalReportData


SYSTEM_PROMPT = """
You are an environmental data extraction agent preparing a DRAFT
environmental report aligned with BRSR Principle 6.

Use only the supplied project metadata and source-document text.
Never invent measurements, dates, permits, approvals, or compliance outcomes.

Rules:
1. Preserve values, units, reporting periods, and source filenames.
2. Never treat missing information as zero.
3. Distinguish reported, calculated, partial, unavailable,
   not_applicable, not_verified, and unknown information.
4. Flag contradictions, missing evidence, missing denominators,
   suspicious calculations, and unverified applicability.
5. If source data is synthetic, set synthetic_data=true.
6. Copy the numeric project_id from the supplied project metadata.
7. Return only data supported by the supplied evidence.
"""



def _make_llm():
    if not GROQ_API_KEY:
        raise RuntimeError("Set GROQ_API_KEY in your .env file.")

    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0,
        max_tokens=8192,
    )


def _prepare_bundle(project: dict, documents: dict[str, str]) -> str:
    bundle = {
        "project_metadata": project,
        "documents": documents,
        "required_fields": list(
            EnvironmentalReportData.model_fields.keys()
        ),
        "metric_structure": {
            "name": "string",
            "value": "string, number, or null",
            "unit": "string or null",
            "status": (
                "reported, calculated, partial, unavailable, "
                "not_applicable, not_verified, or unknown"
            ),
            "source_document": "filename or null",
            "notes": "string or null",
        },
    }

    return json.dumps(bundle, ensure_ascii=False)


def _normalise_report(data, project: dict, documents: dict):
    # Accept either a Pydantic model or a dictionary.
    if isinstance(data, EnvironmentalReportData):
        data = data.model_dump()
    elif not isinstance(data, dict):
        raise ValueError("The model did not return a JSON object.")

    # Trust the database for these identifying fields.
    data["project_id"] = int(project["project_id"])
    data["project_name"] = (
        project.get("project_name") or "Unnamed project"
    )

    if not data.get("reporting_period"):
        data["reporting_period"] = "Not stated"

    existing_sources = data.get("source_documents") or []
    data["source_documents"] = sorted(
        set(existing_sources) | set(documents.keys())
    )

    return EnvironmentalReportData.model_validate(data)


def extract_report_data(
    project: dict,
    documents: dict[str, str],
) -> EnvironmentalReportData:
    llm = _make_llm()
    bundle_text = _prepare_bundle(project, documents)

    messages = [
        
SystemMessage(
    content=(
        SYSTEM_PROMPT
        + "\nReturn the result as a single valid JSON object. "
        "JSON must follow the supplied report schema exactly. "
        "Do not include Markdown fences or explanatory text."
    )
),

        HumanMessage(
            content=(
                "Extract the environmental report from this input:\n"
                + bundle_text
            )
        ),
    ]

    # Attempt 1: use LangChain's structured-output support.
    try:
        structured_llm = llm.with_structured_output(
            EnvironmentalReportData,
            method="json_mode",
        )
        result = structured_llm.invoke(messages)
        return _normalise_report(result, project, documents)

    except Exception as structured_error:
        print(
            "Structured extraction failed; trying JSON repair. "
            f"Reason: {str(structured_error)[:300]}"
        )

    # Attempt 2: ask the model to correct/produce valid JSON.
    repair_messages = [
        SystemMessage(
            content=(
                SYSTEM_PROMPT
                + "\nReturn exactly one valid JSON object. "
                "Use double quotes for every key and string. "
                "Do not use Markdown fences, comments, or trailing commas. "
                "Include all required schema fields."
            )
        ),
        HumanMessage(
            content=(
                "Extract the report using the original source input below. "
                "Return valid JSON only.\n\n"
                + bundle_text
            )
        ),
    ]

    response = llm.invoke(repair_messages)
    raw = str(response.content).strip()

    # Handle accidental Markdown fences.
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Groq returned invalid JSON even after the repair attempt. "
            f"Parser error: {exc}. "
            f"Response excerpt: {raw[:1000]}"
        ) from exc

    return _normalise_report(data, project, documents)
