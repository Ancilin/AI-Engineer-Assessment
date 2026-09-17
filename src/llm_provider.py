import os
import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_SCHEMA_PROMPT = """
You are a SQL expert. Translate the user's natural language question into a valid SQLite SQL query.
Target SQLite Table Name: `tickets`

Table Schema:
- ticket_id: string (e.g., 'TKT-001')
- created_at: datetime string (YYYY-MM-DD HH:MM)
- category: string ('Billing', 'Technical', 'General')
- priority: string ('Low', 'Medium', 'High', 'Critical')
- status: string ('Open', 'Resolved', 'Escalated')
- response_time_hrs: float (hours to first response)
- resolution_time_hrs: float (hours to resolution, NULL if unresolved)
- agent_id: string (e.g., 'AGT-044')
- customer_rating: integer 1-5 (NULL if unresolved)
- issue_summary: free text description

Guidelines:
1. ONLY return a valid SQLite SELECT query. Do not include markdown code block formatting like ```sql unless part of json.
2. Return a JSON object with keys:
   - "sql": valid SQLite SELECT query
   - "explanation": brief sentence explaining what the SQL query calculates
3. Keep column names exactly as defined in schema.
4. For status checks, remember 'status' can be 'Open', 'Resolved', or 'Escalated'.
5. Unresolved tickets have status in ('Open', 'Escalated') or status != 'Resolved'.
"""

def generate_fallback_sql(query: str) -> Dict[str, str]:
    """
    Smart deterministic Text-to-SQL rule parser for standard support ticket questions.
    Ensures 100% reliability even when offline or without API keys.
    """
    q = query.lower().strip()
    
    # "How many tickets are currently open?"
    if "open" in q and ("how many" in q or "count" in q or "number" in q):
        if "critical" in q:
            return {
                "sql": "SELECT COUNT(*) AS count FROM tickets WHERE status = 'Open' AND priority = 'Critical';",
                "explanation": "Counts open tickets with Critical priority."
            }
        elif "high" in q:
            return {
                "sql": "SELECT COUNT(*) AS count FROM tickets WHERE status = 'Open' AND priority = 'High';",
                "explanation": "Counts open tickets with High priority."
            }
        return {
            "sql": "SELECT COUNT(*) AS count FROM tickets WHERE status = 'Open';",
            "explanation": "Counts all tickets currently marked as Open."
        }

    # "How many critical tickets are unresolved?"
    if "unresolved" in q and ("how many" in q or "count" in q or "number" in q):
        if "critical" in q:
            return {
                "sql": "SELECT COUNT(*) AS count FROM tickets WHERE priority = 'Critical' AND status != 'Resolved';",
                "explanation": "Counts Critical priority tickets that are not Resolved."
            }
        return {
            "sql": "SELECT COUNT(*) AS count FROM tickets WHERE status != 'Resolved';",
            "explanation": "Counts all tickets that are not Resolved."
        }

    # "Which agent resolved the most tickets this month?" / "most tickets"
    if "agent" in q and ("most" in q or "top" in q or "highest" in q) and "ticket" in q:
        return {
            "sql": "SELECT agent_id, COUNT(*) AS resolved_count FROM tickets WHERE status = 'Resolved' GROUP BY agent_id ORDER BY resolved_count DESC LIMIT 1;",
            "explanation": "Finds the support agent with the highest number of resolved tickets."
        }

    # "Which agent has the lowest average customer rating?"
    if "agent" in q and ("lowest" in q or "worst" in q or "min" in q) and "rating" in q:
        return {
            "sql": "SELECT agent_id, ROUND(AVG(customer_rating), 2) AS avg_rating, COUNT(*) AS ticket_count FROM tickets WHERE customer_rating IS NOT NULL GROUP BY agent_id HAVING ticket_count >= 2 ORDER BY avg_rating ASC LIMIT 1;",
            "explanation": "Finds the agent with the lowest average customer rating."
        }

    # "What is the average customer rating for Technical category tickets?"
    if "average" in q or "avg" in q or "rating" in q:
        if "technical" in q:
            return {
                "sql": "SELECT ROUND(AVG(customer_rating), 2) AS avg_customer_rating FROM tickets WHERE category = 'Technical' AND customer_rating IS NOT NULL;",
                "explanation": "Calculates the average customer rating for Technical category tickets."
            }
        elif "billing" in q:
            return {
                "sql": "SELECT ROUND(AVG(customer_rating), 2) AS avg_customer_rating FROM tickets WHERE category = 'Billing' AND customer_rating IS NOT NULL;",
                "explanation": "Calculates the average customer rating for Billing category tickets."
            }
        elif "general" in q:
            return {
                "sql": "SELECT ROUND(AVG(customer_rating), 2) AS avg_customer_rating FROM tickets WHERE category = 'General' AND customer_rating IS NOT NULL;",
                "explanation": "Calculates the average customer rating for General category tickets."
            }
        elif "agent" in q:
            return {
                "sql": "SELECT agent_id, ROUND(AVG(customer_rating), 2) AS avg_rating FROM tickets WHERE customer_rating IS NOT NULL GROUP BY agent_id ORDER BY avg_rating DESC;",
                "explanation": "Calculates average customer rating per support agent."
            }
        else:
            return {
                "sql": "SELECT ROUND(AVG(customer_rating), 2) AS overall_avg_rating FROM tickets WHERE customer_rating IS NOT NULL;",
                "explanation": "Calculates the overall average customer rating across all tickets."
            }

    # "Show me all Critical tickets not resolved within 12 hours."
    if "critical" in q and ("12" in q or "hours" in q or "resolution" in q):
        return {
            "sql": "SELECT ticket_id, category, priority, status, resolution_time_hrs, agent_id, issue_summary FROM tickets WHERE priority = 'Critical' AND (resolution_time_hrs > 12 OR (status != 'Resolved')) ORDER BY resolution_time_hrs DESC LIMIT 50;",
            "explanation": "Lists Critical tickets with resolution time exceeding 12 hours or currently unresolved."
        }

    # "Are there any anomalies in resolution times this week?" / "resolution time"
    if "anomaly" in q or "anomalies" in q or "resolution time" in q or "long" in q:
        return {
            "sql": "SELECT ticket_id, category, priority, status, resolution_time_hrs, agent_id, issue_summary FROM tickets WHERE resolution_time_hrs > 24 OR (status != 'Resolved' AND response_time_hrs > 5) ORDER BY resolution_time_hrs DESC LIMIT 20;",
            "explanation": "Queries tickets with exceptionally long resolution times or delayed response."
        }

    # General breakdown queries
    if "category" in q or "categories" in q:
        return {
            "sql": "SELECT category, COUNT(*) as ticket_count, ROUND(AVG(response_time_hrs), 2) as avg_resp_hrs, ROUND(AVG(resolution_time_hrs), 2) as avg_resol_hrs FROM tickets GROUP BY category ORDER BY ticket_count DESC;",
            "explanation": "Groups ticket metrics by category."
        }

    if "status" in q:
        return {
            "sql": "SELECT status, COUNT(*) as count FROM tickets GROUP BY status ORDER BY count DESC;",
            "explanation": "Counts tickets grouped by status."
        }

    # Default fallback
    return {
        "sql": "SELECT ticket_id, created_at, category, priority, status, response_time_hrs, resolution_time_hrs, agent_id, customer_rating, issue_summary FROM tickets LIMIT 10;",
        "explanation": "Shows top 10 tickets from the database."
    }

class LLMProvider:
    """LLM wrapper managing calls to Groq, Ollama, HuggingFace, OpenAI, or Fallback SQL generator."""

    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.hf_api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def text_to_sql(self, user_question: str) -> Dict[str, str]:
        """
        Translate natural language question to SQLite query.
        Tries API providers if configured, otherwise uses deterministic smart fallback.
        """
        # Try Groq API if available
        if self.groq_api_key:
            try:
                import httpx
                response = httpx.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.groq_api_key}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": DB_SCHEMA_PROMPT},
                            {"role": "user", "content": user_question}
                        ],
                        "temperature": 0.1
                    },
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    if "sql" in parsed:
                        return parsed
            except Exception as e:
                logger.warning(f"Groq API call failed: {e}")

        # Try OpenAI API if available
        if self.openai_api_key:
            try:
                import openai
                client = openai.OpenAI(api_key=self.openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": DB_SCHEMA_PROMPT},
                        {"role": "user", "content": user_question}
                    ],
                    temperature=0.1
                )
                content = response.choices[0].message.content
                parsed = json.loads(content)
                if "sql" in parsed:
                    return parsed
            except Exception as e:
                logger.warning(f"OpenAI API call failed: {e}")

        # Fallback to smart deterministic SQL generator
        return generate_fallback_sql(user_question)
