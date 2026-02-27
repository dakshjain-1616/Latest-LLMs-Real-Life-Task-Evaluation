"""
Storage Layer
JSONL writer and SQLite database management for benchmark results.
"""

import json
import sqlite3
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JSONLWriter:
    """Async JSONL writer for raw results."""
    
    def __init__(self, output_dir: str):
        """Initialize JSONL writer."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.lock = asyncio.Lock()
        self.current_file = None
        self.file_handle = None
    
    async def write_result(self, result: Dict[str, Any]):
        """Write a single result to JSONL file."""
        async with self.lock:
            if self.file_handle is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.current_file = self.output_dir / f"results_{timestamp}.jsonl"
                self.file_handle = open(self.current_file, 'a')
            
            json_line = json.dumps(result)
            self.file_handle.write(json_line + '\n')
            self.file_handle.flush()
    
    async def close(self):
        """Close the file handle."""
        async with self.lock:
            if self.file_handle:
                self.file_handle.close()
                self.file_handle = None
                logger.info(f"Closed JSONL file: {self.current_file}")


class SQLiteStorage:
    """SQLite database management for benchmark results."""
    
    def __init__(self, db_path: str):
        """Initialize SQLite storage."""
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                config_hash TEXT NOT NULL,
                suite_version TEXT NOT NULL,
                provider_credentials_hash TEXT,
                total_tasks INTEGER,
                completed_tasks INTEGER,
                status TEXT
            )
        """)
        
        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                prompt TEXT NOT NULL,
                expected_format TEXT,
                evaluation_method TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                temperature REAL,
                max_tokens INTEGER,
                success_threshold REAL
            )
        """)
        
        # Results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                provider TEXT NOT NULL,
                raw_output TEXT,
                score REAL,
                tokens_prompt INTEGER,
                tokens_completion INTEGER,
                tokens_used INTEGER,
                cost_usd REAL,
                latency_ms REAL,
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                timestamp TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id),
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
        """)
        
        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                category TEXT,
                mean_score REAL,
                std_dev REAL,
                median_score REAL,
                hallucination_rate REAL,
                failure_rate REAL,
                token_efficiency REAL,
                cost_normalized_score REAL,
                total_cost REAL,
                avg_latency_ms REAL,
                p50_latency_ms REAL,
                p95_latency_ms REAL,
                p99_latency_ms REAL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_run_id ON results(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_task_id ON results(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_model ON results(model_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_run_model ON metrics(run_id, model_name)")
        
        self.conn.commit()
        logger.info(f"SQLite database initialized: {self.db_path}")
    
    def insert_run(self, run_data: Dict[str, Any]):
        """Insert a new run record."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO runs (run_id, timestamp, config_hash, suite_version,
                            provider_credentials_hash, total_tasks, completed_tasks, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_data['run_id'],
            run_data['timestamp'],
            run_data['config_hash'],
            run_data['suite_version'],
            run_data.get('provider_credentials_hash', ''),
            run_data['total_tasks'],
            run_data.get('completed_tasks', 0),
            run_data.get('status', 'running')
        ))
        self.conn.commit()
    
    def insert_task(self, task_data: Dict[str, Any]):
        """Insert or update a task record."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tasks (task_id, category, prompt, expected_format,
                                         evaluation_method, weight, temperature, max_tokens, success_threshold)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_data['task_id'],
            task_data['category'],
            task_data['prompt'],
            task_data.get('expected_format', ''),
            task_data['evaluation_method'],
            task_data.get('weight', 1.0),
            task_data.get('temperature', 0.7),
            task_data.get('max_tokens', 1024),
            task_data.get('success_threshold', 0.7)
        ))
        self.conn.commit()
    
    def insert_result(self, result_data: Dict[str, Any]):
        """Insert a result record."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO results (run_id, task_id, model_name, provider, raw_output, score,
                               tokens_prompt, tokens_completion, tokens_used, cost_usd,
                               latency_ms, retry_count, error_message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result_data['run_id'],
            result_data['task_id'],
            result_data['model_name'],
            result_data['provider'],
            result_data.get('raw_output', ''),
            result_data.get('score'),
            result_data.get('tokens_prompt', 0),
            result_data.get('tokens_completion', 0),
            result_data.get('tokens_used', 0),
            result_data.get('cost_usd', 0.0),
            result_data.get('latency_ms', 0.0),
            result_data.get('retry_count', 0),
            result_data.get('error_message'),
            result_data.get('timestamp', datetime.now().isoformat())
        ))
        self.conn.commit()
    
    def insert_metrics(self, metrics_data: Dict[str, Any]):
        """Insert aggregated metrics."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO metrics (run_id, model_name, category, mean_score, std_dev, median_score,
                               hallucination_rate, failure_rate, token_efficiency,
                               cost_normalized_score, total_cost, avg_latency_ms,
                               p50_latency_ms, p95_latency_ms, p99_latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metrics_data['run_id'],
            metrics_data['model_name'],
            metrics_data.get('category'),
            metrics_data.get('mean_score'),
            metrics_data.get('std_dev'),
            metrics_data.get('median_score'),
            metrics_data.get('hallucination_rate'),
            metrics_data.get('failure_rate'),
            metrics_data.get('token_efficiency'),
            metrics_data.get('cost_normalized_score'),
            metrics_data.get('total_cost'),
            metrics_data.get('avg_latency_ms'),
            metrics_data.get('p50_latency_ms'),
            metrics_data.get('p95_latency_ms'),
            metrics_data.get('p99_latency_ms')
        ))
        self.conn.commit()
    
    def get_results_by_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all results for a specific run."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM results WHERE run_id = ?", (run_id,))
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    
    def get_metrics_by_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all metrics for a specific run."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM metrics WHERE run_id = ?", (run_id,))
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    
    def update_run_status(self, run_id: str, status: str, completed_tasks: int):
        """Update run status and completed task count."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE runs SET status = ?, completed_tasks = ? WHERE run_id = ?
        """, (status, completed_tasks, run_id))
        self.conn.commit()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("SQLite database connection closed")


class ResultLogger:
    """Unified result logger for JSONL and SQLite."""
    
    def __init__(self, jsonl_dir: str, db_path: str):
        """Initialize result logger."""
        self.jsonl_writer = JSONLWriter(jsonl_dir)
        self.sqlite_storage = SQLiteStorage(db_path)
    
    async def log_result(self, result: Dict[str, Any]):
        """Log result to both JSONL and SQLite."""
        # Write to JSONL
        await self.jsonl_writer.write_result(result)
        
        # Write to SQLite
        self.sqlite_storage.insert_result(result)
    
    def log_run(self, run_data: Dict[str, Any]):
        """Log run metadata."""
        self.sqlite_storage.insert_run(run_data)
    
    def log_task(self, task_data: Dict[str, Any]):
        """Log task definition."""
        self.sqlite_storage.insert_task(task_data)
    
    def log_metrics(self, metrics_data: Dict[str, Any]):
        """Log aggregated metrics."""
        self.sqlite_storage.insert_metrics(metrics_data)
    
    def update_run_status(self, run_id: str, status: str, completed_tasks: int):
        """Update run status."""
        self.sqlite_storage.update_run_status(run_id, status, completed_tasks)
    
    async def close(self):
        """Close all connections."""
        await self.jsonl_writer.close()
        self.sqlite_storage.close()
