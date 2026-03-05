from ddgs import DDGS
from src.config import Config

def fetch_snippets(business_name: str, city: str, facebook_url: str | None = None) -> str:

    queries = [
        f"{business_name} {city} Facebook page reviews",
        f"{business_name} {city} customer reviews complaints",
        f"{business_name} {city} Facebook page reviews",
    ]

    all_snippets: list[str] = []
    seen_urls: set[str] = set()

    with DDGS() as ddg:
        for query in queries:
            try:
                results = ddg.text(
                    query,
                    max_results=Config.DDG_MAX_RESULTS,
                    region="us-en",
                )
                for r in results:
                    url = r.get("href", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = r.get("title", "No title")
                    body = r.get("body", "No snippet")
                    all_snippets.append(f"[SOURCE: {title} - {body} ({url})]")
                
            except Exception as e:
                all_snippets.append(f"[SEARCH ERROR: '{query}']: {str(e)}")
        
    if not all_snippets:
        return "[NO SEARCH RESULTS FOUND - data is insufficient for analysis]"
    
    return "\n".join(all_snippets)