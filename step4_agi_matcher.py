# step4_agi_matcher.py
"""
STEP 4: Match analyzed IPs to companies using AGI API
Multi-agent matching system
"""
import json
import logging
from pathlib import Path
from typing import Dict, List
import requests

# Load config
from config import AGI_API_KEY, AGI_API_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AGIMatcher:
    """
    Uses AGI API multi-agent system for matching
    """
    
    def __init__(self):
        if not AGI_API_KEY:
            raise ValueError("AGI_API_KEY not found!")
        
        self.api_key = AGI_API_KEY
        self.api_url = AGI_API_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Mock company database (expand with real data)
        self.companies = [
            {"name": "GeneTech Therapeutics", "focus": "gene_therapy", "stage": "Series A", "location": "Boston"},
            {"name": "RareDisease Bio", "focus": "rare_disease", "stage": "Seed", "location": "SF"},
            {"name": "DiagnosticAI", "focus": "diagnostics", "stage": "Series B", "location": "London"},
            {"name": "Delivery Systems Inc", "focus": "drug_delivery", "stage": "Pre-seed", "location": "Singapore"},
            {"name": "NeuroBiotech", "focus": "neuroscience", "stage": "Series A", "location": "Boston"},
            {"name": "Cancer Therapeutics", "focus": "oncology", "stage": "Series B", "location": "SF"},
        ]
        
        logger.info(f"🎯 AGI Matcher initialized with {len(self.companies)} companies")
    
    def find_matches(self, analyzed_ip: Dict) -> List[Dict]:
        """Use AGI API to find company matches"""
        ip_id = analyzed_ip.get('ip_id', 'unknown')
        logger.info(f"🔍 Finding matches for {ip_id}...")
        
        analysis = analyzed_ip.get('agi_analysis', {})
        therapeutic_area = analysis.get('therapeutic_area', 'biotech')
        
        # Filter relevant companies (simple keyword matching)
        relevant = [c for c in self.companies 
                   if any(term in therapeutic_area.lower() 
                         for term in c['focus'].lower().split('_'))]
        
        if not relevant:
            relevant = self.companies[:3]  # Fallback to top 3
            logger.info(f"   No specific matches, using top {len(relevant)} companies")
        else:
            logger.info(f"   Found {len(relevant)} potentially relevant companies")
        
        matches = []
        for company in relevant:
            match = self._evaluate_match(analyzed_ip, company)
            if match:
                matches.append(match)
        
        return sorted(matches, key=lambda x: x.get('score', 0), reverse=True)[:5]
    
    def _evaluate_match(self, ip_data: Dict, company: Dict) -> Dict:
        """Use AGI API to evaluate match quality"""
        
        analysis = ip_data.get('agi_analysis', {})
        
        prompt = f"""Evaluate this IP-Company match for licensing/partnership:

UNIVERSITY IP:
- Title: {ip_data.get('title', 'Unknown')}
- Commercial Score: {analysis.get('commercial_score', 'N/A')}/10
- Therapeutic Area: {analysis.get('therapeutic_area', 'Unknown')}
- Stage: {analysis.get('market_readiness', 'Unknown')}
- Differentiation: {analysis.get('differentiation', 'N/A')}

COMPANY:
- Name: {company['name']}
- Focus: {company['focus']}
- Stage: {company['stage']}
- Location: {company['location']}

Evaluate the match and return JSON:
{{
    "is_good_match": true/false,
    "score": 0-10,
    "reasoning": "why this is/isn't a good match",
    "deal_structure": "license/co-development/acquisition",
    "estimated_deal_value": "$XM",
    "outreach_strategy": "how to approach them",
    "synergies": ["synergy1", "synergy2"],
    "potential_challenges": ["challenge1", "challenge2"]
}}

Respond with ONLY valid JSON.
"""
        
        try:
            response = requests.post(
                f"{self.api_url}/agents/complete",
                headers=self.headers,
                json={
                    "prompt": prompt,
                    "model": "agi-agent-v1",
                    "max_tokens": 1000,
                    "temperature": 0.3
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("content", "{}")
                
                # Clean markdown if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                match_data = json.loads(content)
                
                if match_data.get('is_good_match'):
                    match_data['company_name'] = company['name']
                    match_data['company_details'] = company
                    match_data['ip_title'] = ip_data.get('title')
                    match_data['ip_id'] = ip_data.get('ip_id')
                    match_data['university'] = ip_data.get('ip_id', '').split('_')[0] if ip_data.get('ip_id') else 'Unknown'
                    
                    logger.info(f"   ✅ Match: {company['name']} - Score: {match_data.get('score')}/10")
                    return match_data
                else:
                    logger.info(f"   ⚠️ Not a good match: {company['name']}")
                    return None
            else:
                logger.warning(f"   ⚠️ AGI API error for {company['name']}: {response.status_code}")
                return None
            
        except json.JSONDecodeError as e:
            logger.warning(f"   ⚠️ JSON parse error for {company['name']}: {e}")
            return None
        except Exception as e:
            logger.warning(f"   ⚠️ Match evaluation failed for {company['name']}: {e}")
            return None
    
    def match_all(self, analyzed_file: Path) -> Path:
        """Match all analyzed IPs"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Loading analyzed data from {analyzed_file}")
        logger.info(f"{'='*60}\n")
        
        if not analyzed_file.exists():
            raise FileNotFoundError(f"Analyzed file not found: {analyzed_file}")
        
        with open(analyzed_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        ips = data.get('ips', [])
        logger.info(f"Found {len(ips)} IPs to match\n")
        
        all_matches = []
        for i, ip in enumerate(ips, 1):
            logger.info(f"[{i}/{len(ips)}] " + "-"*50)
            matches = self.find_matches(ip)
            all_matches.extend(matches)
        
        # Save matches
        output_file = analyzed_file.parent / analyzed_file.name.replace('_analyzed.json', '_matches.json')
        output = {
            'match_date': data.get('analyzed_date'),
            'total_ips': len(ips),
            'total_matches': len(all_matches),
            'matches': all_matches
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ MATCHING COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"📁 Output: {output_file}")
        logger.info(f"📊 Total Matches: {len(all_matches)}")
        
        # Show top matches
        if all_matches:
            logger.info(f"\n🏆 TOP 3 MATCHES:")
            logger.info("-"*60)
            top_matches = sorted(all_matches, key=lambda x: x.get('score', 0), reverse=True)[:3]
            for i, match in enumerate(top_matches, 1):
                logger.info(f"\n{i}. {match.get('company_name')} ← {match.get('university', 'Unknown')}")
                logger.info(f"   IP: {match.get('ip_title', 'Unknown')[:50]}...")
                logger.info(f"   Score: {match.get('score')}/10")
                logger.info(f"   Deal: {match.get('deal_structure', 'Unknown')}")
                logger.info(f"   Value: {match.get('estimated_deal_value', 'Unknown')}")
        
        return output_file


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        logger.error("\n" + "="*60)
        logger.error("STEP 4: AGI MATCHER")
        logger.error("="*60)
        logger.error("\nUsage: python step4_agi_matcher.py <analyzed_file>")
        logger.error("\nExample:")
        logger.error("  python step4_agi_matcher.py data/scraped/hybrid_ips_stanford_analyzed.json")
        logger.error("\nThis will create:")
        logger.error("  data/scraped/hybrid_ips_stanford_matches.json")
        sys.exit(1)
    
    analyzed_file = Path(sys.argv[1])
    
    try:
        matcher = AGIMatcher()
        matcher.match_all(analyzed_file)
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)