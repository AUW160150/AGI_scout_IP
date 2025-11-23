# step3_agi_analyzer.py
"""
STEP 3: Analyze scraped IPs using AGI API
This is the AGENTIC part that the hackathon requires!
"""
import json
import logging
from pathlib import Path
from typing import Dict, List
import requests

# Load config (which loads .env)
from config import AGI_API_KEY, AGI_API_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AGIAnalyzer:
    """
    Uses AGI API to analyze university IP
    This is the agentic intelligence layer!
    """
    
    def __init__(self):
        if not AGI_API_KEY:
            raise ValueError("AGI_API_KEY not found in environment!")
        
        self.api_key = AGI_API_KEY
        self.api_url = AGI_API_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"🤖 AGI API initialized: {self.api_key[:8]}****")
    
    def analyze_ip(self, scraped_data: Dict) -> Dict:
        """
        Use AGI API to analyze commercial potential
        """
        logger.info(f"🧠 Analyzing {scraped_data.get('ip_id')} with AGI...")
        
        # Build prompt for AGI agent
        prompt = f"""Analyze this university technology for commercialization:

Title: {scraped_data.get('title', 'Unknown')}
Summary: {scraped_data.get('summary', 'N/A')}
Applications: {scraped_data.get('applications', 'N/A')}
Stage: {scraped_data.get('stage_of_development', 'Unknown')}

Provide analysis in JSON format:
{{
    "commercial_score": 0-10,
    "market_readiness": "early/mid/late",
    "therapeutic_area": "specific area",
    "ideal_licensee": "startup/pharma/device",
    "deal_size_estimate": "$XM",
    "key_risks": ["risk1", "risk2"],
    "differentiation": "what makes this unique",
    "commercialization_timeline": "X years",
    "competitive_advantages": ["adv1", "adv2"]
}}

Respond with ONLY valid JSON, no markdown or explanations.
"""
        
        # Call AGI API (agent endpoint)
        try:
            response = requests.post(
                f"{self.api_url}/agents/complete",
                headers=self.headers,
                json={
                    "prompt": prompt,
                    "model": "agi-agent-v1",  # Adjust based on hackathon docs
                    "max_tokens": 1500,
                    "temperature": 0.3
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Parse AGI response
                content = result.get("content", "{}")
                
                # Clean markdown if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                analysis = json.loads(content)
                analysis['ip_id'] = scraped_data.get('ip_id')
                analysis['analyzed_by'] = 'agi_api'
                
                logger.info(f"   ✅ Score: {analysis.get('commercial_score', 'N/A')}/10")
                return analysis
            else:
                logger.error(f"   ❌ AGI API error: {response.status_code} - {response.text}")
                return {
                    "error": f"AGI API returned {response.status_code}",
                    "ip_id": scraped_data.get('ip_id'),
                    "commercial_score": 5,  # Default
                    "market_readiness": "unknown"
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"   ❌ JSON parse error: {e}")
            return {
                "error": "Failed to parse AGI response",
                "ip_id": scraped_data.get('ip_id'),
                "commercial_score": 5
            }
        except Exception as e:
            logger.error(f"   ❌ AGI API exception: {e}")
            return {
                "error": str(e),
                "ip_id": scraped_data.get('ip_id'),
                "commercial_score": 5
            }
    
    def analyze_batch(self, scraped_file: Path) -> Path:
        """Analyze all IPs in a scraped file"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Loading scraped data from {scraped_file}")
        logger.info(f"{'='*60}\n")
        
        if not scraped_file.exists():
            raise FileNotFoundError(f"Scraped file not found: {scraped_file}")
        
        with open(scraped_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        ips = data.get('ips', [])
        logger.info(f"Found {len(ips)} IPs to analyze\n")
        
        analyzed_ips = []
        for i, ip in enumerate(ips, 1):
            logger.info(f"[{i}/{len(ips)}] " + "-"*50)
            analysis = self.analyze_ip(ip)
            ip['agi_analysis'] = analysis
            analyzed_ips.append(ip)
        
        # Save analyzed data
        output_file = scraped_file.parent / scraped_file.name.replace('.json', '_analyzed.json')
        output = {
            'analyzed_date': data.get('scraped_date'),
            'total_count': len(analyzed_ips),
            'analysis_method': 'agi_api',
            'ips': analyzed_ips
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ ANALYSIS COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"📁 Output: {output_file}")
        logger.info(f"📊 Analyzed: {len(analyzed_ips)} IPs")
        
        # Show sample
        logger.info(f"\n📋 Sample results:")
        for ip in analyzed_ips[:3]:
            analysis = ip.get('agi_analysis', {})
            logger.info(f"  • {ip.get('title', 'Unknown')[:50]}...")
            logger.info(f"    Score: {analysis.get('commercial_score', 'N/A')}/10")
            logger.info(f"    Area: {analysis.get('therapeutic_area', 'Unknown')}")
        
        return output_file


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        logger.error("\n" + "="*60)
        logger.error("STEP 3: AGI ANALYZER")
        logger.error("="*60)
        logger.error("\nUsage: python step3_agi_analyzer.py <scraped_file>")
        logger.error("\nExample:")
        logger.error("  python step3_agi_analyzer.py data/scraped/hybrid_ips_stanford.json")
        logger.error("\nThis will create:")
        logger.error("  data/scraped/hybrid_ips_stanford_analyzed.json")
        sys.exit(1)
    
    scraped_file = Path(sys.argv[1])
    
    try:
        analyzer = AGIAnalyzer()
        analyzer.analyze_batch(scraped_file)
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)