import json
import csv
import os
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from datetime import datetime

class ReportingEngine:
    """Generates comprehensive reports and structured data from benchmark results."""

    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_report(self, results: List[Dict[str, Any]], models: List[str]) -> str:
        """Generate a Markdown report from results."""
        df = pd.DataFrame(results)
        
        # Summary statistics per model
        summary = df.groupby('model_name').agg({
            'score': 'mean',
            'latency_ms': 'mean',
            'cost_usd': 'sum',
            'status': lambda x: (x == 'success').mean() * 100
        }).round(4)
        summary.columns = ['Avg Score', 'Avg Latency (ms)', 'Total Cost (USD)', 'Success Rate (%)']
        
        # Ensure non-zero formatting for very small costs
        summary['Total Cost (USD)'] = summary['Total Cost (USD)'].apply(lambda x: f"{x:.6f}")
        summary['Avg Score'] = summary['Avg Score'].apply(lambda x: f"{x:.4f}")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = f"# LLM Comparison Report\n"
        report += f"Generated on: {timestamp}\n\n"
        
        # Executive Summary
        report += "## Executive Summary\n"
        if len(models) > 5:
            # Transpose summary for readability if many models
            report += summary.transpose().to_markdown() + "\n\n"
        else:
            report += summary.to_markdown() + "\n\n"
        
        # Category Performance
        report += "## Performance by Category\n"
        cat_summary = df.groupby(['model_name', 'category'])['score'].mean().unstack().round(3)
        if len(models) > 5:
            # Transpose category summary too
            report += cat_summary.transpose().to_markdown() + "\n\n"
        else:
            report += cat_summary.to_markdown() + "\n\n"
        
        report += "## Detailed Results\n"
        report += df[['task_id', 'model_name', 'category', 'status', 'score', 'latency_ms']].head(20).to_markdown()
        if len(df) > 20:
            report += f"\n\n*(Showing top 20 of {len(df)} results)*\n"

        # Save report
        report_path = os.path.join(self.output_dir, f"comparison_report_{datetime.now().strftime('%Y%md_%H%M%S')}.md")
        with open(report_path, 'w') as f:
            f.write(report)
        
        # Save structured data
        self._save_structured_data(df)
        
        return report_path

    def _save_structured_data(self, df: pd.DataFrame):
        """Save results to JSON and CSV."""
        base_name = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        df.to_csv(os.path.join(self.output_dir, f"{base_name}.csv"), index=False)
        df.to_json(os.path.join(self.output_dir, f"{base_name}.json"), orient='records', indent=2)
        logger.info(f"Structured data saved to {self.output_dir}")

import logging
logger = logging.getLogger(__name__)
