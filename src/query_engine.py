import os
import logging
from typing import Dict, Any, List
from src.db import execute_query, DEFAULT_DB_PATH
from src.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

class QueryEngine:
    """Processes natural language questions about ticket data into SQL queries and results."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.llm_provider = LLMProvider()

    def process_query(self, user_question: str) -> Dict[str, Any]:
        """
        Main interface to answer natural language questions about the ticket database.
        Returns dictionary containing:
        - question: original question
        - sql: generated SQL query
        - explanation: explanation of SQL logic
        - columns: column names
        - rows: row dictionary list
        - row_count: total rows returned
        - answer_summary: human-friendly text summary of results
        - success: boolean
        - error: error string if any
        """
        if not user_question or not user_question.strip():
            return {
                "question": user_question,
                "sql": "",
                "explanation": "",
                "columns": [],
                "rows": [],
                "row_count": 0,
                "answer_summary": "Please enter a valid non-empty question.",
                "success": False,
                "error": "Empty question provided."
            }

        # Step 1: Generate SQL query using LLM or smart fallback
        sql_gen_result = self.llm_provider.text_to_sql(user_question)
        sql_query = sql_gen_result.get("sql", "").strip()
        explanation = sql_gen_result.get("explanation", "Executed SQL query against tickets dataset.")

        if not sql_query:
            return {
                "question": user_question,
                "sql": "",
                "explanation": explanation,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "answer_summary": "Failed to translate natural language question to SQL.",
                "success": False,
                "error": "SQL translation failure."
            }

        # Step 2: Execute SQL query on SQLite database safely
        query_result = execute_query(sql_query, self.db_path)

        if not query_result["success"]:
            return {
                "question": user_question,
                "sql": sql_query,
                "explanation": explanation,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "answer_summary": f"Query execution error: {query_result['error']}",
                "success": False,
                "error": query_result["error"]
            }

        rows = query_result["rows"]
        columns = query_result["columns"]
        row_count = query_result["row_count"]

        # Step 3: Format natural language summary of answer
        answer_summary = self._build_answer_summary(user_question, rows, columns, row_count)

        return {
            "question": user_question,
            "sql": sql_query,
            "explanation": explanation,
            "columns": columns,
            "rows": rows,
            "row_count": row_count,
            "answer_summary": answer_summary,
            "success": True,
            "error": None
        }

    def _build_answer_summary(self, question: str, rows: List[Dict[str, Any]], columns: List[str], row_count: int) -> str:
        """Construct a concise natural language summary based on query results."""
        if row_count == 0:
            return "No matching tickets or records found for your query."

        # Case 1: Aggregate single-row answer (COUNT, AVG, MAX, MIN)
        if row_count == 1:
            row = rows[0]
            items = [f"{col}: {val}" for col, val in row.items()]
            return f"Result: {', '.join(items)}."

        # Case 2: Agent ranking or grouped results
        if "agent_id" in columns and row_count <= 5:
            agent_details = [f"Agent {r.get('agent_id')}: {list(r.values())[1]}" for r in rows]
            return f"Found {row_count} matching agent records. Top records: {'; '.join(agent_details)}."

        # Case 3: Tabular listing
        return f"Found {row_count} matching tickets for query '{question}'."
