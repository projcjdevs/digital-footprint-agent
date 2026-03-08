import json
import logging
from groq import Groq
from src.config import Config
from src.evaluator.prompts import EVALUATOR_SYSTEM_PROMPT, EVALUATOR_USER_PROMPT
from src.evaluator.supabase_client import get_rag_context

logger = logging.getLogger(__name__)

client = Groq(api_key=Config.GROQ_API_KEY)

def _flatten(payload: dict) -> dict:
    """Safely flatten master payload into prompt variables"""
    quali = payload.get("qualitative") or {}
    fb = (payload.get("quantitative") or {}).get("facebook") or {}
    ig = (payload.get("quantitative") or {}).get("instagram") or {}
    web = (payload.get("quantitative") or {}).get("website") or {}

    def safe(val):
        if val is None or val == "":
            return "N/A"
        return val

    return {
        "business_name": safe(payload.get("business_name")),
        "city": safe(payload.get("city")),
        "category": safe(fb.get("category")),
        "facebook_url": safe(payload.get("facebook_url")),
        "website_url": safe(payload.get("website_url")),
        "vibe_analysis": safe(quali.get("vibe_analysis")),
        "key_offerings": json.dumps(quali.get("key_offerings") or [], indent=2),
        "customer_pain_points": json.dumps(quali.get("customer_pain_points") or [], indent=2),
        "digital_presence_gaps": json.dumps(quali.get("digital_presence_gaps") or [], indent=2),
        "sentiment_summary": safe(quali.get("sentiment_summary")),
        "confidence_score": safe(quali.get("confidence_score")),
        "fb_followers": safe(fb.get("followers")),
        "fb_likes": safe(fb.get("likes")),
        "fb_email": safe(fb.get("email")),
        "fb_phone": safe(fb.get("phone")),
        "fb_rating": safe(fb.get("rating")),
        "fb_review_count": safe(fb.get("review_count")),
        "fb_address": safe(fb.get("address")),
        "fb_services": safe(fb.get("services")),
        "fb_ad_status": safe(fb.get("ad_status")),
        "fb_creation_date": safe(fb.get("creation_date")),
        "fb_category": safe(fb.get("category")),
        "ig_username": safe(ig.get("username")),
        "ig_followers": safe(ig.get("followers")),
        "ig_follows": safe(ig.get("follows")),
        "ig_profile_url": safe(ig.get("profile_url")),
        "web_overall_score": safe(web.get("overall_score")),
        "web_design_score": safe(web.get("design_score")),
        "web_functionality_score": safe(web.get("functionality_score")),
        "web_seo_score": safe(web.get("seo_score")),
        "web_mobile_readiness": safe(web.get("mobile_readiness")),
        "web_summary": safe(web.get("summary")),
        "web_top_issues": json.dumps(web.get("top_issues") or [], indent=2),
        "web_recommendation": safe(web.get("recommendation")),
    }


async def evaluate_lead(payload: dict) -> dict:
    """
    Full evaluation pipeline:
    1. Flatten master payload
    2. Get RAG context from Supabase
    3. Build prompt
    4. Call Groq LLaMA 70B
    5. Return structured evaluation
    """

    flat = _flatten(payload)

    # Step 1: RAG context (cold start safe)
    rag = await get_rag_context(
        business_name=flat["business_name"],
        category=flat["category"]
    )

    # Step 2: Build prompts with RAG injected
    system_prompt = EVALUATOR_SYSTEM_PROMPT.format(
        rag_success=rag["success_synthesis"],
        rag_blacklist=rag["blacklist_synthesis"]
    )
    user_prompt = EVALUATOR_USER_PROMPT.format(**flat)

    # Step 3: Call Groq
    logger.info(f"Evaluating: {flat['business_name']}")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,         # low temp = consistent, data-driven scoring
        max_tokens=2000,
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content
    evaluation = json.loads(raw)

    # Step 4: Attach metadata for downstream use
    evaluation["rag_context"] = {
        "success_match": rag.get("success_business"),
        "success_score": rag.get("success_score"),
        "success_similarity": rag.get("success_similarity"),
        "blacklist_match": rag.get("blacklist_name"),
        "blacklist_similarity": rag.get("blacklist_similarity")
    }
    evaluation["lead_snapshot"] = payload

    logger.info(
        f"Evaluation done: {flat['business_name']} "
        f"→ Score: {evaluation.get('agency_fit_score')} "
        f"→ {evaluation.get('status_recommendation')}"
    )

    return evaluation