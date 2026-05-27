import io
import os
import sys
from pathlib import Path

import fitz
import pytesseract
from PIL import Image
from fastapi import Body, FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from classifier import build_sections, classify_page
from mortgage_blueprint import detect_known_mortgage_package
from splitter import create_zip, split_pdf

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

GOOGLE_CREDENTIALS_FILE = "credentials.json"
GOOGLE_TOKEN_FILE = "token.json"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def safe_filename(value):
    invalid = '<>:"/\\|?*'

    for char in invalid:
        value = value.replace(char, "")

    return value.strip()


def configure_tesseract():
    if getattr(sys, "frozen", False):
        base_path = Path(sys.executable).resolve().parent
        bundled_root = base_path / "resources" / "tesseract"

        tesseract_path = bundled_root / "bin" / "tesseract"
        tessdata_path = bundled_root / "tessdata"

        if tesseract_path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)

        if tessdata_path.exists():
            os.environ["TESSDATA_PREFIX"] = str(tessdata_path)

    else:
        local_tesseract = "/opt/homebrew/bin/tesseract"
        local_tessdata = "/opt/homebrew/share/tessdata"

        if os.path.exists(local_tesseract):
            pytesseract.pytesseract.tesseract_cmd = local_tesseract

        if os.path.exists(local_tessdata):
            os.environ["TESSDATA_PREFIX"] = local_tessdata


def get_app_base_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def get_google_credentials_path():
    return get_app_base_path() / GOOGLE_CREDENTIALS_FILE


def get_google_token_path():
    return get_app_base_path() / GOOGLE_TOKEN_FILE


def get_google_drive_service():
    credentials = None

    credentials_path = get_google_credentials_path()
    token_path = get_google_token_path()

    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Google credentials file not found at: {credentials_path}"
        )

    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(
            str(token_path),
            GOOGLE_SCOPES,
        )

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path),
                GOOGLE_SCOPES,
            )

            credentials = flow.run_local_server(
                host="localhost",
                port=0,
                authorization_prompt_message=(
                    "Opening browser for Google Drive authorization..."
                ),
                success_message=(
                    "Google Drive authorization complete. You may close this window."
                ),
                open_browser=True,
            )

        with open(token_path, "w") as token_file:
            token_file.write(credentials.to_json())

    return build("drive", "v3", credentials=credentials)


app = FastAPI(title="LoanFlow API", version="0.1.0")

configure_tesseract()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS = {}
PROGRESS = {}


@app.get("/")
def root():
    return {"app": "LoanFlow", "status": "running"}


def extract_text_with_ocr_fallback(page) -> str:
    text = page.get_text("text") or ""

    if len(text.strip()) >= 50:
        return text

    try:
        pix = page.get_pixmap(dpi=350)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        img = img.convert("L")
        img = img.point(lambda x: 0 if x < 180 else 255)

        ocr_text = pytesseract.image_to_string(img, config="--psm 6")

        if len(ocr_text.strip()) > len(text.strip()):
            return ocr_text

    except Exception as error:
        print(f"OCR failed on page: {error}")

    return text


@app.post("/analyze")
def analyze_pdf(
    file: UploadFile = File(...),
    job_id: str = Form(...),
):
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}.pdf")

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    doc = fitz.open(file_path)
    total_pages = len(doc)

    PROGRESS[job_id] = {
        "current": 0,
        "total": total_pages,
        "status": "Preparing analysis...",
        "done": False,
    }

    pages = []

    for index, page in enumerate(doc, start=1):
        PROGRESS[job_id] = {
            "current": index,
            "total": total_pages,
            "status": f"Analyzing Page {index} out of {total_pages}",
            "done": False,
        }

        text = extract_text_with_ocr_fallback(page)
        result = classify_page(text)

        pages.append(
            {
                "page": index,
                "text": text[:4000],
                "category": result["category"],
                "confidence": result["confidence"],
                "score": result["score"],
            }
        )

    doc.close()

    blueprint_sections = detect_known_mortgage_package(pages)

    if blueprint_sections:
        sections = blueprint_sections
    else:
        sections = build_sections(pages)

    JOBS[job_id] = {
        "filePath": file_path,
        "pages": pages,
        "sections": sections,
        "files": [],
        "zipPath": None,
        "clientName": "",
        "zipFilename": "",
    }

    PROGRESS[job_id] = {
        "current": total_pages,
        "total": total_pages,
        "status": f"Complete. Analyzed {total_pages} pages.",
        "done": True,
    }

    return {
        "jobId": job_id,
        "pages": pages,
        "sections": sections,
    }


@app.get("/progress/{job_id}")
def get_progress(job_id: str):
    return PROGRESS.get(
        job_id,
        {
            "current": 0,
            "total": 0,
            "status": "Waiting",
            "done": False,
        },
    )


@app.post("/split/{job_id}")
def split(job_id: str, payload: dict = Body(...)):
    if job_id not in JOBS:
        return {"error": "Job not found"}

    sections = payload.get("sections", [])
    client = payload.get("client", {})

    first_name = client.get("firstName", "").strip()
    last_name = client.get("lastName", "").strip()

    if not first_name or not last_name:
        return {"error": "Client first and last name are required."}

    client_name = safe_filename(f"{last_name}, {first_name}")

    job = JOBS[job_id]
    output_dir = os.path.join(OUTPUT_DIR, job_id)

    files = split_pdf(
        job["filePath"],
        sections,
        output_dir,
        client_name,
    )

    zip_filename = f"{client_name}.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    create_zip(files, zip_path)

    job["sections"] = sections
    job["files"] = files
    job["zipPath"] = zip_path
    job["clientName"] = client_name
    job["zipFilename"] = zip_filename

    return {
        "files": [
            {
                "category": f["category"],
                "filename": f["filename"],
                "downloadUrl": f"/download/{job_id}/{f['filename']}",
                "startPage": f["startPage"],
                "endPage": f["endPage"],
            }
            for f in files
        ],
        "zipUrl": f"/download-zip/{job_id}",
    }


@app.post("/upload-to-google-drive/{job_id}")
def upload_to_google_drive(job_id: str):
    if job_id not in JOBS:
        return {"error": "Job not found"}

    job = JOBS[job_id]

    zip_filename = job.get("zipFilename")

    if not zip_filename:
        return {"error": "ZIP not found. Create Split PDFs first."}

    zip_path = os.path.join(OUTPUT_DIR, job_id, zip_filename)

    if not os.path.exists(zip_path):
        return {"error": "ZIP not found. Create Split PDFs first."}

    try:
        service = get_google_drive_service()

        file_metadata = {
            "name": zip_filename,
            "mimeType": "application/zip",
        }

        media = MediaFileUpload(
            zip_path,
            mimetype="application/zip",
            resumable=True,
        )

        uploaded_file = (
            service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id,name,webViewLink",
            )
            .execute()
        )

        return {
            "success": True,
            "message": "ZIP uploaded to Google Drive successfully.",
            "fileId": uploaded_file.get("id"),
            "fileName": uploaded_file.get("name"),
            "webViewLink": uploaded_file.get("webViewLink"),
        }

    except Exception as error:
        print(f"Google Drive upload failed: {error}")

        return {
            "error": "Failed to upload ZIP to Google Drive.",
            "details": str(error),
        }


@app.get("/preview-page/{job_id}/{page_number}")
def preview_page(job_id: str, page_number: int):
    if job_id not in JOBS:
        return {"error": "Job not found"}

    path = JOBS[job_id]["filePath"]

    if not os.path.exists(path):
        return {"error": "Original PDF not found"}

    doc = fitz.open(path)

    if page_number < 1 or page_number > len(doc):
        doc.close()
        return {"error": "Page out of range"}

    page = doc[page_number - 1]
    pix = page.get_pixmap(dpi=140)

    image_path = os.path.join(UPLOAD_DIR, f"{job_id}_page_{page_number}.png")
    pix.save(image_path)

    doc.close()

    return FileResponse(image_path, media_type="image/png")


@app.get("/download/{job_id}/{filename}")
def download_file(job_id: str, filename: str):
    path = os.path.join(OUTPUT_DIR, job_id, filename)

    if not os.path.exists(path):
        return {"error": "File not found"}

    return FileResponse(path, filename=filename, media_type="application/pdf")


@app.get("/download-zip/{job_id}")
def download_zip(job_id: str):
    if job_id not in JOBS:
        return {"error": "Job not found"}

    job = JOBS[job_id]

    zip_filename = job.get("zipFilename")

    if not zip_filename:
        return {"error": "ZIP not found"}

    path = os.path.join(OUTPUT_DIR, job_id, zip_filename)

    if not os.path.exists(path):
        return {"error": "ZIP not found"}

    return FileResponse(
        path,
        filename=zip_filename,
        media_type="application/zip",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
    )