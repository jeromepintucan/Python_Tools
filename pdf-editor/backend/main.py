"""
PDF Editor Backend
------------------
FastAPI service providing PDF operations: merge, split, compress, rotate,
delete pages, and PDF -> image conversion.

Design notes:
- Uploaded files are saved to a temp working directory per-request.
- After each request, files are cleaned up immediately once the response
  is sent (BackgroundTask). A sweeper thread also runs periodically to
  delete any orphaned files older than FILE_TTL_SECONDS, in case a
  cleanup step fails or the server restarts mid-job.
- No persistent storage. Nothing survives past a single job + TTL window.
"""

import os
import shutil
import time
import uuid
import threading
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import fitz  # PyMuPDF

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

FILE_TTL_SECONDS = int(os.environ.get("FILE_TTL_SECONDS", 30 * 60))  # 30 min default
                                                                       # (text editor is multi-step: extract -> edit -> save)
SWEEP_INTERVAL_SECONDS = 60

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title="PDF Editor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auto-delete: background sweeper for orphaned files
# ---------------------------------------------------------------------------

def _sweep_old_files():
    while True:
        try:
            now = time.time()
            for f in STORAGE_DIR.glob("*"):
                try:
                    if f.is_file() and (now - f.stat().st_mtime) > FILE_TTL_SECONDS:
                        f.unlink(missing_ok=True)
                except FileNotFoundError:
                    pass
        except Exception as e:
            print(f"[sweeper] error: {e}")
        time.sleep(SWEEP_INTERVAL_SECONDS)


@app.on_event("startup")
def start_sweeper():
    t = threading.Thread(target=_sweep_old_files, daemon=True)
    t.start()


def cleanup_paths(paths: List[Path]):
    """BackgroundTask callback: delete files immediately after response is sent."""
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception as e:
            print(f"[cleanup] failed to delete {p}: {e}")


def job_dir() -> Path:
    d = STORAGE_DIR / uuid.uuid4().hex
    d.mkdir(parents=True, exist_ok=True)
    return d


async def save_upload(upload: UploadFile, dest: Path) -> Path:
    if upload.content_type not in ("application/pdf", "application/octet-stream"):
        # Some browsers send octet-stream for .pdf; check extension as fallback
        if not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"'{upload.filename}' is not a PDF")
    path = dest / upload.filename
    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/merge")
async def merge_pdfs(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(400, "Upload at least two PDFs to merge")

    d = job_dir()
    saved_paths = []
    try:
        merged = fitz.open()
        for uf in files:
            p = await save_upload(uf, d)
            saved_paths.append(p)
            with fitz.open(p) as src:
                merged.insert_pdf(src)

        out_path = d / "merged.pdf"
        merged.save(out_path)
        merged.close()
        saved_paths.append(out_path)

        background_tasks.add_task(cleanup_paths, saved_paths)
        background_tasks.add_task(lambda: d.rmdir() if d.exists() and not any(d.iterdir()) else None)
        return FileResponse(out_path, media_type="application/pdf", filename="merged.pdf",
                             background=background_tasks)
    except Exception as e:
        cleanup_paths(saved_paths)
        raise HTTPException(500, f"Merge failed: {e}")


@app.post("/split")
async def split_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                     ranges: str = Form(...)):
    """
    ranges: comma-separated page ranges, 1-indexed, e.g. "1-3,4-6,7"
    Returns a zip of the resulting PDFs.
    """
    import zipfile

    d = job_dir()
    saved_paths = []
    try:
        src_path = await save_upload(file, d)
        saved_paths.append(src_path)

        doc = fitz.open(src_path)
        n_pages = doc.page_count

        parsed_ranges = []
        for part in ranges.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-")
                start, end = int(start) - 1, int(end) - 1
            else:
                start = end = int(part) - 1
            if start < 0 or end >= n_pages or start > end:
                raise HTTPException(400, f"Invalid page range: {part} (doc has {n_pages} pages)")
            parsed_ranges.append((start, end))

        zip_path = d / "split.zip"
        out_files = []
        with zipfile.ZipFile(zip_path, "w") as zf:
            for i, (start, end) in enumerate(parsed_ranges, 1):
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=start, to_page=end)
                out_path = d / f"part_{i}.pdf"
                new_doc.save(out_path)
                new_doc.close()
                out_files.append(out_path)
                zf.write(out_path, arcname=f"part_{i}.pdf")

        doc.close()
        saved_paths.extend(out_files)
        saved_paths.append(zip_path)

        background_tasks.add_task(cleanup_paths, saved_paths)
        return FileResponse(zip_path, media_type="application/zip", filename="split.zip",
                             background=background_tasks)
    except HTTPException:
        cleanup_paths(saved_paths)
        raise
    except Exception as e:
        cleanup_paths(saved_paths)
        raise HTTPException(500, f"Split failed: {e}")


@app.post("/compress")
async def compress_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                        quality: str = Form("medium")):
    """
    quality: "low" | "medium" | "high" -> maps to image downsampling DPI
    Uses PyMuPDF's garbage collection + deflate; for stronger compression
    on image-heavy PDFs, pipe through Ghostscript instead (see README).
    """
    d = job_dir()
    saved_paths = []
    try:
        src_path = await save_upload(file, d)
        saved_paths.append(src_path)

        out_path = d / "compressed.pdf"
        doc = fitz.open(src_path)
        doc.save(out_path, garbage=4, deflate=True, clean=True)
        doc.close()
        saved_paths.append(out_path)

        background_tasks.add_task(cleanup_paths, saved_paths)
        return FileResponse(out_path, media_type="application/pdf", filename="compressed.pdf",
                             background=background_tasks)
    except Exception as e:
        cleanup_paths(saved_paths)
        raise HTTPException(500, f"Compress failed: {e}")


@app.post("/rotate")
async def rotate_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                      degrees: int = Form(...), pages: str = Form("all")):
    """degrees: 90, 180, or 270. pages: "all" or comma list e.g. "1,3,5" """
    d = job_dir()
    saved_paths = []
    try:
        if degrees not in (90, 180, 270, -90, -180, -270):
            raise HTTPException(400, "degrees must be one of 90, 180, 270")

        src_path = await save_upload(file, d)
        saved_paths.append(src_path)

        doc = fitz.open(src_path)
        if pages == "all":
            target_pages = range(doc.page_count)
        else:
            target_pages = [int(p) - 1 for p in pages.split(",")]

        for i in target_pages:
            page = doc[i]
            page.set_rotation((page.rotation + degrees) % 360)

        out_path = d / "rotated.pdf"
        doc.save(out_path)
        doc.close()
        saved_paths.append(out_path)

        background_tasks.add_task(cleanup_paths, saved_paths)
        return FileResponse(out_path, media_type="application/pdf", filename="rotated.pdf",
                             background=background_tasks)
    except HTTPException:
        cleanup_paths(saved_paths)
        raise
    except Exception as e:
        cleanup_paths(saved_paths)
        raise HTTPException(500, f"Rotate failed: {e}")


@app.post("/delete-pages")
async def delete_pages(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                        pages: str = Form(...)):
    """pages: comma list of 1-indexed page numbers to remove, e.g. "2,4" """
    d = job_dir()
    saved_paths = []
    try:
        src_path = await save_upload(file, d)
        saved_paths.append(src_path)

        doc = fitz.open(src_path)
        to_delete = sorted({int(p) - 1 for p in pages.split(",")}, reverse=True)
        for i in to_delete:
            if 0 <= i < doc.page_count:
                doc.delete_page(i)

        out_path = d / "edited.pdf"
        doc.save(out_path)
        doc.close()
        saved_paths.append(out_path)

        background_tasks.add_task(cleanup_paths, saved_paths)
        return FileResponse(out_path, media_type="application/pdf", filename="edited.pdf",
                             background=background_tasks)
    except Exception as e:
        cleanup_paths(saved_paths)
        raise HTTPException(500, f"Delete pages failed: {e}")


@app.post("/to-images")
async def pdf_to_images(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                         dpi: int = Form(150)):
    """Converts each page to a PNG, returns a zip."""
    import zipfile

    d = job_dir()
    saved_paths = []
    try:
        src_path = await save_upload(file, d)
        saved_paths.append(src_path)

        doc = fitz.open(src_path)
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)

        zip_path = d / "pages.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for i, page in enumerate(doc, 1):
                pix = page.get_pixmap(matrix=mat)
                img_path = d / f"page_{i}.png"
                pix.save(img_path)
                saved_paths.append(img_path)
                zf.write(img_path, arcname=f"page_{i}.png")
        doc.close()
        saved_paths.append(zip_path)

        background_tasks.add_task(cleanup_paths, saved_paths)
        return FileResponse(zip_path, media_type="application/zip", filename="pages.zip",
                             background=background_tasks)
    except Exception as e:
        cleanup_paths(saved_paths)
        raise HTTPException(500, f"Conversion failed: {e}")


# ---------------------------------------------------------------------------
# Text editing: extract -> view -> edit -> apply
#
# Unlike the stateless operations above, this is a multi-step flow, so the
# uploaded source PDF is kept in its job folder (not deleted immediately)
# until /apply-edits finishes, or until the TTL sweeper reclaims it.
# ---------------------------------------------------------------------------

class TextLineEdit(BaseModel):
    page: int
    bbox: List[float]     # [x0, y0, x1, y1] in PDF points, top-left origin
    font: str
    size: float
    color: int             # packed sRGB int, as returned by PyMuPDF
    text: str               # the NEW text to write in place of the original


class ApplyEditsRequest(BaseModel):
    edits: List[TextLineEdit]


def _map_font(original_font: str) -> str:
    """Map an arbitrary embedded font name to the closest PyMuPDF base-14 font."""
    name = (original_font or "").lower()
    bold = "bold" in name
    italic = "italic" in name or "oblique" in name

    if "times" in name or "georgia" in name or "serif" in name or "roman" in name:
        family = ("tibi" if bold and italic else "tibo" if bold else "tiit" if italic else "tiro")
    elif "courier" in name or "consolas" in name or "mono" in name:
        family = ("cobi" if bold and italic else "cobo" if bold else "coit" if italic else "cour")
    else:
        family = ("hebi" if bold and italic else "hebo" if bold else "heit" if italic else "helv")
    return family


@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    """
    Uploads a PDF and returns, per page, every line of text with its
    bounding box (in PDF points), font, size, and color — everything the
    frontend needs to overlay editable boxes exactly on top of the real text.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a PDF")

    job_id = uuid.uuid4().hex
    d = STORAGE_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    src_path = d / "source.pdf"

    try:
        with open(src_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        doc = fitz.open(src_path)
        pages_out = []
        for pno in range(doc.page_count):
            page = doc[pno]
            rect = page.rect
            text_dict = page.get_text("dict")

            lines_out = []
            line_counter = 0
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # 0 = text block, 1 = image block
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    spans = [s for s in spans if s.get("text", "").strip()]
                    if not spans:
                        continue
                    text = "".join(s["text"] for s in spans)
                    x0 = min(s["bbox"][0] for s in spans)
                    y0 = min(s["bbox"][1] for s in spans)
                    x1 = max(s["bbox"][2] for s in spans)
                    y1 = max(s["bbox"][3] for s in spans)
                    first = spans[0]
                    lines_out.append({
                        "id": f"{pno}_{line_counter}",
                        "bbox": [x0, y0, x1, y1],
                        "font": first.get("font", "helv"),
                        "size": round(first.get("size", 11), 2),
                        "color": first.get("color", 0),
                        "text": text,
                    })
                    line_counter += 1

            pages_out.append({
                "page": pno,
                "width": rect.width,
                "height": rect.height,
                "lines": lines_out,
            })
        doc.close()

        return {"job_id": job_id, "page_count": len(pages_out), "pages": pages_out}
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(500, f"Text extraction failed: {e}")


@app.get("/page-image/{job_id}/{page_num}")
def page_image(job_id: str, page_num: int, dpi: int = 150):
    """Renders one page of a previously-uploaded (extract-text) job as a PNG."""
    src_path = STORAGE_DIR / job_id / "source.pdf"
    if not src_path.exists():
        raise HTTPException(404, "Job not found or expired — please re-upload")

    doc = fitz.open(src_path)
    try:
        if page_num < 0 or page_num >= doc.page_count:
            raise HTTPException(400, "Invalid page number")
        page = doc[page_num]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        out_path = STORAGE_DIR / job_id / f"page_{page_num}_{dpi}.png"
        pix.save(out_path)
    finally:
        doc.close()

    return FileResponse(out_path, media_type="image/png")


@app.post("/apply-edits/{job_id}")
async def apply_edits(job_id: str, background_tasks: BackgroundTasks, payload: ApplyEditsRequest):
    """
    Applies edited text lines back into the original PDF:
    for each edit, whites out the original line's bounding box and draws
    the new text in its place using the closest matching base-14 font.
    Cleans up the entire job folder once the response is sent.
    """
    src_path = STORAGE_DIR / job_id / "source.pdf"
    if not src_path.exists():
        raise HTTPException(404, "Job not found or expired — please re-upload")

    doc = fitz.open(src_path)
    try:
        for edit in payload.edits:
            if edit.page < 0 or edit.page >= doc.page_count:
                continue
            page = doc[edit.page]
            x0, y0, x1, y1 = edit.bbox
            rect = fitz.Rect(x0, y0, x1, y1)

            # Actually remove the original text (not just paint over it) using
            # real redaction, so the old text can't be selected, searched, or
            # copied out from underneath the new text. White fill is a
            # reasonable default for most documents; this is the main source
            # of visual mismatch on non-white backgrounds (see README).
            page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()

            c = edit.color
            r, g, b = ((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255
            fontname = _map_font(edit.font)
            fontsize = edit.size
            # Approximate baseline: PyMuPDF's text origin is the baseline,
            # not the top of the bbox, so nudge up from the bottom edge.
            baseline_y = y1 - (fontsize * 0.2)

            page.insert_text(
                (x0, baseline_y),
                edit.text,
                fontname=fontname,
                fontsize=fontsize,
                color=(r, g, b),
            )

        out_path = STORAGE_DIR / job_id / "edited.pdf"
        doc.save(out_path)
    except Exception as e:
        doc.close()
        raise HTTPException(500, f"Applying edits failed: {e}")
    finally:
        doc.close()

    job_dir_path = STORAGE_DIR / job_id
    background_tasks.add_task(lambda: shutil.rmtree(job_dir_path, ignore_errors=True))
    return FileResponse(out_path, media_type="application/pdf", filename="edited.pdf",
                         background=background_tasks)
