from supabase import create_client
from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_BUCKET

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def fetch_project_and_files(project_id: int) -> tuple[dict, dict]:
    client = get_supabase_client()

    project_response = (
        client.table("project_details")
        .select("project_id, project_name, project_description, project_details_file, created_at")
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )
    projects = project_response.data or []
    if not projects:
        raise ValueError(f"No project_details row found for project_id={project_id}.")
    project = projects[0]

    files_response = (
        client.table("project_environmental_files")
        .select(
            "project_id, energy_record, water_record, emission_record, waste_record, "
            "environmental_clearances_assessments, environmental_compliance_records"
        )
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )
    rows = files_response.data or []
    if not rows:
        raise ValueError(
            f"No project_environmental_files row found for project_id={project_id}. "
            "Add the environmental file paths before running the agent."
        )
    return project, rows[0]

def download_storage_object(storage_path: str, destination):
    if not storage_path:
        raise ValueError("Empty Storage path.")
    client = get_supabase_client()
    data = client.storage.from_(SUPABASE_BUCKET).download(storage_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def upload_report_pdf(local_pdf_path, project_id: int) -> tuple[str, str]:
    """
    Upload a generated PDF to the configured private Supabase Storage bucket.
    Returns (storage_object_path, signed_download_url).
    """
    from datetime import datetime, timezone
    from pathlib import Path
    from config import SIGNED_URL_SECONDS, SUPABASE_URL

    path = Path(local_pdf_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Generated report PDF not found: {path}")

    client = get_supabase_client()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    object_path = (
        f"generated-reports/project-{project_id}/"
        f"environmental-report-{timestamp}.pdf"
    )

    with path.open("rb") as file_handle:
        client.storage.from_(SUPABASE_BUCKET).upload(
            path=object_path,
            file=file_handle.read(),
            file_options={
                "content-type": "application/pdf",
                "upsert": "true",
            },
        )

    signed = client.storage.from_(SUPABASE_BUCKET).create_signed_url(
        object_path,
        SIGNED_URL_SECONDS,
    )

    signed_url = (
        signed.get("signedURL")
        or signed.get("signedUrl")
        or signed.get("signed_url")
    )
    if not signed_url:
        raise RuntimeError(
            "PDF uploaded to Supabase, but no signed URL was returned."
        )

    # Some SDK versions return a relative Storage URL.
    if signed_url.startswith("/"):
        signed_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1{signed_url}"

    return object_path, signed_url
