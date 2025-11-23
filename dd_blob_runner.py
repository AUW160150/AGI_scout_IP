"""
Life Sciences & Biotech Due Diligence Analysis System
Complete, ready-to-run analyzer for medical, pharmaceutical, and biotech IP
Includes domain-specific citations from credible medical/scientific sources
"""
from dotenv import load_dotenv
load_dotenv()
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from openai import OpenAI
from pathlib import Path
import argparse
import re

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration for Life Sciences DD Analysis"""
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    # Use GPT-5 family by default; override via --model
    # Available sizes include: "gpt-5", "gpt-5-mini", "gpt-5-nano"
    MODEL = "gpt-5"
    OUTPUT_DIR = "biotech_dd_reports"
    MAX_TOKENS = 25000  # increased for detailed medical analysis
    TEMPERATURE = 0.2  # lower for more consistent medical/scientific analysis
    ENABLE_DOMAIN_VALIDATION = True
# ============================================================================
# SCORING WEIGHTS
# ============================================================================

SCORE_WEIGHTS = {
    "clinical_evidence": 0.20,
    "regulatory_clarity": 0.15,
    "ip_strength": 0.15,
    "market_attractiveness": 0.15,
    "manufacturing_cmc_readiness": 0.10,
    "competitive_moat": 0.10,
    "team_inventor_quality": 0.10,
    "source_quality": 0.05
}

# ============================================================================
# LIFE SCIENCES CITATION SOURCES (reference cues only; not enforced)
# ============================================================================

LIFE_SCIENCES_SOURCES = {
    "medical_journals": [
        "New England Journal of Medicine (NEJM)",
        "The Lancet",
        "Journal of the American Medical Association (JAMA)",
        "Nature Medicine",
        "Nature Biotechnology",
        "Science Translational Medicine",
        "Cell",
        "Nature Reviews Drug Discovery",
        "British Medical Journal (BMJ)",
        "Annals of Internal Medicine",
        "Clinical Cancer Research",
        "Journal of Clinical Oncology",
        "Circulation",
        "Gastroenterology",
        "Hepatology"
    ],
    "pharma_databases": [
        "ClinicalTrials.gov",
        "FDA Orange Book",
        "FDA Purple Book",
        "EMA Clinical Data",
        "WHO International Clinical Trials Registry",
        "PubMed/MEDLINE",
        "Cochrane Database",
        "DrugBank",
        "PharmGKB"
    ],
    "regulatory_sources": [
        "FDA Guidance Documents",
        "EMA Guidelines",
        "ICH Guidelines",
        "PMDA (Japan)",
        "NMPA (China)",
        "Health Canada",
        "TGA (Australia)",
        "MHRA (UK)",
        "SwissMedic"
    ],
    "market_research": [
        "GlobalData Healthcare",
        "Evaluate Pharma",
        "IQVIA",
        "Frost & Sullivan Healthcare",
        "Grand View Research - Healthcare",
        "BioMedTracker",
        "Cortellis",
        "Citeline",
        "BioCentury"
    ],
    "agricultural_veterinary": [
        "Journal of Animal Science",
        "Veterinary Microbiology",
        "Aquaculture",
        "Fish & Shellfish Immunology",
        "Vaccine",
        "Preventive Veterinary Medicine",
        "Journal of Agricultural and Food Chemistry",
        "Crop Protection",
        "Plant Biotechnology Journal"
    ],
    "medical_device_sources": [
        "Journal of Medical Devices",
        "Medical Device and Diagnostic Industry (MD+DI)",
        "Biomedical Engineering Online",
        "IEEE Transactions on Biomedical Engineering",
        "Journal of Biomedical Materials Research",
        "FDA MAUDE Database",
        "FDA 510(k) Database"
    ]
}

# ============================================================================
# LIFE SCIENCES SPECIFIC PROMPTS
# ============================================================================

class LifeSciencesPrompts:
    """Specialized prompts for biotech/pharma/medical analysis"""

    BASE_SYSTEM_PROMPT = """You are a senior life sciences due diligence analyst.

NON-NEGOTIABLES
- No source, no claim: every factual/clinical/regulatory/market statement must have a credible citation.
- Acceptable sources: PubMed/DOI/PMID; ClinicalTrials.gov (NCT); FDA/EMA/ICH/WHO; CMS; national HTAs; SEC 10-K/8-K/20-F; FDA Orange/Purple; EMA EPAR; reputable healthcare market research (IQVIA/Evaluate/GlobalData/Citeline/etc); USDA-APHIS CVB (vet vaccines), FDA-CVM (vet drugs), NOAA Fisheries, FAO, ICES, OIE/WOAH, national fish health agencies; reputable aquaculture journals (Aquaculture, Journal of Fish Diseases, Reviews in Aquaculture, Veterinary Parasitology).

- Not acceptable: Wikipedia, blogs, generic news, social posts. If you cannot find a valid citation, set the field’s value to null (the native JSON null). 
- Do not return "NA", "N/A", or an empty string. 
- Set its "citation" to "", and add a precise entry to data_gaps like: "Not enough valid cited information: <json_path>".
- Use the web_search tool for any fact you don’t know with high confidence; every non-obvious fact must include at least one URL citation.

SOURCE HIERARCHY
- Prefer Tier 1: FDA/EMA/ICH/WHO; PubMed/PMID/DOI; NEJM/Lancet/JAMA/Nature/Science/Cell; EPAR; FDA labels/PMAs.
- If Tier 1 is not available, Tier 2 is acceptable: ClinicalTrials.gov/NCI SEER/CDC/EudraCT.
- If still unavailable, Tier 3 is acceptable: SEC/company reports; IQVIA/Evaluate/GlobalData/Citeline/…
- Never use hard-blocked sources (Wikipedia/blogs/Medium/social/forums).
- Always include an inline citation. If using Tier 2/3, still provide the value with that citation (do NOT omit or set NA). Keep the JSON shape unchanged.

SCORING VS CAS
- Keep pillar scores separate from any CAS/novelty/IP risk. CAS/novelty belongs only in the IP section notes; do not mix into `scores`.

STYLE
- Investor-ready, concise, no speculation. Prefer human clinical > preprint > animal > in vitro; prefer regulator/registry > company press.

Return ONLY valid JSON for the requested schema, in the exact order specified."""

    # ===================== GLOBAL (origin_country + global + US) =====================
    GLOBAL_LIFE_SCIENCES_PROMPT = """You are a senior life sciences due diligence analyst. Produce a CITED JSON diligence packet for GLOBAL commercialization.

STRICT RULES
- Every claim must carry a credible citation (see system prompt). No Wikipedia/blogs.
- Provide ≥5 close comparators spanning same and adjacent modalities.
- For any uncitable field: value null, "citation": "", and add a `data_gaps` item "Not enough valid cited information: <json_path>".
- Multi-geo scope is fixed: (1) origin_country (where the IP is published/assigned), (2) global, (3) US. Infer origin_country from assignee/inventor/patent priority data; if unclear, set origin_country.name = null and add a data gap.

STAGE-BREADTH MODE: GLOBAL_EARLY

TECHNOLOGY DATA (verbatim):
{technology_data}

REQUIRED OUTPUT JSON (exact order and shape):
{{
  "meta": {{"analysis_date":"YYYY-MM-DD","stage_breadth_mode":"GLOBAL_EARLY","analysis_type":"global_life_sciences"}},
  "executive_summary": {{
    "summary_bullets": ["",""],
    "key_takeaway": "",
    "citation": ""
  }},
  "unmet_need_and_market_overview": {{
    "market_size": {{
      "global": {{"current_usd":"","cagr_percent":"","five_year_usd_out":"","citation":""}},
      "us":     {{"current_usd":"","cagr_percent":"","five_year_usd_out":"","citation":""}}
    }},
    "epidemiology": {{
      "prevalence": {{"global":"","us":"","citation":""}},
      "incidence":  {{"global":"","us":"","citation":""}}
    }}
  }},
  "technological_differentiation": {{
    "mechanism_of_action": {{"description":"","citation":""}},
    "indication": "",
    "therapeutic_area": "",
    "modality": "",
    "route_of_administration": ""
  }},
  "current_treatment_paradigm": {{
    "if_indication_listed": {{
      "first_line":  [""],
      "second_line": [""],
      "third_line":  [""] ,
      "citation": ""
    }},
    "if_indication_not_listed": {{
      "recommended_indications_based_on_moa": [""] ,
      "gold_standard_treatments_for_recommended_indications": [""] ,
      "citation": ""
    }}
  }},
  "competitive_landscape": {{
    "clinical_stage_assets_global": [{{"product":"","company":"","modality":"","moa":"","stage":"","key_ref_or_nct":"","citation":""}}] ,
    "on_market_drugs":             [{{"product":"","company":"","modality":"","moa":"","year_of_approval":"","sales_or_share_ref":"","citation":""}}] ,
    "drugs_in_clinical_trials":    [{{"product":"","company":"","phase":"","pivotal_endpoint":"","pdufa_or_milestone":"","citation":""}}] ,
    "preclinical_stage_assets_global": [{{"program":"","company_or_institution":"","modality":"","moa":"","citation":""}}] ,
    "internal_ip_db_similar": [{{"reference_id":"","title_or_handle":"","note":"(leave empty if not accessible)","citation":""}}]
  }},
  "intellectual_property": {{
    "patent_portfolio_and_strength": {{
      "composition_of_matter": {{"patents":[""],"expiry":"","jurisdictions":[""],"citation":""}},
      "method_of_use":         {{"patents":[""],"expiry":"","citation":""}},
      "formulation_or_process":{{"patents":[""],"expiry":"","citation":""}},
      "overall_strength_commentary": ""
    }},
    "cas_novelty_and_ip_risk_notes": {{"commentary":"","citation":""}}
  }},
  "research_plan_and_milestones": [
    {{"milestone":"","timeline_quarter_year":"","success_criteria":"","citation":""}}
  ],
  "market_scope": {{
    "origin_country": {{
      "name": "",
      "market_size_usd": "",
      "cagr_percent": "",
      "five_year_usd_out": "",
      "citation": ""
    }},
    "global": {{
      "market_size_usd": "",
      "cagr_percent": "",
      "five_year_usd_out": "",
      "citation": ""
    }},
    "us": {{
      "market_size_usd": "",
      "cagr_percent": "",
      "five_year_usd_out": "",
      "citation": ""
    }}
  }},
  "partnership_recommendations_and_exit_strategy": {{
    "partnerships": [{{"company":"","rationale":"","precedent_deals_refs":[""],"citation":""}}] ,
    "exit_strategy": {{"options":["licensing","acquisition","ipo"],"potential_acquirers":[""],"valuation_range":{{"low":"","high":"","citation":""}}}}
  }},
  "commercialization_strategy": {{
    "go_to_market": "",
    "access_and_pricing": {{"benchmark_products":[""],"expected_price_range":"","citation":""}},
    "medical_affairs_and_kol": "",
    "launch_phasing": ""
  }},
  "scores": {{
    "pillars": {{
      "clinical_evidence":           {{"score":0,"rationale":"","citation":""}},
      "regulatory_clarity":          {{"score":0,"rationale":"","citation":""}},
      "ip_strength":                 {{"score":0,"rationale":"","citation":""}},
      "market_attractiveness":       {{"score":0,"rationale":"","citation":""}},
      "manufacturing_cmc_readiness": {{"score":0,"rationale":"","citation":""}},
      "competitive_moat":            {{"score":0,"rationale":"","citation":""}},
      "team_inventor_quality":       {{"score":0,"rationale":"","citation":""}},
      "source_quality":              {{"score":0,"rationale":"","citation":""}}
    }},
    "methodology": {{
      "weights": {{"clinical_evidence":0.20,"regulatory_clarity":0.15,"ip_strength":0.15,"market_attractiveness":0.15,"manufacturing_cmc_readiness":0.10,"competitive_moat":0.10,"team_inventor_quality":0.10,"source_quality":0.05}},
      "scoring_notes": "",
      "limitations": ""
    }}
  }},
  "citations_summary": {{"total_citations":0,"peer_reviewed_papers":0,"regulatory_documents":0,"clinical_trial_refs":0,"primary_sources":[""]}},
  "data_gaps": [],
  "bibliography": [{{"category":"peer_reviewed/regulatory/market/patent","citation":""}}]
}}
Return ONLY valid JSON.
"""

    # ===================== US (same packet order, US emphasis) =====================
    US_LIFE_SCIENCES_PROMPT = """You are a senior life sciences due diligence analyst. Produce a CITED JSON diligence packet for the US market. Use the same packet order and fields as the GLOBAL prompt.

STRICT RULES
- Cite every claim with FDA/CMS/ClinicalTrials.gov, peer-reviewed journals, SEC filings, and reputable US market sources.
- Provide ≥5 US-relevant close comparators with formulary/coverage or pricing/market refs where applicable.
- For any uncitable field: value null, empty "citation", and add "Not enough valid cited information: <json_path>" to data_gaps.
- Keep pillar scores separate from CAS novelty.

STAGE-BREADTH MODE: US_LATE

TECHNOLOGY DATA (verbatim):
{technology_data}

REQUIRED OUTPUT JSON (exact order and shape — identical keys as GLOBAL; US-specific facts should be emphasized where relevant):
{{
  "meta": {{"analysis_date":"YYYY-MM-DD","stage_breadth_mode":"US_LATE","analysis_type":"us_life_sciences"}},
  "executive_summary": {{
    "summary_bullets": ["",""],
    "key_takeaway": "",
    "citation": ""
  }},
  "unmet_need_and_market_overview": {{
    "market_size": {{
      "global": {{"current_usd":"","cagr_percent":"","five_year_usd_out":"","citation":""}},
      "us":     {{"current_usd":"","cagr_percent":"","five_year_usd_out":"","citation":""}}
    }},
    "epidemiology": {{
      "prevalence": {{"global":"","us":"","citation":""}},
      "incidence":  {{"global":"","us":"","citation":""}}
    }}
  }},
  "technological_differentiation": {{
    "mechanism_of_action": {{"description":"","citation":""}},
    "indication": "",
    "therapeutic_area": "",
    "modality": "",
    "route_of_administration": ""
  }},
  "current_treatment_paradigm": {{
    "if_indication_listed": {{
      "first_line":  [""],
      "second_line": [""],
      "third_line":  [""] ,
      "citation": ""
    }},
    "if_indication_not_listed": {{
      "recommended_indications_based_on_moa": [""] ,
      "gold_standard_treatments_for_recommended_indications": [""] ,
      "citation": ""
    }}
  }},
  "competitive_landscape": {{
    "clinical_stage_assets_global": [{{"product":"","company":"","modality":"","moa":"","stage":"","key_ref_or_nct":"","citation":""}}] ,
    "on_market_drugs":             [{{"product":"","company":"","modality":"","moa":"","year_of_approval":"","sales_or_share_ref":"","citation":""}}] ,
    "drugs_in_clinical_trials":    [{{"product":"","company":"","phase":"","pivotal_endpoint":"","pdufa_or_milestone":"","citation":""}}] ,
    "preclinical_stage_assets_global": [{{"program":"","company_or_institution":"","modality":"","moa":"","citation":""}}] ,
    "internal_ip_db_similar": [{{"reference_id":"","title_or_handle":"","note":"(leave empty if not accessible)","citation":""}}]
  }},
  "intellectual_property": {{
    "patent_portfolio_and_strength": {{
      "composition_of_matter": {{"patents":[""],"expiry":"","jurisdictions":[""],"citation":""}},
      "method_of_use":         {{"patents":[""],"expiry":"","citation":""}},
      "formulation_or_process":{{"patents":[""],"expiry":"","citation":""}},
      "overall_strength_commentary": ""
    }},
    "cas_novelty_and_ip_risk_notes": {{"commentary":"","citation":""}}
  }},
  "research_plan_and_milestones": [
    {{"milestone":"","timeline_quarter_year":"","success_criteria":"","citation":""}}
  ],
  "market_scope": {{
    "origin_country": {{
      "name": "",
      "market_size_usd": "",
      "cagr_percent": "",
      "five_year_usd_out": "",
      "citation": ""
    }},
    "global": {{
      "market_size_usd": "",
      "cagr_percent": "",
      "five_year_usd_out": "",
      "citation": ""
    }},
    "us": {{
      "market_size_usd": "",
      "cagr_percent": "",
      "five_year_usd_out": "",
      "citation": ""
    }}
  }},
  "partnership_recommendations_and_exit_strategy": {{
    "partnerships": [{{"company":"","rationale":"","precedent_deals_refs":[""],"citation":""}}] ,
    "exit_strategy": {{"options":["licensing","acquisition","ipo"],"potential_acquirers":[""],"valuation_range":{{"low":"","high":"","citation":""}}}}
  }},
  "commercialization_strategy": {{
    "go_to_market": "",
    "access_and_pricing": {{"benchmark_products":[""],"expected_price_range":"","citation":""}},
    "medical_affairs_and_kol": "",
    "launch_phasing": ""
  }},
  "scores": {{
    "pillars": {{
      "clinical_evidence":           {{"score":0,"rationale":"","citation":""}},
      "regulatory_clarity":          {{"score":0,"rationale":"","citation":""}},
      "ip_strength":                 {{"score":0,"rationale":"","citation":""}},
      "market_attractiveness":       {{"score":0,"rationale":"","citation":""}},
      "manufacturing_cmc_readiness": {{"score":0,"rationale":"","citation":""}},
      "competitive_moat":            {{"score":0,"rationale":"","citation":""}},
      "team_inventor_quality":       {{"score":0,"rationale":"","citation":""}},
      "source_quality":              {{"score":0,"rationale":"","citation":""}}
    }},
    "methodology": {{
      "weights": {{"clinical_evidence":0.20,"regulatory_clarity":0.15,"ip_strength":0.15,"market_attractiveness":0.15,"manufacturing_cmc_readiness":0.10,"competitive_moat":0.10,"team_inventor_quality":0.10,"source_quality":0.05}},
      "scoring_notes": "",
      "limitations": ""
    }}
  }},
  "citations_summary": {{"total_citations":0,"peer_reviewed_papers":0,"regulatory_documents":0,"clinical_trial_refs":0,"primary_sources":[""]}},
  "data_gaps": [],
  "bibliography": [{{"category":"peer_reviewed/regulatory/market/patent","citation":""}}]
}}
Return ONLY valid JSON.
"""

# ============================================================================
# CITATION VALIDATOR FOR LIFE SCIENCES
# ============================================================================

class LifeSciencesCitationValidator:
    """Validates citations for medical/scientific credibility with tiers."""

    # Hard blocklist stays
    FORBIDDEN = ['wikipedia', 'webmd', 'healthline', 'blog', 'medium.com',
                 'reddit', 'quora', 'facebook', 'twitter']

    # Regex groups for tiers (highest preference first)
    TIER_PATTERNS = [
        # Tier 1: regulators, PubMed/DOI/PMID, top journals
        (1, [
            r'\b(fda|ema|ich|who|pmda|tga|mhra|swissmedic)\b',
            r'\bepar\b',
            r'\bpubmed\b|\bpmid:\s*\d+\b',
            r'\bdoi:\s*10\.\d{4,9}/\S+',
            r'\bnejm\b|\blancet\b|\bjama\b|\bnature\b|\bscience\b|\bcell\b',
            r'drugsatfda|accessdata\.fda\.gov|cfpma|pma\.cfm'
        ]),
        # Tier 2: clinical registries and public health/statistics
        (2, [
            r'clinicaltrials\.gov|\bnct\d{8}\b',
            r'\bseer\.cancer\.gov\b',
            r'\bcdc\.gov\b',
            r'\beudract\b'
        ]),
        # Tier 3: company and market research (acceptable if needed)
        (3, [
            r'\bsec\.gov\b|\b10-k\b|\bannual report\b',
            r'iqvia|evaluate|globaldata|citeline|biomedtracker|cortellis|frost\s*&\s*sullivan|grand\s*view\s*research'
        ])
    ]

    @staticmethod
    def _matches_any(text: str, patterns) -> bool:
        return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)

    def assess(self, citation: str):
        """
        Returns (allowed: bool, tier: int|None, reason: str)
        """
        if not isinstance(citation, str) or not citation.strip():
            return (False, None, 'empty')

        c = citation.lower()
        if any(b in c for b in self.FORBIDDEN):
            return (False, None, 'forbidden')

        for tier, pats in self.TIER_PATTERNS:
            if self._matches_any(citation, pats):
                return (True, tier, 'matched')

        # If it doesn't match any pattern, allow it but treat as Tier 3 fallback
        return (True, 3, 'fallback')

    # Backwards-compatible shim (so the rest of your code keeps calling the same name if needed)
    def validate_medical_citation(self, citation: str) -> bool:
        """
        Treat Tier 1, 2, and 3 as valid (allowed). Only forbidden/empty are invalid.
        """
        allowed, tier, _ = self.assess(citation)
        return bool(allowed and tier in (1, 2, 3))



    @staticmethod
    def format_medical_citation(citation_data: Dict) -> str:
        """Format medical/scientific citations properly"""
        cit_type = citation_data.get('type', '')

        if cit_type == 'journal':
            authors = citation_data.get('authors', 'Unknown')
            year = citation_data.get('year', 'n.d.')
            title = citation_data.get('title', 'Untitled')
            journal = citation_data.get('journal', 'Unknown Journal')
            volume = citation_data.get('volume', '')
            pages = citation_data.get('pages', '')
            doi = citation_data.get('doi', '')
            pmid = citation_data.get('pmid', '')

            citation = f"{authors}. ({year}). {title}. {journal}"
            if volume:
                citation += f", {volume}"
            if pages:
                citation += f":{pages}"
            if doi:
                citation += f". DOI: {doi}"
            elif pmid:
                citation += f". PMID: {pmid}"
            return citation

        elif cit_type == 'clinical_trial':
            nct = citation_data.get('nct_number', '')
            title = citation_data.get('title', 'Untitled')
            sponsor = citation_data.get('sponsor', 'Unknown')
            status = citation_data.get('status', '')
            return f"ClinicalTrials.gov {nct}. {title}. Sponsor: {sponsor}. Status: {status}"

        elif cit_type == 'regulatory':
            agency = citation_data.get('agency', 'FDA')
            doc_type = citation_data.get('doc_type', 'Guidance')
            title = citation_data.get('title', 'Untitled')
            year = citation_data.get('year', 'n.d.')
            doc_number = citation_data.get('doc_number', '')
            return f"{agency}. ({year}). {doc_type}: {title}. {doc_number}"

        else:
            source = citation_data.get('source', 'Unknown')
            year = citation_data.get('year', 'n.d.')
            title = citation_data.get('title', '')
            return f"{source}. ({year}). {title}"

# ============================================================================
# MAIN ANALYZER CLASS
# ============================================================================

class LifeSciencesDueDiligenceAnalyzer:
    """Complete analyzer for life sciences and biotech IP"""

    def __init__(self, api_key: str = None):
        """Initialize with OpenAI client and validators"""
        self.api_key = api_key or Config.OPENAI_API_KEY
        self.client = OpenAI(api_key=self.api_key)
        self.citation_validator = LifeSciencesCitationValidator()
        self.ensure_output_dir()

    
    def _responses_generate_json(self, system_prompt: str, user_prompt: str, max_output_tokens: int):
        """
        Call Responses API with hosted web_search enabled.
        Force JSON via instruction (no response_format arg).
        """
        # Strong, explicit JSON-only nudge
        json_only_nudge = (
            "Return ONLY a valid JSON object matching the requested schema. "
            "No markdown, no prose, no preamble."
        )

        resp = self.client.responses.create(
            model=Config.MODEL,
            input=[
                {
                    "role": "system",
                    "content": [
                        {"type": "input_text", "text": system_prompt}
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": f"{user_prompt}\n\n{json_only_nudge}"}
                    ],
                },
            ],
            tools=[{"type": "web_search"}],
            # tool_choice is optional; default is auto. If you keep it:
            tool_choice="auto",
            max_output_tokens=max_output_tokens,
            #temperature=Config.TEMPERATURE,
        )



        # Prefer the convenience property if present
        raw_json = getattr(resp, "output_text", None)

        # Fallback: walk the structured output for the first text part
        if not raw_json:
            msg = next((x for x in getattr(resp, "output", []) if getattr(x, "type", "") == "message"), None)
            if msg and getattr(msg, "content", None):
                part = msg.content[0]
                raw_json = getattr(part, "text", None) or str(part)

        if not raw_json:
            raise RuntimeError("Responses API returned no text; cannot parse JSON.")

        # Strict parse, then fallback to largest-JSON-block extraction if needed
        try:
            data = json.loads(raw_json)
        except Exception:
            data = json.loads(self._extract_json_block(raw_json))

        # Optional: collect a few URL citations for debug
        sample_urls = []
        try:
            msg = next((x for x in getattr(resp, "output", []) if getattr(x, "type", "") == "message"), None)
            parts = getattr(msg, "content", []) if msg else []
            anns = []
            for p in parts:
                anns.extend(getattr(p, "annotations", []) or [])
            sample_urls = [a.url for a in anns if getattr(a, "type", "") == "url_citation" and getattr(a, "url", None)]
        except Exception:
            pass

        # Light usage capture if available
        usage = getattr(resp, "usage", None)
        self.last_token_usage = {
            "prompt_tokens": getattr(usage, "input_tokens", None),
            "completion_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": ((getattr(usage, "input_tokens", 0) or 0) + (getattr(usage, "output_tokens", 0) or 0)),
        }

        return data, {"url_citations_found": len(sample_urls), "sample_citations": sample_urls[:5]}

    def _generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Now uses Responses API + web_search. Same return contract.
        """
        data, dbg = self._responses_generate_json(system_prompt, user_prompt, Config.MAX_TOKENS)
        self.last_debug = dbg
        return data


    def ensure_output_dir(self):
        """Create output directory if it doesn't exist"""
        Path(Config.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    def _compute_composite_score(self, scores_pillars: Dict[str, Any]) -> Dict[str, Any]:
        """Compute weighted composite score 0-100 and band."""
        total = 0.0
        weight_sum = 0.0
        for pillar, w in SCORE_WEIGHTS.items():
            try:
                s = float(scores_pillars.get(pillar, {}).get("score", 0))
                s = max(0.0, min(5.0, s))
            except (TypeError, ValueError):
                s = 0.0
            total += (s / 5.0) * w
            weight_sum += w
        pct = round(((total / weight_sum) * 100.0), 1) if weight_sum else 0.0
        band = "Green" if pct >= 75 else ("Amber" if pct >= 55 else "Red")
        return {"score_0_100": pct, "band": band}

    def detect_life_sciences_category(self, technology_data: Dict) -> tuple:
        """Detect specific life sciences category from data"""
        data_str = str(technology_data).lower()

        categories = {
            'SMALL_MOLECULE_DRUG': ['small molecule', 'compound', 'nce', 'new chemical entity', 'oral drug'],
            'BIOLOGIC': ['antibody', 'protein', 'peptide', 'biologic', 'mab', 'biosimilar', 'fusion protein'],
            'GENE_THERAPY': ['gene therapy', 'gene editing', 'crispr', 'aav', 'lentivirus', 'car-t'],
            'VACCINE': ['vaccine', 'immunization', 'prophylactic', 'adjuvant', 'antigen'],
            'DIAGNOSTIC': ['diagnostic', 'biomarker', 'assay', 'pcr', 'elisa', 'sequencing', 'liquid biopsy'],
            'MEDICAL_DEVICE': ['device','implant','surgical','catheter','stent','510k','510(k)','pma'],
            'DIGITAL_HEALTH': ['digital therapeutic', 'dtx', 'samd', 'ai diagnostic', 'telehealth', 'mhealth'],
            'AGRICULTURAL_BIOTECH': ['crop', 'seed', 'pesticide', 'herbicide', 'gmo', 'plant', 'soil', 'yield', 'trait'],
            'VETERINARY': ['veterinary', 'animal health', 'livestock', 'aquaculture', 'fish', 'cattle', 'poultry', 'companion animal', 'salmon', 'louse', 'parasite'],
        }

        scores = {}
        for category, keywords in categories.items():
            score = sum(2 if keyword in data_str and len(keyword) > 5 else 1 for keyword in keywords if keyword in data_str)
            if score > 0:
                scores[category] = score
        
        if scores:
            # Get top category but also check for multi-category technologies
            detected = max(scores, key=scores.get)
            
            # Special handling for combination categories
            if 'DIAGNOSTIC' in scores and 'DIGITAL_HEALTH' in scores:
                detected = 'DIGITAL_DIAGNOSTIC'
            elif 'MEDICAL_DEVICE' in scores and 'DIGITAL_HEALTH' in scores:
                detected = 'CONNECTED_MEDICAL_DEVICE'
            
            return detected, scores
        
        return 'GENERAL_LIFE_SCIENCES', {}

    def _guess_origin_country(self, technology_data: Dict[str, Any]) -> str:
        """Best-effort origin-country hint from fields or text (non-authoritative)"""
        # direct fields first
        for key in ("assignee_country","inventor_country","priority_country",
                    "jurisdiction","applicant_country","origin_country"):
            v = technology_data.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # heuristic scan
        txt = json.dumps(technology_data, ensure_ascii=False).lower()
        candidates = [
            "united states","usa","us","china","cn","europe","eu","japan","jp",
            "korea","kr","india","in","united kingdom","uk","germany","de",
            "france","fr","italy","it","canada","ca","australia","au","brazil","br"
        ]
        for c in candidates:
            if c in txt:
                return c
        return ""

    def enhance_prompt_with_sources(self, category: str) -> str:
        """Add relevant citation source hints based on category"""
        source_recommendations = []

        if 'DRUG' in category or 'BIOLOGIC' in category:
            source_recommendations.extend([
                "Search PubMed for mechanism of action studies",
                "Check ClinicalTrials.gov (NCT) for ongoing trials / endpoints",
                "Review FDA Orange/Purple Book for patent & exclusivity",
                "Use IQVIA/Evaluate/GlobalData for market size and share"
            ])
        elif 'VACCINE' in category:
            source_recommendations.extend([
                "NEJM/Lancet vaccine trials",
                "WHO vaccine pipeline / SAGE/ACIP",
                "EMA EPAR, FDA BLA precedents"
            ])
        elif 'DIAGNOSTIC' in category:
            source_recommendations.extend([
                "Diagnostic accuracy studies (sensitivity/specificity)",
                "FDA 510(k)/PMA predicates",
                "CMS coverage decisions (NCD/LCD)"
            ])
        elif 'DEVICE' in category:
            source_recommendations.extend([
                "FDA MAUDE adverse events",
                "510(k)/PMA database for predicates",
                "Peer-reviewed device outcomes"
            ])
        elif 'AGRICULTURAL' in category or 'VETERINARY' in category:
            source_recommendations.extend([
                "USDA/EPA registrations",
                "Veterinary/agri peer-reviewed journals",
                "FAO market/epidemiology reports"
            ])

        return "\n".join(source_recommendations)
    
    def _merge_corrections(self, original: Dict, corrections: Dict) -> Dict:
        """Merge targeted corrections into original report"""
        import copy
        merged = copy.deepcopy(original)
        
        def update_nested(target, source, path=""):
            for key, value in source.items():
                if key in target:
                    if isinstance(value, dict) and isinstance(target[key], dict):
                        update_nested(target[key], value, f"{path}.{key}" if path else key)
                    elif value is not None and value != "":
                        # Only update if correction has valid data
                        target[key] = value
                        print(f"      Updated: {path}.{key}")
                else:
                    target[key] = value
        
        update_nested(merged, corrections)
        return merged

    def load_technology_data(self, file_path: str, record_index: Optional[int] = None) -> Dict[str, Any]:
        """Load technology data from JSON file; optionally select one record in a list."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                data = json.load(f)

        if isinstance(data, list) and record_index is not None:
            if record_index < 0 or record_index >= len(data):
                raise IndexError(f"record_index {record_index} out of range (0..{len(data)-1})")
            item = data[record_index]
            if isinstance(item, dict) and "details" in item and isinstance(item["details"], dict):
                return item["details"]
            return item
        return data

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """Best-effort: pull the largest JSON object from a text block."""
        if not text:
            return ""
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end+1].strip()
        return text.strip()


    def analyze_life_sciences_ip(self, technology_data: Dict[str, Any], analysis_type: str = "global") -> Dict[str, Any]:
        # Detect category early (you already do this later; do it once here)
        category, _ = self.detect_life_sciences_category(technology_data)
        print(f"   Detected Category: {category}")

        # Prompt enhancers (optional module)
        domain_requirements = ""
        if Config.ENABLE_DOMAIN_VALIDATION:
            try:
                from domain_validation import DomainSpecificPrompter
                prompter = DomainSpecificPrompter()
                domain_requirements = prompter.get_enhancement(category)
            except ImportError:
                print("   (domain_validation not installed; skipping domain prompt enhancements)")
            except Exception as e:
                print(f"   (domain_validation prompt enhancer warning: {e})")

        source_guidance = self.enhance_prompt_with_sources(category)
        origin_hint = self._guess_origin_country(technology_data)
        origin_hint_line = f"ORIGIN COUNTRY HINT (best-effort): {origin_hint or 'NA'}"

        base_prompt = (
            LifeSciencesPrompts.GLOBAL_LIFE_SCIENCES_PROMPT
            if analysis_type == "global"
            else LifeSciencesPrompts.US_LIFE_SCIENCES_PROMPT
        ).format(technology_data=json.dumps(technology_data, indent=2))

        enhanced_prompt = f"""
    {origin_hint_line}
    DETECTED TECHNOLOGY CATEGORY: {category}

    {domain_requirements}

    RECOMMENDED CITATION SOURCES FOR THIS CATEGORY:
    {source_guidance}

    SPECIFIC CREDIBLE SOURCES TO PRIORITIZE:
    - Medical Journals: {', '.join(LIFE_SCIENCES_SOURCES['medical_journals'][:5])}
    - Databases: {', '.join(LIFE_SCIENCES_SOURCES['pharma_databases'][:5])}
    - Regulatory: {', '.join(LIFE_SCIENCES_SOURCES['regulatory_sources'][:5])}
    - Market Research: {', '.join(LIFE_SCIENCES_SOURCES['market_research'][:5])}

    {base_prompt}
    """

        try:
            print("   Generating analysis report...")
            result = self._generate_json(LifeSciencesPrompts.BASE_SYSTEM_PROMPT, enhanced_prompt)
            dbg = getattr(self, "last_debug", {}) or {}
            print("🔎 web citations found:", dbg.get("url_citations_found", 0))
            print("🔗 sample URLs:", dbg.get("sample_citations", []))

            if hasattr(self, "last_token_usage"):
                result.setdefault("meta", {})["token_usage"] = self.last_token_usage

            result = self.validate_report_citations(result)

            # Domain-specific validation and review (optional)
            if Config.ENABLE_DOMAIN_VALIDATION:
                try:
                    from domain_validation import DomainValidator, AnalysisReviewer
                    validator = DomainValidator()
                    issues = validator.validate_market_data(result, category)  # result & category now exist

                    if issues:
                        print(f"⚠️ Found {len(issues)} validation issues")
                        high_priority = [i for i in issues if i.get('severity') == 'HIGH']
                        if high_priority:
                            print("   Attempting to correct critical issues...")
    #                         correction_prompt = f"""
    # Based on the initial analysis, the following CRITICAL issues need correction:

    # {json.dumps(high_priority, indent=2)}

    # For each issue, perform the specific recommended search and provide ONLY the corrected data.
    # DO NOT use broad sector data as a proxy. If specific data cannot be found, set the field to null 
    # and add an appropriate data_gap entry.

    # Focus on:
    # 1. Finding {category}-specific market data (not total sector)
    # 2. Adding missing required fields with proper citations
    # 3. Using targeted search queries as recommended

    # Return corrections in JSON format matching the original schema.
    # """
    #                         try:
    #                             corrections = self._generate_json(LifeSciencesPrompts.BASE_SYSTEM_PROMPT, correction_prompt)
    #                             result = self._merge_corrections(result, corrections)
    #                             print("   ✓ Applied corrections")
    #                         except Exception as e:
    #                             print(f"   ⚠️ Could not apply all corrections: {e}")

                    reviewer = AnalysisReviewer()
                    review = reviewer.review_report(result, category)
                    result['quality_assessment'] = {
                        'score': review.get('quality_score', 0),
                        'category': category,
                        'issues_found': len(review.get('issues', [])),
                        'passed_validation': review.get('quality_score', 0) >= 70
                    }
                    print(f"   Quality Score: {result['quality_assessment']['score']}/100")
                    if result['quality_assessment']['score'] < 70:
                        for rec in review.get('recommendations', [])[:3]:
                            print(f"     - {rec}")
                except ImportError:
                    # Optional module missing; skip without failing the run
                    pass
                except Exception as e:
                    print(f"   Validation/review warning: {e}")

            # Composite score
            try:
                pillars = result.get("scores", {}).get("pillars")
                if isinstance(pillars, dict):
                    result["scores"]["composite"] = self._compute_composite_score(pillars)
            except Exception:
                pass

            return result

        except Exception as e:
            print(f"Error during analysis: {e}")
            raise


    def validate_report_citations(self, report: Dict) -> Dict:
        """Validate all citations; if invalid: blank citation, set simple value to 'None', and log data_gap.
        Also count Tier 1/2/3 sources in citations_summary.tier_counts."""
        citation_count = 0
        valid_citations = 0
        invalid_citations = []

        # 1) counters for Tier 1/2/3 (classification comes from citation_validator.assess)
        tier_counts = {1: 0, 2: 0, 3: 0}  
        valid_by_tier = {1: 0, 2: 0, 3: 0}
        

        def add_gap(path: str, flagged_source: str = ""):
            gaps = report.setdefault("data_gaps", [])
            if flagged_source:
                msg = f"Not enough valid cited information: {path} → flagged source: {flagged_source}"
            else:
                msg = f"Not enough valid cited information: {path}"
            if msg not in gaps:
                gaps.append(msg)

        def check(obj, path=""):
            nonlocal citation_count, valid_citations
            if isinstance(obj, dict):
                for k, v in obj.items():
                    p = f"{path}.{k}" if path else k
                    if k == "citation" and isinstance(v, str):
                        citation_count += 1

                        # Single source of truth for tier + allow/deny
                        allowed, tier, _ = self.citation_validator.assess(v) if v else (False, None, 'empty')
                        is_valid = self.citation_validator.validate_medical_citation(v)  # now True for tiers 1/2/3

                        if allowed and is_valid:
                            # Count every allowed (tiers 1/2/3) as valid
                            valid_citations += 1
                            if tier in (1, 2, 3):
                                tier_counts[tier] += 1
                                valid_by_tier[tier] += 1
                        else:
                            # Only forbidden/empty hit this path → blank cite, set sibling to NA, add data_gap
                            invalid_citations.append(f"{p}: {v}")
                            obj[k] = ""  # blank invalid citation
                            for sk in list(obj.keys()):
                                if sk == "citation":
                                    continue
                                sv = obj[sk]
                                if isinstance(sv, (str, int, float)) and sv not in ("",):
                                    obj[sk] = None
                                    break
                            add_gap(path, flagged_source=v.strip())

                    elif isinstance(v, (dict, list)):
                        check(v, p)
            elif isinstance(obj, list):
                for i, it in enumerate(obj):
                    check(it, f"{path}[{i}]")

        check(report)

        # Update citation summary
        rep = report.setdefault('citations_summary', {})
        rep['total_citations'] = citation_count
        rep['valid_citations'] = valid_citations
        rep['citation_quality_score'] = f"{(valid_citations/max(1, citation_count)*100):.1f}%"
        if invalid_citations:
            rep['invalid_citations'] = invalid_citations[:10]

        #tier counts to the summary
        rep['tier_counts'] = {              
            "tier1": tier_counts[1],
            "tier2": tier_counts[2],
            "tier3": tier_counts[3],
        }
        rep['valid_by_tier'] = {
            "tier1": valid_by_tier[1],
            "tier2": valid_by_tier[2],
            "tier3": valid_by_tier[3],
        }
        return report


    def save_report(self, report: Dict[str, Any], input_file: str, analysis_type: str):
        """Save the analysis report with bibliography"""
        base_name = Path(input_file).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        report_file = f"{Config.OUTPUT_DIR}/{base_name}_{analysis_type}_lifesci_dd_{timestamp}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        biblio_file = f"{Config.OUTPUT_DIR}/{base_name}_{analysis_type}_bibliography_{timestamp}.txt"
        self.export_bibliography(report, biblio_file)

        print(f"✓ {analysis_type.upper()} analysis saved to: {report_file}")
        print(f"✓ Bibliography saved to: {biblio_file}")

        return report_file

    def export_bibliography(self, report: Dict, output_file: str):
        """Export formatted medical/scientific bibliography"""
        citations = []

        def extract_citations(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == 'citation' and isinstance(value, str) and value and not value.startswith('Not enough'):
                        if value not in citations:
                            citations.append(value)
                    elif isinstance(value, (dict, list)):
                        extract_citations(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_citations(item)

        extract_citations(report)

        journal_citations = [c for c in citations if any(j.lower() in c.lower() for j in
                               ['journal', 'nejm', 'lancet', 'jama', 'nature', 'science', 'cell'])]
        regulatory_citations = [c for c in citations if any(r in c.lower() for r in
                                  ['fda', 'ema', 'guidance', 'regulation', 'epar', 'sec.gov', 'orange book', 'purple book'])]
        trial_citations = [c for c in citations if 'nct' in c.lower() or 'clinicaltrials' in c.lower()]
        market_citations = [c for c in citations if any(m in c.lower() for m in
                               ['market', 'iqvia', 'evaluate', 'globaldata', 'citeline'])]
        other_citations = [c for c in citations if c not in journal_citations + regulatory_citations + trial_citations + market_citations]

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("MEDICAL & SCIENTIFIC BIBLIOGRAPHY\n")
            f.write("="*60 + "\n\n")

            if journal_citations:
                f.write("PEER-REVIEWED PUBLICATIONS\n")
                f.write("-"*40 + "\n")
                for i, citation in enumerate(sorted(journal_citations), 1):
                    f.write(f"[{i}] {citation}\n\n")

            if trial_citations:
                f.write("\nCLINICAL TRIALS\n")
                f.write("-"*40 + "\n")
                for i, citation in enumerate(sorted(trial_citations), 1):
                    f.write(f"[{i}] {citation}\n\n")

            if regulatory_citations:
                f.write("\nREGULATORY DOCUMENTS\n")
                f.write("-"*40 + "\n")
                for i, citation in enumerate(sorted(regulatory_citations), 1):
                    f.write(f"[{i}] {citation}\n\n")

            if market_citations:
                f.write("\nMARKET RESEARCH\n")
                f.write("-"*40 + "\n")
                for i, citation in enumerate(sorted(market_citations), 1):
                    f.write(f"[{i}] {citation}\n\n")

            if other_citations:
                f.write("\nOTHER SOURCES\n")
                f.write("-"*40 + "\n")
                for i, citation in enumerate(sorted(other_citations), 1):
                    f.write(f"[{i}] {citation}\n\n")

    def run_complete_analysis(self, input_file: str, record_index: Optional[int] = None):
        """Run only the US analysis for life sciences IP"""
        print(f"\n🧬 Starting Life Sciences Due Diligence Analysis")
        print("="*60)

        # Load data
        print("📁 Loading technology data...")
        technology_data = self.load_technology_data(input_file, record_index)

        # Detect and display category
        category, _ = self.detect_life_sciences_category(technology_data)
        print(f"🔬 Technology Category: {category}")

        # --- GLOBAL analysis (DISABLED) ---
        # print("\n🌍 Running GLOBAL life sciences analysis...")
        # print("   Searching medical/scientific literature...")
        # global_report = self.analyze_life_sciences_ip(technology_data, "global")
        # global_quality = global_report.get('citations_summary', {}).get('citation_quality_score', '0%')
        # print(f"   Citation Quality: {global_quality}")
        # global_file = self.save_report(global_report, input_file, "global")

        global_report = None
        global_file = None

        # Run US market analysis (ENABLED)
        print("\n🇺🇸 Running US MARKET life sciences analysis...")
        print("   Searching FDA/CMS/US medical sources...")
        us_report = self.analyze_life_sciences_ip(technology_data, "us")

        us_quality = us_report.get('citations_summary', {}).get('citation_quality_score', '0%')
        print(f"   Citation Quality: {us_quality}")

        us_file = self.save_report(us_report, input_file, "us")

        # Summary
        print("\n" + "="*60)
        print("✅ Life Sciences Analysis Complete!")
        print(f"📊 Technology Type: {category}")
        # print(f"📄 Global Report: {global_file}")  # (DISABLED)
        print(f"📄 US Report: {us_file}")

        # Citation summary
        print("\n📚 Citation Summary:")
        # print(f"   Global: {global_report.get('citations_summary', {}).get('total_citations', 0)} citations ({global_quality} valid)")  # (DISABLED)
        print(f"   US: {us_report.get('citations_summary', {}).get('total_citations', 0)} citations ({us_quality} valid)")

        
        return us_report  # or: return (None, us_report)

    
    # def run_complete_analysis(self, input_file: str, record_index: Optional[int] = None):
    #     """Run both global and US analyses for life sciences IP"""
    #     print(f"\n🧬 Starting Life Sciences Due Diligence Analysis")
    #     print("="*60)

    #     # Load data
    #     print("📁 Loading technology data...")
    #     technology_data = self.load_technology_data(input_file, record_index)

    #     # Detect and display category
    #     category, _ = self.detect_life_sciences_category(technology_data)
    #     print(f"🔬 Technology Category: {category}")

    #     # Run global analysis
    #     print("\n🌍 Running GLOBAL life sciences analysis...")
    #     print("   Searching medical/scientific literature...")
    #     global_report = self.analyze_life_sciences_ip(technology_data, "global")

    #     global_quality = global_report.get('citations_summary', {}).get('citation_quality_score', '0%')
    #     print(f"   Citation Quality: {global_quality}")

    #     global_file = self.save_report(global_report, input_file, "global")

    #     # Run US market analysis
    #     print("\n🇺🇸 Running US MARKET life sciences analysis...")
    #     print("   Searching FDA/CMS/US medical sources...")
    #     us_report = self.analyze_life_sciences_ip(technology_data, "us")

    #     us_quality = us_report.get('citations_summary', {}).get('citation_quality_score', '0%')
    #     print(f"   Citation Quality: {us_quality}")

    #     us_file = self.save_report(us_report, input_file, "us")

    #     # Summary
    #     print("\n" + "="*60)
    #     print("✅ Life Sciences Analysis Complete!")
    #     print(f"📊 Technology Type: {category}")
    #     print(f"📄 Global Report: {global_file}")
    #     print(f"📄 US Report: {us_file}")

    #     # Citation summary
    #     print("\n📚 Citation Summary:")
    #     print(f"   Global: {global_report.get('citations_summary', {}).get('total_citations', 0)} citations ({global_quality} valid)")
    #     print(f"   US: {us_report.get('citations_summary', {}).get('total_citations', 0)} citations ({us_quality} valid)")

    #     return global_report, us_report

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for the life sciences DD analyzer"""
    parser = argparse.ArgumentParser(
        description='Generate Life Sciences Due Diligence Reports with Medical/Scientific Citations'
    )
    parser.add_argument('--record-index', type=int, default=None, help='If the input JSON is a list, analyze just this 0-based index')
    parser.add_argument('input_file', help='Path to input JSON file containing life sciences IP data')
    parser.add_argument('--api-key', help='OpenAI API key (or set OPENAI_API_KEY env variable)')
    parser.add_argument('--model', default=Config.MODEL, help='OpenAI model to use (default: gpt-5)')
    parser.add_argument('--output-dir', default=Config.OUTPUT_DIR, help='Output directory for reports')

    args = parser.parse_args()

    # Update configuration
    if args.api_key:
        Config.OPENAI_API_KEY = args.api_key
    if args.model:
        Config.MODEL = args.model
    if args.output_dir:
        Config.OUTPUT_DIR = args.output_dir

    # Validate API key
    if not Config.OPENAI_API_KEY or Config.OPENAI_API_KEY == "your-api-key-here":
        print("❌ Error: OpenAI API key not set!")
        print("   Set it via --api-key flag or OPENAI_API_KEY environment variable")
        return

    # Run analysis
    try:
        analyzer = LifeSciencesDueDiligenceAnalyzer()
        analyzer.run_complete_analysis(args.input_file, args.record_index)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
