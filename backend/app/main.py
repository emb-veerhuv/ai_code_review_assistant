from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from io import BytesIO
from zipfile import ZipFile, is_zipfile
import json
import yaml
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .review_graph import review_graph

APP_DIR = Path(__file__).resolve().parent
BASE = PurePosixPath(__file__).parent
DEFAULT_RULES_PATH= APP_DIR/"default_rules.yaml"

with DEFAULT_RULES_PATH.open("r",encoding="utf-8") as rules_file:
    DEFAULT_RULES=yaml.safe_load(rules_file)

EXTS = {".c", ".h", ".cpp", ".hpp", ".cc"}


def parse_rules(raw: str | None):
    if not raw or not raw.strip():
        return DEFAULT_RULES
    try:
        value = yaml.safe_load(raw)
        if not isinstance(value, dict):
            raise ValueError("Rules must be a YAML object")
        merged = json.loads(json.dumps(DEFAULT_RULES))
        for key, item in value.items():
            merged[key] = item
        return merged
    except Exception as exc:
        raise HTTPException(400, f"Invalid rules YAML: {exc}") from exc


def run(
    files: dict[str, str],
    rules: dict,
):
    result = review_graph.invoke(
        {
            "files": files,
            "rules": rules,
            "findings": [],
            "llm_findings": [],
            "summary": {},
            "patches": [],
            "llm_enabled": False,
            "llm_status": "",
        }
    )

    return {
        "summary": result.get(
            "summary",
            {},
        ),
        "findings": result.get(
            "findings",
            [],
        ),
        "documentation": result.get(
            "patches",
            [],
        ),
        "llm_enabled": result.get(
            "llm_enabled",
            False,
        ),
        "llm_status": result.get(
            "llm_status",
            "",
        ),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Embedded Review Assistant", version="1.0.0", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok", "langgraph": True}


@app.post("/api/review/code")
async def review_code(path: str = Form("snippet.cpp"), code: str = Form(...), rules_yaml: str | None = Form(None)):
    clean = PurePosixPath(path).name or "snippet.cpp"
    return run({clean: code}, parse_rules(rules_yaml))


@app.post("/api/review/repository")
async def review_repository(repository: UploadFile = File(...), rules_yaml: str | None = Form(None)):
    content = await repository.read()
    if not is_zipfile(BytesIO(content)):
        raise HTTPException(400, "Please upload a ZIP archive.")
    files = {}
    skipped = []
    blocked_parts = {".."}
    with ZipFile(BytesIO(content)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = PurePosixPath(info.filename)
            if any(part in blocked_parts or part.startswith(".") and part not in {"."} for part in name.parts):
                skipped.append(info.filename)
                continue
            if name.suffix.lower() in EXTS and info.file_size <= 2_000_000:
                files[name.as_posix()] = archive.read(info).decode("utf-8", errors="replace")
    result = run(files, parse_rules(rules_yaml))
    result["skipped_files"] = skipped
    return result


app.mount("/", StaticFiles(directory=str(APP_DIR.parent.parent / "frontend"), html=True), name="frontend")
