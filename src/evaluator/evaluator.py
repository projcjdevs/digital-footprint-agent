import json
import logging
from groq import Groq
from src.config import Config
from src.evaluator.prompts import EVALUATOR_SYSTEM_PROMPT, EVALUATOR_USER_PROMPT
from src.evaluator.supabase_client import get_rag_context
from datetime import datetime

logger = logging.getLogger(__name__)
client = Groq(api_key=Config.GROQ_API_KEY)


def _compute_fb_age(creation_date_str: str) -> str:
    try:
        created = datetime.strptime(creation_date_str, "%B %d, %Y")
        now = datetime.now()
        total_months = (now.year - created.year) * 12 + (now.month - created.month)
        years = total_months // 12
        months = total_months % 12
        parts = []
        if years > 0:
            parts.append(f"{years} year{'s' if years > 1 else ''}")
        if months > 0:
            parts.append(f"{months} month{'s' if months > 1 else ''}")
        return f"Page created on {creation_date_str} ({' and '.join(parts)} ago)"
    except Exception:
        return creation_date_str or "N/A"


def _flatten(payload: dict) -> dict:
    quali = payload.get("qualitative") or {}
    fb = (payload.get("quantitative") or {}).get("facebook") or {}
    ig = (payload.get("quantitative") or {}).get("instagram") or {}
    web = (payload.get("quantitative") or {}).get("website") or {}

    def safe(val):
        if val is None or val == "":
            return "N/A"
        return val

    fb_age = _compute_fb_age(fb.get("creation_date", ""))

    return {
        "business_name":          safe(payload.get("business_name")),
        "city":                   safe(payload.get("city")),
        "category":               safe(fb.get("category") or payload.get("category")),
        "facebook_url":           safe(payload.get("facebook_url")),
        "website_url":            safe(payload.get("website_url")),
        "vibe_analysis":          safe(quali.get("vibe_analysis")),
        "key_offerings":          json.dumps(quali.get("key_offerings") or [], indent=2),
        "customer_pain_points":   json.dumps(quali.get("customer_pain_points") or [], indent=2),
        "digital_presence_gaps":  json.dumps(quali.get("digital_presence_gaps") or [], indent=2),
        "sentiment_summary":      safe(quali.get("sentiment_summary")),
        "confidence_score":       safe(quali.get("confidence_score")),
        "fb_followers":           safe(fb.get("followers")),
        "fb_likes":               safe(fb.get("likes")),
        "fb_email":               safe(fb.get("email")),
        "fb_phone":               safe(fb.get("phone")),
        "fb_rating":              safe(fb.get("rating")),
        "fb_review_count":        safe(fb.get("review_count")),
        "fb_address":             safe(fb.get("address")),
        "fb_services":            safe(fb.get("services")),
        "fb_ad_status":           safe(fb.get("ad_status")),
        "fb_creation_date":       fb_age,
        "fb_category":            safe(fb.get("category")),
        "ig_username":            safe(ig.get("username")),
        "ig_followers":           safe(ig.get("followers")),
        "ig_follows":             safe(ig.get("follows")),
        "ig_profile_url":         safe(ig.get("profile_url")),
        "web_overall_score":      safe(web.get("overall_score")),
        "web_design_score":       safe(web.get("design_score")),
        "web_functionality_score": safe(web.get("functionality_score")),
        "web_seo_score":          safe(web.get("seo_score")),
        "web_mobile_readiness":   safe(web.get("mobile_readiness")),
        "web_summary":            safe(web.get("summary")),
        "web_top_issues":         json.dumps(web.get("top_issues") or [], indent=2),
        "web_recommendation":     safe(web.get("recommendation")),
    }


def _build_business_snapshot(payload: dict, flat: dict) -> dict:
    fb = (payload.get("quantitative") or {}).get("facebook") or {}
    ig = (payload.get("quantitative") or {}).get("instagram") or {}
    web = (payload.get("quantitative") or {}).get("website") or {}
    quali = payload.get("qualitative") or {}

    return {
        "identity": {
            "business_name": payload.get("business_name"),
            "city":          payload.get("city"),
            "category":      fb.get("category") or payload.get("category"),
            "facebook_url":  payload.get("facebook_url"),
            "website_url":   payload.get("website_url"),
            "fb_address":    fb.get("address"),
        },
        "facebook": {
            "followers":    fb.get("followers"),
            "likes":        fb.get("likes"),
            "email":        fb.get("email"),
            "phone":        fb.get("phone"),
            "rating":       fb.get("rating"),
            "review_count": fb.get("review_count"),
            "services":     fb.get("services"),
            "ad_status":    fb.get("ad_status"),
            "page_age":     flat["fb_creation_date"],
            "category":     fb.get("category"),
        },
        "instagram": {
            "username":    ig.get("username"),
            "followers":   ig.get("followers"),
            "follows":     ig.get("follows"),
            "profile_url": ig.get("profile_url"),
        },
        "website_audit": {
            "url":                  web.get("url"),
            "overall_score":        web.get("overall_score"),
            "design_score":         web.get("design_score"),
            "functionality_score":  web.get("functionality_score"),
            "seo_score":            web.get("seo_score"),
            "mobile_readiness":     web.get("mobile_readiness"),
            "summary":              web.get("summary"),
            "top_issues":           web.get("top_issues"),
            "recommendation":       web.get("recommendation"),
        },
        "qualitative": {
            "vibe_analysis":         quali.get("vibe_analysis"),
            "key_offerings":         quali.get("key_offerings"),
            "customer_pain_points":  quali.get("customer_pain_points"),
            "digital_presence_gaps": quali.get("digital_presence_gaps"),
            "sentiment_summary":     quali.get("sentiment_summary"),
            "confidence_score":      quali.get("confidence_score"),
        }
    }


async def evaluate_lead(payload: dict) -> dict:
    flat = _flatten(payload)

    rag = await get_rag_context(
        business_name=flat["business_name"],
        category=flat["category"]
    )

    system_prompt = EVALUATOR_SYSTEM_PROMPT.format(
        rag_success=rag["success_synthesis"],
        rag_blacklist=rag["blacklist_synthesis"]
    )
    user_prompt = EVALUATOR_USER_PROMPT.format(**flat)

    logger.info(f"Evaluating: {flat['business_name']}")

    response = client.chat.completions.create(
        model=Config.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
        max_tokens=2500,
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content
    evaluation = json.loads(raw)

    result = {
        "agency_fit_score":   evaluation.get("agency_fit_score"),
        "priority_level":     evaluation.get("priority_level"),
        "status":             evaluation.get("status"),
        "score_breakdown":    evaluation.get("score_breakdown"),
        "the_reasoning":      evaluation.get("the_reasoning"),
        "pitch_angle":        evaluation.get("pitch_angle"),
        "services_to_offer":  evaluation.get("services_to_offer"),
        "identity":           evaluation.get("identity"),
        "contacts":           evaluation.get("contacts"),
        "snapshot":           evaluation.get("snapshot"),
        "rag":                evaluation.get("rag"),
        "rag_reasoning": {
            "success_match":       rag.get("success_business"),
            "success_score":       rag.get("success_score"),
            "success_similarity":  rag.get("success_similarity"),
            "success_reasoning":   evaluation.get("rag", {}).get("success_similarity") if isinstance(evaluation.get("rag"), dict) else None,
            "blacklist_match":     rag.get("blacklist_name"),
            "blacklist_similarity": rag.get("blacklist_similarity"),
            "blacklist_reasoning": evaluation.get("rag", {}).get("blacklist_similarity") if isinstance(evaluation.get("rag"), dict) else None,
        },
        "business_snapshot": _build_business_snapshot(payload, flat),
    }

    logger.info(
        f"Done: {flat['business_name']} "
        f"→ Score: {result['agency_fit_score']} "
        f"→ {result['status']}"
    )

    return result