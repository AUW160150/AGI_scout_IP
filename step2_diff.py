# Detail Scraper Using OpenAI Search Models
# - Uses gpt-4o-search-preview for built-in agentic web searching
# - More reliable than Responses API + web_search tool
import os
import re
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# ---- tqdm import (tolerant) ----
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class SearchModelDetailScraper:
    """
    Uses OpenAI's dedicated search models (gpt-4o-search-preview)
    These models have built-in agentic web searching
    """
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o-search-preview"):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        k = api_key or OPENAI_API_KEY
        if not k or not k.startswith("sk-"):
            raise ValueError("OPENAI_API_KEY missing or malformed (must start with 'sk-')")
        
        logger.info(f"OpenAI key suffix in use: …{k[-6:]}")
        self.openai_client = OpenAI(api_key=k)
        self.model = model
        
        # Tracking
        self.traditional_count = 0
        self.gpt_count = 0
        self.total_cost = 0.0
        self.last_token_usage = {}
        self.last_citations = []

    def _fetch_with_requests(self, url: str) -> Optional[BeautifulSoup]:
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.debug(f"Requests failed: {e}")
            return None

    def _extract_traditional(self, soup: BeautifulSoup, url: str, ip_id: str) -> Dict[str, Any]:
        details = {
            "title": None,
            "post_date": None,
            "summary": None,
            "abstract": None,
            "benefit": None,
            "market_application": None,
            "technology_description": None,
            "publications": {"text": None, "urls": []},
            "image_urls": [],
            "licensing_contacts": [],
            "researchers": [],
            "organizations": [],
            "companies_interested": [],
            "additional_data": {},
            "extracted_urls": []
        }
        
        # Title
        for tag in ['h1', 'h2', 'title']:
            elem = soup.find(tag)
            if elem:
                details['title'] = elem.get_text(strip=True)
                break
        
        # Abstract/description
        for selector in ['abstract', 'description', 'summary', 'overview']:
            elem = soup.find(class_=re.compile(selector, re.I))
            if elem:
                details['abstract'] = elem.get_text(strip=True)
                break

        # If abstract exists but summary is empty, derive a short summary from abstract
        if details["abstract"] and not details["summary"]:
            # Take the first sentence-ish from the abstract
            first_sentence = re.split(r'(?<=[.!?])\s+', details["abstract"].strip())[0]
            if first_sentence:
                details["summary"] = first_sentence

        # Images
        for img in soup.find_all('img')[:5]:
            src = img.get('src', '')
            if src:
                if src.startswith('http'):
                    details['image_urls'].append(src)
                elif src.startswith('/'):
                    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    details['image_urls'].append(urljoin(base_url, src))
        
        # Links
        for link in soup.find_all('a', href=True)[:20]:
            href = link['href']
            if href.startswith('http'):
                details['extracted_urls'].append(href)
        
        return details

    def _calculate_completeness(self, details: Dict) -> float:
        fields = ['title', 'abstract', 'researchers', 'licensing_contacts']
        filled = sum(1 for f in fields if details.get(f))
        return filled / len(fields)

    def _search_model_extract(self, url: str, ip_id: str) -> Optional[Dict[str, Any]]:
        logger.info(f"   🔍 Using search model ({self.model}) for {ip_id}")
        
        prompt = f"""You are researching a technology transfer opportunity. Search the web thoroughly to extract complete information about this technology.

TARGET URL: {url}

INSTRUCTIONS:
1. Search for and read the technology page at the URL above
2. Search for related information from the university/institution's technology transfer office
3. Search for the researchers/inventors and their affiliations
4. Search for any related publications, patents, or press releases
5. Search for licensing contact information

Extract and return ONLY the following information in valid JSON format (no markdown, no code blocks):

{{
  "details": {{
    "title": "Technology title from the page",
    "post_date": "Publication or posting date if available",
    "summary": "Brief 2-3 sentence summary",
    "abstract": "Full technical description or abstract",
    "benefit": "Key benefits and advantages of this technology",
    "market_application": "Potential market applications and use cases",
    "technology_description": "Additional technical details",
    "publications": {{
      "text": "Description of related publications",
      "urls": ["URLs to publications, papers, or patents"]
    }},
    "image_urls": ["URLs to relevant images"],
    "licensing_contacts": [
      {{
        "name": "Contact person name",
        "phone": "Phone number",
        "email": "Email address"
      }}
    ],
    "researchers": ["Names of researchers/inventors"],
    "organizations": [
      {{
        "name": "Institution or organization name",
        "logo_url": "Logo URL if available"
      }}
    ],
    "companies_interested": [],
    "additional_data": {{}},
    "extracted_urls": ["All relevant URLs you found"]
  }},
  "citations": ["List ALL source URLs you used"]
}}

CRITICAL RULES:
- Use null for any field you cannot find
- Use empty arrays [] for lists with no data
- Include ALL source URLs in the citations field
- Return ONLY valid JSON, no other text
- Do NOT make up information - only use what you find"""

        try:
            # Use Chat Completions API with search model
            # NOTE: Search models don't accept temperature parameter
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000
            )
            
            # Extract the response
            content = response.choices[0].message.content
            
            # Parse JSON from response
            try:
                # Try direct parse
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                content = content.strip()
                if content.startswith('```'):
                    # Remove markdown code blocks
                    content = re.sub(r'^```(?:json)?\s*', '', content)
                    content = re.sub(r'\s*```$', '', content)
                
                # Try to find JSON object
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    data = json.loads(json_str)
                else:
                    logger.error(f"   ✗ Could not extract JSON from response")
                    return None
            
            # Extract citations
            self.last_citations = []
            try:
                for cit in data.get('citations', []):
                    if isinstance(cit, str) and cit.startswith('http'):
                        self.last_citations.append(cit)
                    elif isinstance(cit, dict):
                        u = cit.get('url') or cit.get('source')
                        if u and isinstance(u, str) and u.startswith('http'):
                            self.last_citations.append(u)
            except Exception:
                pass
            
            # Token usage and cost calculation
            usage = response.usage
            if usage:
                self.last_token_usage = {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                }
                
                # Pricing for gpt-4o-search-preview: $30 per 1000 queries (not per token)
                # This is query-based pricing, approximately $0.03 per query
                self.total_cost += 0.03
            
            logger.info(f"   ✅ Extracted with {len(self.last_citations)} citations using {self.model}")
            return data
            
        except Exception as e:
            logger.error(f"   ✗ Search model failed for {ip_id}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def scrape_single(self, url: str, ip_id: str, source_id: str) -> Dict[str, Any]:
        logger.info(f"Processing: {ip_id}")
        
        soup = self._fetch_with_requests(url)
        if soup:
            details = self._extract_traditional(soup, url, ip_id)
            completeness = self._calculate_completeness(details)
            logger.info(f"   📊 Traditional extraction: {completeness:.0%} complete")
            
            # FORCE search model whenever completeness is not 100%
            if completeness < 0.6:
                logger.info(f"   🔄 Insufficient data, using search model")
                gpt_data = self._search_model_extract(url, ip_id)
                
                if gpt_data and 'details' in gpt_data:
                    self.gpt_count += 1
                    details = gpt_data['details']
                    completeness = self._calculate_completeness(details)
                    scraping_method = 'search_model'
                    model_used = self.model
                else:
                    self.traditional_count += 1
                    scraping_method = 'traditional'
                    model_used = 'beautifulsoup'
                    logger.warning(f"   ⚠️ Search model failed, using traditional")
            else:
                self.traditional_count += 1
                scraping_method = 'traditional'
                model_used = 'beautifulsoup'
        else:
            logger.info(f"   ⚠️ Traditional failed, using search model")
            gpt_data = self._search_model_extract(url, ip_id)
            
            if gpt_data and 'details' in gpt_data:
                self.gpt_count += 1
                details = gpt_data['details']
                completeness = self._calculate_completeness(details)
                scraping_method = 'search_model'
                model_used = self.model
            else:
                details = {
                    "title": None,
                    "abstract": None,
                    "researchers": [],
                    "licensing_contacts": []
                }
                completeness = 0.0
                scraping_method = 'failed'
                model_used = 'none'
        
        return {
            "_id": {"$oid": ip_id},
            "source_id": source_id,
            "url": url,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "model": model_used,
            "scraping_method": scraping_method,
            "completeness_score": completeness,
            "web_citations": self.last_citations if self.last_citations else []
        }

    def scrape_all(self, urls_file: Path) -> List[Dict[str, Any]]:
        logger.info(f"Loading URLs from {urls_file}")
        
        with open(urls_file, 'r', encoding='utf-8') as f:
            url_data = json.load(f)
        
        urls = url_data.get('urls', [])
        source_id = url_data.get('source_id', 'unknown')
        
        logger.info(f"\n{'='*60}")
        logger.info(f"SCRAPING {len(urls)} IP PAGES")
        logger.info(f"Source: {source_id}")
        logger.info(f"Model: {self.model}")
        logger.info(f"{'='*60}\n")
        
        results = []
        for url_entry in tqdm(urls, desc="Scraping IPs"):
            url = url_entry['url']
            ip_id = url_entry.get('id', url.split('/')[-1])
            
            result = self.scrape_single(url, ip_id, source_id)
            results.append(result)
            self.last_citations = []
            time.sleep(0.5)
        
        return results

    def save_results(self, results: List[Dict], urls_file: Path, output_dir: Path = None):
        if output_dir is None:
            output_dir = Path('data/detailed')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        source_name = Path(urls_file).stem.replace('filtered_urls_', '').replace('raw_urls_', '')
        
        output = {
            "scraped_date": datetime.now().isoformat(),
            "total_count": len(results),
            "traditional_count": self.traditional_count,
            "search_model_count": self.gpt_count,
            "total_cost": round(self.total_cost, 4),
            "model": self.model,
            "ips": results
        }
        
        output_file = output_dir / f"detailed_{source_name}.json"
        backup_file = output_dir / f"detailed_{source_name}_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n{'='*60}")
        logger.info("SCRAPING COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total IPs: {len(results)}")
        logger.info(f"Traditional: {self.traditional_count}")
        logger.info(f"Search Model: {self.gpt_count}")
        logger.info(f"Total Cost: ${self.total_cost:.2f}")
        logger.info(f"\nSaved to: {output_file}")
        
        return output_file


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("\n" + "="*60)
        print("SEARCH MODEL DETAIL SCRAPER")
        print("="*60)
        print("\nUses OpenAI's dedicated search models for agentic web searching")
        print("- gpt-4o-search-preview (recommended)")
        print("- gpt-4o-mini-search-preview (cheaper)")
        print("\nUsage: python step2_search_model.py <urls_file> [model]")
        print("\nExamples:")
        print("  python step2_search_model.py data/raw/filtered_urls_tto.json")
        print("  python step2_search_model.py data/raw/filtered_urls_tto.json gpt-4o-mini-search-preview")
        print("\nPricing:")
        print("  gpt-4o-search-preview: $30 per 1000 queries (~$0.03/query)")
        print("  gpt-4o-mini-search-preview: $25 per 1000 queries (~$0.025/query)")
        print("\nRequires: OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    urls_file = Path(sys.argv[1])
    model = sys.argv[2] if len(sys.argv) > 2 else "gpt-4o-search-preview"
    
    # Validate model
    valid_models = ["gpt-4o-search-preview", "gpt-4o-mini-search-preview"]
    if model not in valid_models:
        print(f"⚠️  Warning: {model} may not be a search model")
        print(f"   Valid search models: {', '.join(valid_models)}")
        response = input("   Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    if not urls_file.exists():
        print(f"❌ File not found: {urls_file}")
        sys.exit(1)
    
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not set!")
        print("\nSet it in PowerShell:")
        print('  $env:OPENAI_API_KEY="sk-your-key-here"')
        print("\nSet it in Linux/Mac:")
        print('  export OPENAI_API_KEY="sk-your-key-here"')
        sys.exit(1)
    
    try:
        scraper = SearchModelDetailScraper(model=model)
        results = scraper.scrape_all(urls_file)
        output_file = scraper.save_results(results, urls_file)
        
        print(f"\n✅ Success! Results saved to:")
        print(f"   {output_file}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
