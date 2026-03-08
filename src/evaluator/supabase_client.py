from supabase import create_client, Client
from src.config import Config
from src.evaluator.embedding import embed_text
import logging
import asyncio
from datetime import datetime, timezone
from functools import partial

logger = logging.getLogger(__name__)

def get_supabase() -> Client:
    return create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

async def get_rag_context(business_name: str, category: str = "") -> dict:
    default = {
        "success_synthesis": "No historical reference available.",
        "success_business": None,
        "success_score": None,
        "success_similarity": 0.0,
        "blacklist_synthesis": "No historical reference available.",
        "blacklist_name": None,
        "blacklist_reason": None,
        "blacklist_similarity": 0.0
    }

    try:
        query_text = f"{business_name} {category}".strip()
        
        # Run sync embedding in thread pool (its CPU heavy)
        loop = asyncio.get_event_loop()
        query_embedding = await loop.run_in_executor(None, embed_text, query_text)
        
        supabase = get_supabase()

        # Run sync supabase calls in thread pool
        success_res = await loop.run_in_executor(
            None,
            lambda: supabase.rpc(
                'match_successful_leads',
                {'query_embedding': query_embedding, 'match_count': 1}
            ).execute()
        )

        blacklist_res = await loop.run_in_executor(
            None,
            lambda: supabase.rpc(
                'match_blacklisted_leads',
                {'query_embedding': query_embedding, 'match_count': 1}
            ).execute()
        )

        if success_res.data:
            row = success_res.data[0]
            default["success_synthesis"] = row.get("the_synthesis", default["success_synthesis"])
            default["success_business"] = row.get("business_name")
            default["success_score"] = row.get("agency_fit_score")
            default["success_similarity"] = round(row.get("similarity", 0.0), 3)

        if blacklist_res.data:
            row = blacklist_res.data[0]
            default["blacklist_synthesis"] = row.get("the_synthesis", default["blacklist_synthesis"])
            default["blacklist_name"] = row.get("name")
            default["blacklist_reason"] = row.get("reason")
            default["blacklist_similarity"] = round(row.get("similarity", 0.0), 3)

        logger.info(f"RAG context fetched for: {business_name}")
        return default

    except Exception as e:
        logger.warning(f"RAG query failed (cold start safe): {e}")
        return default


async def store_evaluation(payload: dict, evaluation: dict, decision: str) -> bool:
    try:
        supabase = get_supabase()
        the_synthesis = evaluation.get("the_synthesis", "")

        # Run sync embedding in thread pool
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(None, embed_text, the_synthesis)

        fb = (payload.get("quantitative") or {}).get("facebook") or {}
        ig = (payload.get("quantitative") or {}).get("instagram") or {}
        web = (payload.get("quantitative") or {}).get("website") or {}
        quali = payload.get("qualitative") or {}

        record = {
            "business_name": payload.get("business_name"),
            "city": payload.get("city"),
            "category": fb.get("category"),
            "facebook_url": payload.get("facebook_url"),
            "website_url": payload.get("website_url"),
            "fb_followers": fb.get("followers"),
            "fb_email": fb.get("email"),
            "fb_phone": fb.get("phone"),
            "fb_rating": fb.get("rating"),
            "fb_review_count": fb.get("review_count"),
            "fb_ad_status": fb.get("ad_status"),
            "ig_username": ig.get("username"),
            "ig_followers": ig.get("followers"),
            "website_overall_score": web.get("overall_score"),
            "website_seo_score": web.get("seo_score"),
            "vibe_analysis": quali.get("vibe_analysis"),
            "sentiment_summary": quali.get("sentiment_summary"),
            "digital_presence_gaps": quali.get("digital_presence_gaps", []),
            "agency_fit_score": evaluation.get("agency_fit_score"),
            "priority_level": evaluation.get("priority_level"),
            "executive_summary": evaluation.get("executive_summary"),
            "strengths": evaluation.get("strengths", []),
            "weaknesses": evaluation.get("weaknesses", []),
            "opportunities": evaluation.get("opportunities", []),
            "pain_points": evaluation.get("pain_points", []),
            "pitch_angle": evaluation.get("pitch_angle"),
            "services_to_offer": evaluation.get("services_to_offer", []),
            "the_synthesis": the_synthesis,
            "status_recommendation": evaluation.get("status_recommendation"),
            "blacklist_similarity_reasoning": evaluation.get("blacklist_similarity_reasoning"),
            "success_similarity_reasoning": evaluation.get("success_similarity_reasoning"),
            "decision": decision,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "synthesis_embedding": embedding
        }

        await loop.run_in_executor(
            None,
            lambda: supabase.table('lead_evaluations').insert(record).execute()
        )

        if decision == "rejected":
            blacklist_record = {
                "name": payload.get("business_name"),
                "place_id": payload.get("place_id"),
                "reason": "rejected_by_human",
                "the_synthesis": the_synthesis,
                "synthesis_embedding": embedding
            }
            await loop.run_in_executor(
                None,
                lambda: supabase.table('blacklist').insert(blacklist_record).execute()
            )
            logger.info(f"Added to blacklist: {payload.get('business_name')}")

        logger.info(f"Evaluation stored: {payload.get('business_name')} → {decision}")
        return True

    except Exception as e:
        logger.error(f"Failed to store evaluation: {e}")
        raise