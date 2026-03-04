from fastapi import FastAPI, HTTPException
from src.models import AuditReport, AuditRequest
from src.llm_client import get_audit_report
from src.config import Config

app = FastAPI(
    title="Digital Footprint Agent",
    description="AI-powered local business digital presence auditor",
    version="beta-0.1"
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "port": Config.PORT}

@app.post("/api/audit/footprint", response_model=AuditReport)
async def audit_footprint(request: AuditRequest):
    try:
        report = await get_audit_report(request)
        return report
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"LLM output parsing failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=Config.PORT, reload=True)