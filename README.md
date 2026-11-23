# grounded-enterprise-assistant

An enterprise AI assistant that answers business questions over **structured data** (natural language → SQL) and **policy documents** (RAG). Every answer is **grounded**: it shows the evidence it came from and is checked before it reaches the user.

> Status: **Phase 1 – secure data layer.** Built step by step; see the roadmap below.

## Why

In an enterprise, a wrong or leaked answer is worse than no answer. So the hard part is not calling a model: it's making sure the model only reads what the user is allowed to see, can never change data, and can prove where each number came from.

## What works today

- **Guarded SQL execution** (`sql/guard.py`): any SQL, including SQL written by an LLM, runs through four layers:
  1. read-only database connection
  2. a single statement only
  3. an authorizer that approves every operation: only `SELECT` and reads of allowed tables
  4. row-level security through views (a regional manager sees only their region, whatever the SQL says)
- **Role policies** (`sql/policies.py`): table-level and row-level access per role.
- **Evidence** for every result: the SQL that ran, the tables and columns it read, row count, truncation.
- **Audit log** (`audit.py`): JSON Lines record of every request, including rejected ones and the reason.
- **21 tests**, including injection and bypass attempts (`DROP`, `PRAGMA`, `ATTACH`, `SELECT 1; DELETE ...`, `FROM main.sales`, CTE tricks).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m grounded_assistant.data.seed               # creates data/demo.db
pytest -v
```

## Azure mapping

The project runs fully locally so anyone can try it. Each local piece has a direct Azure counterpart:

| Here | Azure / enterprise equivalent |
| --- | --- |
| SQLite demo database | Databricks SQL warehouse over ADLS Gen2 (Delta tables) |
| `policies.py` roles + row filters | Unity Catalog grants and row filters, Entra ID groups |
| Local LLM (Ollama) | Azure OpenAI / Azure AI Foundry model deployment |
| Document index (phase 3) | Azure AI Search |
| `audit.jsonl` | Azure Monitor / Log Analytics |
| Evaluation suite (phase 4) | Azure AI Foundry evaluations |

## Roadmap

- [x] Phase 1 – Secure data layer: guarded SQL, roles, row-level security, evidence, audit log
- [ ] Phase 2 – Natural language → SQL with an LLM, structured output, answer validated against the query result
- [ ] Phase 3 – Policy documents with RAG and citations (evidence binding for every claim)
- [ ] Phase 4 – Agent orchestration (LangGraph): route between data and documents, retry, refuse when unsupported
- [ ] Phase 5 – Benchmark set and LLM evaluation, responsible-AI checks
- [ ] Phase 6 – FastAPI, Docker, CI, monitoring; optional Azure deployment

## License

This project is licensed for non-commercial use only.  
See the LICENSE file for details.
