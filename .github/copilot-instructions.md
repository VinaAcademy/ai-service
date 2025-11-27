# Chatbot Service - AI Agent Instructions

## Architecture Overview

**FastAPI microservice** for AI-powered educational quiz generation using Hybrid RAG (BM25 + Dense + RRF Fusion).

```
POST /api/v1/quiz/create
  Document URL → DataLoader (DOCX/PDF) → PassageBuilder → HybridRetriever → MCQGenerator → Quiz JSON
                                                              ↓
                                            BM25 + Dense(FAISS) + RRFFusion
```

**Stack**: FastAPI + LangChain + FAISS + Eureka | Google Gemini (generation) + OpenAI (embeddings only)

## Critical Patterns

### 1. Hybrid RAG Pipeline (NOT pgvector for quiz)
```python
# src/services/quiz_service.py - HybridRetriever orchestrates:
# 1. BM25Retriever (rank_bm25) - keyword sparse retrieval
# 2. DenseRetriever (OpenAI embeddings → FAISS) - semantic search  
# 3. RRFFusion - combines rankings with Reciprocal Rank Fusion (k=60)

retriever = self._retriever_factory.create(passages)  # Returns HybridRetriever
candidates = retriever.retrieve(prompt)  # Returns top-k passage texts
```

### 2. Dependency Injection via `@lru_cache` Singletons
```python
# src/dependencies/services.py - All services are singletons
@lru_cache()
def get_quiz_service() -> QuizService:
    return QuizService(
        retriever_factory=get_retriever_factory(),
        mcq_generator=get_mcq_generator()
    )

# Usage in endpoints via FastAPI Depends()
quiz_service: QuizService = Depends(get_quiz_service)
```

### 3. LLM Output Parsing with Fallback Strategies
```python
# src/services/quiz_service.py - MCQGenerator._parse_with_fallback()
# Handles: direct parse → markdown code block extraction → JSON regex → cleaned parse
parser = PydanticOutputParser(pydantic_object=QuizOutputInternal)
```

### 4. Dual Schema Design
- **Internal** (`src/schemas/external/quiz_llm.py`): `QuizOutputInternal` for LLM parsing (Vietnamese field descriptions)
- **API** (`src/schemas/quiz.py`): `CreateQuizResponse` mirrors Java entity structure for interoperability

### 5. Document Chunking Pattern
```python
# src/data/dataloader.py - Regex-based chapter/section detection for DOCX
# Vietnamese: "CHƯƠNG" prefix, numbered sections (1.1., 1.1.1.)
# Returns DataFrame: [Chapter, Section, Sub_section, Content]
```

## Development Commands

```powershell
# Start server (requires .env with google_api_key, openai_api_key)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Database migrations
alembic upgrade head

# PostgreSQL with pgvector (for future chatbot features)
docker run -d --name pgvector -e POSTGRES_PASSWORD=postgres -p 5432:5432 ankane/pgvector
```

## Key Configuration (`src/config.py`)

| Setting | Purpose | Default |
|---------|---------|---------|
| `llm_provider` | "google" or "openai" | google |
| `gemini_model_name` | Generation model | gemini-2.0-flash |
| `rrf_k` | RRF smoothing (higher = more weight to top ranks) | 60 |
| `candidates_n` | Passages retrieved per retriever | 20 |

## Project Conventions

1. **Vietnamese everywhere**: Prompts, LLM instructions, field descriptions in `src/services/prompt_service.py`
2. **Stateless quiz**: No DB persistence - returns JSON directly to caller
3. **Factory pattern**: `LLMFactory.create()` supports provider switching without code changes
4. **Eureka registration**: Auto-registers on startup via `src/clients/eureka_client.py`

## Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| `Unsupported file type` | Non-DOCX/PDF or inaccessible URL | Check `dataloader.py` byte signature detection |
| Empty retrieval results | Document not chunking properly | Debug regex patterns in `dataloader.py` |
| Pydantic parsing fails | LLM output malformed | Check `MCQGenerator._parse_with_fallback()` strategies |
| Truncated LLM response | Too many questions requested | Reduce count or increase `QUIZ_MAX_TOKENS` (4096) |

## Key Files

- `src/services/quiz_service.py` - Full pipeline: `QuizService`, `HybridRetriever`, `MCQGenerator`
- `src/retriever/fusion.py` - RRF algorithm (20 lines, easy to understand)
- `src/dependencies/services.py` - DI wiring for all services
- `src/schemas/external/quiz_llm.py` - LLM output schema with Vietnamese descriptions
