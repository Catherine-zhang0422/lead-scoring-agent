import argparse
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

from agent.parser import parse_input_file, parse_exhibitor_directory_url
from agent.searcher import FixtureSearchAdapter, SerpApiSearchAdapter
from agent.providers import get_llm_provider
from agent.researcher import BrandResearcher
from agent.scorer import ScoringEngine
from agent.exporter import export_leads


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Trade Show Lead Scoring Agent for UK Retail BD")
    parser.add_argument("--input", required=True, help="Path to CSV/Excel file or exhibitor directory URL")
    parser.add_argument("--mode", choices=["demo", "live"], default="demo", help="Execution mode (demo or live)")
    parser.add_argument("--scoring-config", default="config/scoring_config.json", help="Path to scoring configuration JSON")
    parser.add_argument("--output-dir", default="output/demo", help="Directory for output files")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of brands to process")

    args = parser.parse_args()

    print(f"=== Trade Show Lead Scoring Agent Starting [Mode: {args.mode.upper()}] ===")

    warnings = []
    raw_brands = []
    if args.input.startswith(("http://", "https://")):
        print(f"Parsing exhibitor directory URL: {args.input}")
        raw_brands, warnings = parse_exhibitor_directory_url(args.input, limit=args.limit)
    else:
        print(f"Parsing input file: {args.input}")
        raw_brands, file_warnings = parse_input_file(args.input)
        warnings.extend(file_warnings)

    if args.limit and len(raw_brands) > args.limit:
        raw_brands = raw_brands[:args.limit]
        warnings.append(f"Trimmed brand list to limit of {args.limit}.")

    print(f"Extracted {len(raw_brands)} unique brand(s) for research.")

    if args.mode == "demo":
        searcher = FixtureSearchAdapter()
    else:
        search_api_key = os.getenv("SEARCH_API_KEY")
        if not search_api_key:
            raise ValueError("SEARCH_API_KEY environment variable is required for live mode.")
        searcher = SerpApiSearchAdapter(api_key=search_api_key)

    llm = get_llm_provider(args.mode)
    researcher = BrandResearcher(searcher, llm)
    scorer = ScoringEngine(config_path=args.scoring_config)

    leads = []
    success_count = 0
    fail_count = 0

    for idx, brand_info in enumerate(raw_brands, 1):
        brand_name = brand_info["brand"]
        print(f"[{idx}/{len(raw_brands)}] Researching brand: {brand_name}...")
        
        lead_record = researcher.research_brand(brand_info)
        scored_lead = scorer.score_lead(lead_record)
        
        leads.append(scored_lead)

        if scored_lead.research_status.value in ("success", "partial"):
            success_count += 1
        else:
            fail_count += 1

    run_summary = {
        "mode": args.mode,
        "input": args.input,
        "total_processed": len(leads),
        "successful": success_count,
        "failed": fail_count,
        "warnings": warnings,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    export_leads(leads, args.output_dir, run_summary)
    print(f"=== Pipeline Completed Successfully. Outputs saved to '{args.output_dir}' ===")


if __name__ == "__main__":
    main()
