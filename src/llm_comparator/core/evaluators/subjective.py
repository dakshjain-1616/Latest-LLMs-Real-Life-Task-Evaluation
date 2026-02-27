"""
Subjective Evaluators
Scoring functions for open-ended evaluation using rubrics and LLM-as-judge.
"""

import json
import asyncio
from typing import Dict, Any, Tuple, Optional
import logging
import os
import sys
import yaml

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from llm_comparator.providers.manager import ProviderManager as ModelAbstraction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_judge_config() -> Dict[str, Any]:
    """Load judge configuration from benchmark.yaml."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        '../../config/benchmark.yaml'
    )
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('benchmark', {}).get('judge_config', {})
    except Exception as e:
        logger.warning(f"Failed to load judge config: {e}, using defaults")
        return {
            'model': 'anthropic/claude-3-opus-20240229',
            'temperature': 0.3,
            'use_chain_of_thought': True
        }


def rubric_evaluator(
    output: str,
    rubric: Dict[str, Any],
    **kwargs
) -> Tuple[float, str]:
    """
    Rule-based rubric evaluation.

    Args:
        output: Model output string
        rubric: Dictionary with evaluation criteria and scoring rules

    Returns:
        Tuple of (score, justification)
    """
    total_score = 0.0
    max_score = 0.0
    justifications = []

    for criterion, rules in rubric.get('criteria', {}).items():
        criterion_score = 0.0
        criterion_max = rules.get('max_points', 1.0)
        max_score += criterion_max

        # Check each rule
        for rule in rules.get('rules', []):
            condition = rule.get('condition', '')
            points = rule.get('points', 0.0)

            # Simple keyword/pattern matching
            if condition == 'contains':
                if rule.get('value', '') in output:
                    criterion_score += points
                    justifications.append(f"{criterion}: +{points} ({rule.get('description', 'matched')})")

            elif condition == 'min_length':
                if len(output) >= rule.get('value', 0):
                    criterion_score += points
                    justifications.append(f"{criterion}: +{points} (length requirement met)")

            elif condition == 'max_length':
                if len(output) <= rule.get('value', float('inf')):
                    criterion_score += points
                    justifications.append(f"{criterion}: +{points} (within length limit)")

            elif condition == 'has_structure':
                # Check for basic structure markers
                structure_type = rule.get('value', '')
                if structure_type == 'paragraphs' and '\n\n' in output:
                    criterion_score += points
                    justifications.append(f"{criterion}: +{points} (has paragraphs)")
                elif structure_type == 'bullet_points' and ('•' in output or '-' in output):
                    criterion_score += points
                    justifications.append(f"{criterion}: +{points} (has bullet points)")

        total_score += min(criterion_score, criterion_max)

    # Normalize to 0-1 scale
    normalized_score = total_score / max_score if max_score > 0 else 0.0
    justification = "; ".join(justifications) if justifications else "No criteria met"

    return normalized_score, justification


async def llm_judge_evaluator(
    output: str,
    prompt: str,
    reference: Optional[str] = None,
    judge_model: Optional[str] = None,
    criteria: Optional[Dict[str, str]] = None,
    **kwargs
) -> Tuple[float, str]:
    """
    LLM-as-judge evaluation using configurable judge model (async).

    Args:
        output: Model output to evaluate
        prompt: Original task prompt
        reference: Reference/ground truth answer (optional)
        judge_model: Model to use as judge (format: "provider/model-name")
                     If None, uses default from config
        criteria: Evaluation criteria (dict of dimension: description)

    Returns:
        Tuple of (score, justification)
    """
    # Load judge configuration
    judge_config = _load_judge_config()

    # Use provided judge_model or fall back to config default
    if judge_model is None:
        judge_model = judge_config.get('model', 'anthropic/claude-3-opus-20240229')

    # Use provider from config (not parsed from model string) to avoid
    # deprecated-provider errors when model_id has an 'anthropic/' prefix.
    provider = judge_config.get('provider', 'openrouter')
    # model_name is the full model_id (e.g. "anthropic/claude-opus-4-6")
    # passed directly to call_model which resolves it via the model index.
    model_name = judge_model

    try:
        # Initialize model abstraction
        model_abstraction = ModelAbstraction()

        # Build evaluation prompt with chain-of-thought
        eval_criteria = criteria or {
            'correctness': 'Is the answer factually correct and complete?',
            'relevance': 'Does the answer directly address the question?',
            'clarity': 'Is the answer clear and well-structured?',
            'conciseness': 'Is the answer appropriately concise without unnecessary information?'
        }

        criteria_text = "\n".join([f"- {k}: {v}" for k, v in eval_criteria.items()])

        evaluation_prompt = f"""You are an expert evaluator. Evaluate the following model output based on these criteria:

{criteria_text}

Original Task Prompt:
{prompt}

Model Output to Evaluate:
{output}
"""

        if reference:
            evaluation_prompt += f"""
Reference Answer (for comparison):
{reference}
"""

        evaluation_prompt += """
Instructions:
1. Analyze the output against each criterion
2. Provide a score from 1-5 for each criterion (1=poor, 5=excellent)
3. Calculate an overall score (average of criterion scores)
4. Provide brief justification

Respond in JSON format:
{
  "criterion_scores": {"correctness": 4, "relevance": 5, ...},
  "overall_score": 4.2,
  "justification": "Brief explanation..."
}
"""

        # Prepare call_model config
        max_tokens = 1024
        system_prompt = 'You are an objective evaluator. Respond only with valid JSON.'
        temperature = judge_config.get('temperature', 0.3)

        # Directly await the async call_model — no new event loop needed
        response = await model_abstraction.call_model(
            model_name=model_name,
            prompt=evaluation_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Check for errors
        if response.error:
            logger.error(f"Judge model call failed: {response.error}")
            return 0.5, f"Judge evaluation failed: {response.error}"

        judge_output = response.model_output.strip()

        # Extract JSON (handle markdown code blocks)
        if judge_output.startswith("```"):
            lines = judge_output.split('\n')
            judge_output = '\n'.join(lines[1:-1]) if len(lines) > 2 else judge_output
            judge_output = judge_output.replace("```json", "").replace("```", "").strip()

        result = json.loads(judge_output)

        # Normalize score to 0-1 range (from 1-5 scale)
        overall_score = result.get('overall_score', 3.0)
        normalized_score = (overall_score - 1) / 4  # Scale from [1,5] to [0,1]

        justification = result.get('justification', 'No justification provided')

        return normalized_score, justification

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse judge response as JSON: {e}")
        return 0.5, f"Judge evaluation failed (JSON parse error): {str(e)}"

    except Exception as e:
        logger.error(f"LLM judge evaluation failed: {e}")
        return 0.5, f"Judge evaluation error: {str(e)}"


async def pairwise_comparison_evaluator(
    output1: str,
    output2: str,
    prompt: str,
    judge_model: Optional[str] = None,
    **kwargs
) -> Tuple[str, str]:
    """
    Pairwise comparison between two outputs using LLM judge (async).

    Args:
        output1: First model output
        output2: Second model output
        prompt: Original task prompt
        judge_model: Model to use as judge (format: "provider/model-name")
                     If None, uses default from config

    Returns:
        Tuple of (winner, justification) where winner is "output1", "output2", or "tie"
    """
    # Load judge configuration
    judge_config = _load_judge_config()

    # Use provided judge_model or fall back to config default
    if judge_model is None:
        judge_model = judge_config.get('model', 'anthropic/claude-3-opus-20240229')

    # Use provider from config (not parsed from model string)
    provider = judge_config.get('provider', 'openrouter')
    model_name = judge_model

    try:
        # Initialize model abstraction
        config_dir = os.path.join(os.path.dirname(__file__), '../../config')
        model_abstraction = ModelAbstraction(config_dir=config_dir)

        comparison_prompt = f"""You are an expert evaluator. Compare two model outputs for the same task.

Original Task:
{prompt}

Output A:
{output1}

Output B:
{output2}

Which output is better? Consider:
- Correctness and accuracy
- Completeness
- Clarity and structure
- Following instructions

Respond in JSON format:
{{
  "winner": "A" or "B" or "tie",
  "justification": "Brief explanation..."
}}
"""

        # Prepare call_model config
        call_config = {
            'temperature': judge_config.get('temperature', 0.3),
            'max_tokens': 512,
            'system_prompt': 'You are an objective evaluator. Respond only with valid JSON.'
        }

        # Directly await the async call_model — no new event loop needed
        response = await model_abstraction.call_model(
            provider=provider,
            model_name=model_name,
            prompt=comparison_prompt,
            config=call_config
        )

        # Check for errors
        if response.error:
            logger.error(f"Judge model call failed: {response.error}")
            return "tie", f"Comparison failed: {response.error}"

        judge_output = response.model_output.strip()

        # Extract JSON
        if judge_output.startswith("```"):
            lines = judge_output.split('\n')
            judge_output = '\n'.join(lines[1:-1]) if len(lines) > 2 else judge_output
            judge_output = judge_output.replace("```json", "").replace("```", "").strip()

        result = json.loads(judge_output)
        winner = result.get('winner', 'tie').lower()

        # Map to output names
        if winner == 'a':
            winner = 'output1'
        elif winner == 'b':
            winner = 'output2'

        justification = result.get('justification', 'No justification provided')

        return winner, justification

    except Exception as e:
        logger.error(f"Pairwise comparison failed: {e}")
        return "tie", f"Comparison error: {str(e)}"
