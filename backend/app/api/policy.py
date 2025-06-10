from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pathlib import Path

# Set this from main.py or config for best results,
# but you can hardcode for now if needed:
DOCUMENTS_DIR = Path(__file__).parent.parent / "assets" / "documents"

router = APIRouter(prefix="/api/policy")

@router.get("/privacypolicy", response_class=PlainTextResponse)
async def serve_privacy_policy():
    file_path = DOCUMENTS_DIR / "privacypolicy.txt"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Privacy Policy not found")
    return PlainTextResponse(file_path.read_text(encoding="utf-8"))

@router.get("/termsofconditions", response_class=PlainTextResponse)
async def serve_terms_of_service():
    file_path = DOCUMENTS_DIR / "termsofcondition.txt"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Terms of Service not found")
    return PlainTextResponse(file_path.read_text(encoding="utf-8"))
