import asyncio
import time
import logging
import hashlib
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime

from llm_comparator.providers.manager import ProviderManager, ModelResponse
from llm_comparator.core.storage import ResultLogger
from llm_comparator.core.evaluators.deterministic import (
    exact_match_evaluator,
    json_schema_evaluator,
    regex_evaluator,
    sql_execution_evaluator,
    unit_test_evaluator
)
from llm_comparator.core.evaluators.subjective import rubric_evaluator, llm_judge_evaluator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TestCase:
    """Definition of a single benchmark test case."""
    task_id: str
    category: str
    prompt: str
    expected_format: str
    evaluation_method: str
    temperature: float = 0.0
    max_tokens: int = 1000
    expected_output: Optional[Any] = None
    schema: Optional[Dict[str, Any]] = None
    ground_truth: Optional[Any] = None
    rubric: Optional[Dict[str, Any]] = None
    unit_tests: Optional[List[str]] = None
    unit_test_setup: Optional[str] = None
    unit_test_expected: Optional[Any] = None

class Orchestrator:
    """Orchestrates async execution of benchmark tasks with rate limiting and error recovery."""

    def __init__(
        self, 
        provider_manager: ProviderManager, 
        result_logger: ResultLogger,
        max_concurrent_tasks: Optional[int] = None
    ):
        self.provider_manager = provider_manager
        self.result_logger = result_logger
        
        # Load from environment variables with fallback
        import os
        concurrency = max_concurrent_tasks or int(os.getenv("MAX_CONCURRENT_REQUESTS", 5))
        self.semaphore = asyncio.Semaphore(concurrency)
        self.max_retries = int(os.getenv("RETRY_MAX_ATTEMPTS", 3))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", 120))
        
        self.evaluator_map = {
            "exact_match": exact_match_evaluator,
            "json_schema": json_schema_evaluator,
            "regex": regex_evaluator,
            "sql_execution": sql_execution_evaluator,
            "unit_test": unit_test_evaluator,
            "rubric": rubric_evaluator,
            "llm_judge": llm_judge_evaluator
        }

    async def run_task(self, model_name: str, test_case: TestCase) -> Dict[str, Any]:
        """Execute a single task for a specific model with retries."""
        for attempt in range(self.max_retries):
            async with self.semaphore:
                logger.info(f"Running task {test_case.task_id} on model {model_name} (Attempt {attempt+1})")
                
                try:
                    # Apply timeout
                    response: ModelResponse = await asyncio.wait_for(
                        self.provider_manager.call_model(
                            model_name=model_name,
                            prompt=test_case.prompt,
                            temperature=test_case.temperature,
                            max_tokens=test_case.max_tokens
                        ),
                        timeout=self.request_timeout
                    )
                except asyncio.TimeoutError:
                    response = ModelResponse(
                        model_output="", tokens_prompt=0, tokens_completion=0, tokens_used=0,
                        latency_ms=self.request_timeout * 1000, cost_usd=0.0,
                        error="Request Timeout", provider="", model_name=model_name
                    )

                if response.error and attempt < self.max_retries - 1:
                    wait_time = int(os.getenv("RETRY_BACKOFF_FACTOR", 2)) ** attempt
                    logger.warning(f"Error on {model_name}: {response.error}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                # Evaluate
                score = 0.0
                justification = ""
                if not response.error:
                    eval_fn = self.evaluator_map.get(test_case.evaluation_method)
                    if eval_fn:
                        try:
                            # Map parameters based on evaluator type
                            params = {"output": response.model_output}
                            if test_case.evaluation_method == "exact_match":
                                params["ground_truth"] = test_case.ground_truth or test_case.expected_output
                            elif test_case.evaluation_method == "json_schema":
                                params["schema"] = test_case.schema or test_case.expected_output
                            elif test_case.evaluation_method == "regex":
                                params["pattern"] = test_case.ground_truth or test_case.expected_output
                            elif test_case.evaluation_method == "rubric":
                                params["rubric"] = test_case.rubric or {}
                            elif test_case.evaluation_method == "llm_judge":
                                params["prompt"] = test_case.prompt
                                params["reference"] = test_case.ground_truth or test_case.expected_output
                                params["criteria"] = test_case.rubric
                            
                            if asyncio.iscoroutinefunction(eval_fn):
                                score, justification = await eval_fn(**params)
                            else:
                                score, justification = eval_fn(**params)
                        except Exception as eval_e:
                            logger.error(f"Evaluation error for {test_case.task_id}: {eval_e}")
                            justification = f"Evaluation failed: {str(eval_e)}"
                    else:
                        logger.warning(f"No evaluator found for {test_case.evaluation_method}")
                        justification = "Evaluator not found"

                result = {
                    "task_id": test_case.task_id,
                    "model_name": model_name,
                    "provider": response.provider,
                    "category": test_case.category,
                    "status": "success" if not response.error else "error",
                    "score": float(score),
                    "justification": justification,
                    "latency_ms": response.latency_ms,
                    "cost_usd": response.cost_usd,
                    "tokens_used": response.tokens_used,
                    "tokens_prompt": response.tokens_prompt,
                    "tokens_completion": response.tokens_completion,
                    "raw_output": response.model_output,
                    "error_message": response.error,
                    "timestamp": datetime.now().isoformat()
                }
                # Log result
                result["run_id"] = "test_run"  # Default run_id
                await self.result_logger.log_result(result)
                return result

    async def run_benchmark(
        self, 
        models: List[str], 
        tasks: List[TestCase], 
        sample_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Run the full benchmark suite across multiple models and tasks."""
        if sample_size is not None:
            tasks = tasks[:sample_size]
            logger.info(f"Filtered to {sample_size} tasks per model for faster execution.")
        else:
            logger.info(f"Running full suite with {len(tasks)} tasks per model.")

        all_tasks = []
        for model in models:
            for task in tasks:
                all_tasks.append(self.run_task(model, task))

        results = await asyncio.gather(*all_tasks)
        return results