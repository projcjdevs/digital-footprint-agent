from fastapi import FastAPI, HTTPException
from src.models import AuditReport, AuditRequest
from src.llm_client import get_audit_report
from src.evaluator.evaluator import evaluate_lead
from src.evaluator.supabase_client import store_evaluation
from src.config import Config

app = FastAPI(
    title="Digital Footprint Agent",
    description="AI-powered local business digital presence auditor",
    version="beta-0.2"
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


@app.post("/api/audit/evaluate")
async def evaluate_footprint(payload: dict):
    """
    Takes full Master Payload from N8N.
    Returns structured evaluation with score, pitch, synthesis.
    """
    try:
        evaluation = await evaluate_lead(payload)
        return evaluation
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@app.post("/api/decision/store")
async def store_decision(body: dict):
    """
    Called after human Telegram decision.
    Stores evaluation + embedding in Supabase for future RAG.
    Body: { lead_data: {...}, evaluation: {...}, decision: 'accepted'|'rejected' }
    """
    try:
        lead_data = body.get("lead_data", {})
        evaluation = body.get("evaluation", {})
        decision = body.get("decision", "")

        if decision not in ["accepted", "rejected"]:
            raise HTTPException(status_code=400, detail="decision must be 'accepted' or 'rejected'")

        await store_evaluation(lead_data, evaluation, decision)
        return {"status": "stored", "decision": decision, "business": lead_data.get("business_name")}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=Config.PORT, reload=True)