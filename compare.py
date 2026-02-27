import argparse
import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Ensure src is in path
sys.path.append(os.path.abspath("src"))

from llm_comparator.core.orchestrator import Orchestrator
from llm_comparator.core.storage import ResultLogger
from llm_comparator.providers.manager import ProviderManager
from llm_comparator.reporting.engine import ReportingEngine

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

async def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="LLM Comparison Tool")
    parser.add_argument("--models", nargs="+", help="List of models to compare")
    parser.add_argument("--profile", type=str, help="Named profile from comparison_profiles.yaml")
    parser.add_argument("--limit", type=int, help="Limit number of tasks for evaluation (if not set, runs all tasks)")
    parser.add_argument("--quick", action="store_true", help="Run a quick evaluation with 5 tasks per model")
    parser.add_argument("--output", default="results/reports", help="Output directory for reports")
    
    args = parser.parse_args()

    if not args.models and not args.profile:
        parser.error("At least one of --models or --profile must be specified.")

    setup_logging()
    logger = logging.getLogger("LLMComparator")

    models = args.models or []
    if args.profile:
        import yaml
        profile_path = "src/llm_comparator/config/comparison_profiles.yaml"
        if os.path.exists(profile_path):
            with open(profile_path, 'r') as f:
                profiles = yaml.safe_load(f)
                if args.profile in profiles:
                    models.extend(profiles[args.profile])
                    logger.info(f"Loaded profile '{args.profile}': {profiles[args.profile]}")
                else:
                    logger.error(f"Profile '{args.profile}' not found in {profile_path}")
                    sys.exit(1)
        else:
            logger.error(f"Profiles file not found at {profile_path}")
            sys.exit(1)

    # Set sample size based on flags
    sample_size = args.limit
    if args.quick:
        sample_size = 5
    
    logger.info(f"Starting comparison for models: {models}")
    
    # Initialize components
    storage = ResultLogger(jsonl_dir="results/raw", db_path="results/eval.db")
    provider_manager = ProviderManager()
    orchestrator = Orchestrator(
        provider_manager=provider_manager,
        result_logger=storage
    )
    
    # Load tasks
    from llm_comparator.core.tasks import get_all_tasks
    tasks = get_all_tasks()
    
    # Run benchmark
    results = await orchestrator.run_benchmark(
        models=models,
        tasks=tasks,
        sample_size=sample_size
    )
    
    # Generate report
    report_engine = ReportingEngine(output_dir=args.output)
    report_path = report_engine.generate_report(results=results, models=models)
    
    logger.info(f"Evaluation complete. Report generated at: {report_path}")

if __name__ == "__main__":
    asyncio.run(main())
