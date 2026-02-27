# 🤖 LLM Comparator — Multi-Model Benchmarking Tool

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Async](https://img.shields.io/badge/Execution-Async%20Parallel-green.svg)]()
[![Models](https://img.shields.io/badge/Models-150%2B%20Tasks-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()
[![Powered by NEO](https://img.shields.io/badge/powered%20by-NEO-purple)](https://heyneo.so/)
[![VSCode Extension](https://img.shields.io/badge/VSCode-Extension-blue?logo=visual-studio-code)](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo)

**A modular, async benchmarking tool to compare LLMs across providers on real-world tasks — performance, cost, and reliability in one report.**

**Architected by [NEO](https://heyneo.so/)** — An autonomous ML agent 

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Categories](#-evaluation-categories) • [Metrics](#-metrics)

---

## 🎯 Overview

LLM Comparator lets you benchmark any number of models from **OpenAI, Anthropic, Google, ZhipuAI**, or the unified **OpenRouter** API — side by side, in parallel, with granular cost and accuracy breakdowns.

- **Multi-Provider**: Native API keys or OpenRouter unified access
- **150+ Tasks** across 10 real-world categories
- **Async Parallel Execution**: Fast benchmarking across all models simultaneously
- **Auto Cost Analysis**: Token-based USD cost estimates per model
- **Security First**: API keys via `.env`, never logged or stored

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Dynamic Scaling** | Benchmark unlimited models in a single run |
| **Task Density Control** | `--quick` (5 tasks), `--limit N`, or full 150+ suite |
| **LLM-as-a-Judge** | Accuracy scored via Exact Match, Regex, JSON Schema + LLM rubric |
| **Cost Registry** | Per-model USD cost from `config/models.yaml` pricing metadata |
| **Multi-Format Reports** | Markdown + JSON/CSV output |

---

## 📊 Evaluation Categories

| Category | Tasks | Focus |
|----------|-------|-------|
| **Coding** | 40 | Flask/FastAPI, refactoring, algorithms |
| **Structured Output** | 25 | JSON Schema, CSV, XML, YAML compliance |
| **Summarization** | 20 | Executive summaries, compression |
| **Reasoning** | 20 | Multi-step logic, Sudoku, financial |
| **Multi-turn Memory** | 15 | Context retention over long interactions |
| **Data Extraction** | 8 | Entity recognition, relationship extraction |
| **SQL Generation** | 8 | Complex joins, aggregations from NL |
| **Tool Use** | 8 | Tool call specification & parameter selection |
| **Hallucination Robustness** | 8 | Prompt injection, conflicting instructions |
| **Long-context Stress** | 8 | Retrieval from 32k+ token documents |

---

## 🚀 Installation
```bash
git clone <repository-url>
cd latestLLMEval

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in your API keys
```

### Supported API Keys

### Supported API Keys

| Key | Provider |
|-----|----------|
| `OPENROUTER_API_KEY` | Unified access to all models |
| `OPENAI_API_KEY` | GPT-4o, O1, etc. |
| `ANTHROPIC_API_KEY` | Claude 3.5 / 4.6 |
| `GOOGLE_API_KEY` | Gemini |
| `ZHIPU_API_KEY` | GLM-5 |

## 🌐 OpenRouter Integration

The tool can benchmark any model supported by [OpenRouter](https://openrouter.ai/models). Models can be specified by their full OpenRouter ID or by predefined aliases in `config/models.yaml`.

- **Automatic Routing**: Any model name provided to `--models` that is not found in the local registry defaults to OpenRouter.
- **Unified Attribution**: Costs and latency are tracked even when using the unified API.

## 🛠️ Usage

### Standard Run
Execute a full evaluation across multiple models:
```bash
# Mix native and OpenRouter models
python3 compare.py --models gpt-4o-native claude-4.6-sonnet-or gemini-3.1-pro-native

# Using full OpenRouter IDs (auto-detected)
python3 compare.py --models meta-llama/llama-3.1-405b-instruct anthropic/claude-3.5-sonnet
```

### Quick Run
Useful for rapid testing or sanity checks (uses a subset of tasks):
```bash
# Quick run through OpenRouter for a specific model
python3 compare.py --models anthropic/claude-3-5-sonnet:beta --quick

# Multi-model quick benchmark
python3 compare.py --models gpt-4o-or gemini-3.1-pro-or --quick
```

### Profile Run
Use pre-defined model sets from `config/comparison_profiles.yaml`:
```bash
# Standard profile run
python3 compare.py --profile frontier-openrouter

# Quick profile run
python3 compare.py --profile frontier-openrouter --quick
```

### Advanced Options
```bash
# Limit evaluation to the first 20 tasks
python3 compare.py --models gpt-4o --limit 20

# Run full 150+ benchmark to custom directory
python3 compare.py --models flagship-models --output results/full_eval
```

---

## 📈 Metrics

## 📈 Metrics

Every report includes:

- **Accuracy/Quality Score** — Exact Match, Regex, JSON Schema, LLM-as-a-Judge
- **Latency** — Time-to-first-token & total completion time
- **Cost** — Estimated USD per model from token usage
- **Category Breakdown** — Side-by-side per-category comparison

## 📊 Sample Results

From a recent benchmark run (2026-02-27):

### Executive Summary
| model_name                  |   Avg Score |   Avg Latency (ms) |   Total Cost (USD) |   Success Rate (%) |
|:----------------------------|------------:|-------------------:|-------------------:|-------------------:|
| anthropic/claude-opus-4.6   |      0.865  |            24373.7 |             0      |                100 |
| anthropic/claude-sonnet-4.5 |      0.8835 |            22262.4 |             0      |                100 |
| google/gemini-3-pro-preview |      0.8585 |            19694.6 |             0      |                100 |
| openai/gpt-5.1              |      0.8835 |            15005.5 |             0      |                100 |
| z-ai/glm-5                  |      0.9085 |            67209.4 |             0.0879 |                100 |

### Performance by Category (Coding)
| model_name                  |   coding |
|:----------------------------|---------:|
| anthropic/claude-opus-4.6   |    0.865 |
| anthropic/claude-sonnet-4.5 |    0.884 |
| google/gemini-3-pro-preview |    0.858 |
| openai/gpt-5.1              |    0.884 |
| z-ai/glm-5                  |    0.909 |

## 📁 Project Structure
```
latestLLMEval/
├── compare.py                          # CLI entry point
├── src/llm_comparator/
│   ├── providers/                      # OpenAI, Anthropic, Google, ZhipuAI, OpenRouter
│   ├── core/tasks.py                   # Task definitions & evaluation logic
│   └── config/models.yaml             # Model registry & pricing metadata
└── results/reports/                    # Markdown, JSON, CSV outputs
```

---

## 🔧 Troubleshooting

- **Zero costs**: Verify `.env` keys are valid; missing native keys fall back to OpenRouter
- **Missing scores**: `llm_judge` requires `OPENROUTER_API_KEY` or `OPENAI_API_KEY`
- **No response recorded**: Model hit rate limits or safety filters — no score is logged
- **Pricing mismatch**: Check `config/models.yaml` for your model's identifier

---

## 📄 License

MIT License

---

**⚡ Powered by [NEO](https://heyneo.so/)** — Autonomous ML agent 
Get the [VSCode Extension](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo) to build with NEO directly in your editor.

Made with ❤️ using NEO 