from fastapi import FastAPI, HTTPException, Request
from fastapi import Body
from typing import Any
from src.models import AuditReport, AuditRequest
from src.llm_client import get_audit_report
from src.evaluator.evaluator import evaluate_lead
from src.evaluator.supabase_client import store_evaluation
from src.config import Config
import json
import logging

logger = logging.getLogger(__name__)

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
async def evaluate_footprint(request: Request):
    try:
        raw_body = await request.body()

        if not raw_body or len(raw_body) == 0:
            raise HTTPException(status_code=400, detail="Empty request body")

        body_str = raw_body.decode("utf-8").strip()

        if not body_str:
            raise HTTPException(status_code=400, detail="Empty request body after decode")

        payload = json.loads(body_str)

        if isinstance(payload, list):
            if len(payload) == 0:
                raise HTTPException(status_code=400, detail="Empty array payload")
            payload = payload[0]

        if not payload or not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail=f"Invalid payload: {type(payload)}")

        if not payload.get("business_name"):
            raise HTTPException(status_code=400, detail="Missing business_name in payload")

        logger.info(f"Received evaluate request for: {payload.get('business_name')}")
        evaluation = await evaluate_lead(payload)
        return evaluation

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")

@app.post("/api/decision/store")
async def store_decision(body: dict = Body(...)):
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