# PDF Editor — Setup Guide

Instructions for running this project on a fresh machine (Windows).

## Prerequisites

You need two things installed: **Python** and **Node.js**.

### 1. Check what you already have

Open a terminal (PowerShell) and run:

```
python --version
node --version
npm --version
```

- If `python` returns a version (3.9 or higher) → you're set for the backend.
- If `node` and `npm` return version numbers → you're set for the frontend.
- If either is missing, install it using the steps below.

### 2. Install Python (if missing)

Download from [python.org/downloads](https://www.python.org/downloads/).
During install, check the box **"Add python.exe to PATH"** before clicking Install.

### 3. Install Node.js (if missing)

**Option A — winget (needs admin rights):**
```
winget install OpenJS.NodeJS.LTS
```

**Option B — regular installer (no admin needed):**
1. Go to [nodejs.org](https://nodejs.org)
2. Download the **LTS** version installer (`.msi`)
3. Run it and click Next through the defaults — keep "Add to PATH" checked
4. Close and reopen your terminal
5. Verify with `node --version` and `npm --version`

If neither option works because you don't have permission to install software
on this machine, you'll need a device where you do have install rights, or
IT's help.

## Project setup

### 1. Get the code

If this repo is on GitHub, clone it:
```
git clone <your-repo-url>
cd pdf-editor
```

Or just unzip `pdf-editor.zip` and `cd` into the extracted `pdf-editor` folder.

### 2. Start the backend

Open a terminal in the `backend` folder:

```
cd backend
python -m venv venv
```

Activate the virtual environment:
- **Windows (PowerShell):** `venv\Scripts\Activate.ps1`
- **Windows (cmd):** `venv\Scripts\activate.bat`
- **Mac/Linux:** `source venv/bin/activate`

Then install dependencies and run the server:
```
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

You should see: `Uvicorn running on http://127.0.0.1:8000`

**Leave this terminal running.** This is your PDF-processing engine.

> If PowerShell blocks the activation script with an "execution policy" error,
> run this once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then
> try activating again.

### 3. Start the frontend

Open a **second, separate** terminal in the `frontend` folder:

```
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

You should see: `Local: http://localhost:3000`

**Leave this terminal running too.**

### 4. Open the app

Go to **http://localhost:3000** in your browser.

- The homepage has tools: merge, split, compress, rotate, delete pages, convert to images.
- Click **"Edit text in a PDF"** at the top to open the real text editor: upload a
  PDF, click any line of text to edit it, then **Save & Download**.

Both terminals (backend + frontend) need to stay open while you use the app.
Closing either one will break it.

## Troubleshooting

| Problem | Fix |
|---|---|
| `node` not recognized | Node.js isn't installed or PATH wasn't updated — reopen terminal after installing |
| `python` not recognized | Try `python3` or `py` instead |
| PowerShell blocks `venv\Scripts\Activate.ps1` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once |
| Frontend loads but tools fail / network error | Backend terminal probably isn't running — check it's still showing "Uvicorn running" |
| `winget` says access denied | You need admin rights for that option — use the manual installer from nodejs.org instead |
| Port 8000 or 3000 already in use | Close whatever else is using that port, or change the port in the run command (e.g. `--port 8001`) and update `.env.local` to match |

## Stopping the app

In each terminal, press `Ctrl + C` to stop the server.
