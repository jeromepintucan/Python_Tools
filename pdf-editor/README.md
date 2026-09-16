# PDF Editor

A free, self-hosted PDF toolkit (merge, split, compress, rotate, delete pages,
PDF-to-images) — inspired by iLovePDF. No accounts, no stored files.

## Auto-delete design

- Every uploaded file and every generated output lives only inside a
  per-request temp folder (`backend/storage/<job-id>/`).
- As soon as the response finishes sending, a `BackgroundTask` deletes those
  files immediately.
- A background sweeper thread also runs every 60 seconds and removes any
  file older than `FILE_TTL_SECONDS` (default 15 minutes), as a safety net
  in case a request is interrupted mid-job.
- Nothing is written to a database. There's no user history or file log.

## Project structure

```
pdf-editor/
  backend/          FastAPI service (PyMuPDF-based PDF operations)
    main.py
    requirements.txt
  frontend/         Next.js app (upload UI, calls the backend)
    app/
    components/
    lib/api.js
```

## Running locally

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`. Check `/health` to confirm
it's running.

### Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Visit `http://localhost:3000`.

## Endpoints

| Endpoint                     | Method | Purpose                                          |
|-------------------------------|--------|--------------------------------------------------|
| `/merge`                      | POST   | Merge 2+ PDFs into one                            |
| `/split`                      | POST   | Split a PDF by page ranges, returns a zip         |
| `/compress`                   | POST   | Reduce file size                                  |
| `/rotate`                     | POST   | Rotate all/specific pages                         |
| `/delete-pages`               | POST   | Remove specific pages                             |
| `/to-images`                  | POST   | Convert pages to PNGs, returns a zip              |
| `/extract-text`               | POST   | Upload a PDF, get back every text line + position |
| `/page-image/{job_id}/{page}` | GET    | Render one page as a PNG (for the editor view)    |
| `/apply-edits/{job_id}`       | POST   | Apply text edits, returns the edited PDF          |
| `/health`                     | GET    | Health check                                      |

## Text editor (`/editor` page)

This is the real "edit existing text" feature, at `/editor` in the frontend:

1. **Upload** → calls `/extract-text`, which returns every line of text on
   every page with its bounding box (in PDF points), font, size, and color.
2. **View & edit** → each page is rendered as an image (`/page-image`) with
   an editable text box overlaid exactly on top of each real text line.
   Editing a box just changes its text in the browser — nothing is sent to
   the server yet.
3. **Save** → only the lines you actually changed are sent to
   `/apply-edits`. For each one, the backend uses real redaction
   (`add_redact_annot` + `apply_redactions`) to fully remove the original
   text — not just paint over it — then draws the new text in its place
   using the closest matching standard font.

**Known limitations** (inherent to editing PDFs, not fixable with more code
alone):
- **Font matching**: only the 14 standard PDF fonts (Helvetica, Times,
  Courier, in regular/bold/italic) are used for replacement text. An
  embedded custom/branded font won't be reproduced exactly — expect a
  close-but-not-identical look.
- **Background color**: the redaction box is filled white. On a colored or
  textured background, this will look wrong until per-edit fill-color
  detection is added.
- **No reflow**: if your new text is longer than the original line, it will
  overflow its box rather than wrapping or shrinking automatically.
- Multi-column layouts, tables, and rotated text are extracted as individual
  lines and may not group the way you'd expect.

This flow was tested end-to-end (extract → edit → apply → re-render) against
a sample PDF to confirm the original text is fully replaced, not just
covered up.

## Notes / next steps

- **Compression** currently uses PyMuPDF's built-in garbage collection +
  deflate. For much stronger compression on image-heavy PDFs, pipe the file
  through Ghostscript instead:
  `gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook -o out.pdf in.pdf`
  (requires Ghostscript installed on the host).
- **OCR** isn't included yet. Add it with `pytesseract` + `pdf2image`, or
  PyMuPDF's built-in OCR support if you compile it with Tesseract.
- **Deployment**: frontend deploys free on Vercel; backend works on Render
  or Railway free tiers, or any small VPS. Set `NEXT_PUBLIC_API_BASE` and
  `ALLOWED_ORIGINS` (backend) accordingly for production.
- **File size limits**: consider adding a max upload size check in
  `save_upload()` if you expose this publicly.
