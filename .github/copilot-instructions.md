# Chatbot Service - AI Agent Instructions

## Architecture Overview

**FastAPI microservice** for AI-powered educational quiz generation using Hybrid RAG (BM25 + Dense + RRF Fusion).

```
POST /api/v1/quiz/create
  quiz_id → QuizRepo → Course Context → HybridRetriever → MCQGenerator → DB Save → Questions JSON
                            ↓
          BM25 (sparse) + Dense(OpenAI→FAISS) + RRFFusion(k=60)
```

**Stack**: FastAPI + LangChain + SQLAlchemy (AsyncPG) + FAISS + Eureka  
**LLM**: Google Gemini (generation, 4096 tokens) + OpenAI (embeddings only, text-embedding-3-small)

## Critical Patterns

### 1. Hybrid RAG Pipeline (In-Memory FAISS, NOT pgvector)
```python
# src/services/quiz_service.py - HybridRetriever orchestrates:
# 1. BM25Retriever (rank_bm25) - keyword sparse retrieval
# 2. DenseRetriever (OpenAI embeddings → FAISS in-memory) - semantic search  
# 3. RRFFusion - Reciprocal Rank Fusion: score = Σ(1/(k + rank + 1)), k=60

retriever = self._retriever_factory.create(passages)  # Returns HybridRetriever
candidates = retriever.retrieve(query, top_k=20)  # Returns list of passage texts
```

### 2. Two-Level Dependency Injection (Singleton + Per-Request)
```python
# src/dependencies/services.py - Singletons cached with @lru_cache()
@lru_cache()  # Cached: RetrieverFactory, MCQGenerator
def get_retriever_factory() -> RetrieverFactory: ...


# Per-request: QuizService (requires database session)
async def get_quiz_service(
        quiz_repository: QuizRepository = Depends(get_quiz_repository),  # Per-request
        lesson_repository: LessonRepository = Depends(get_lesson_repository)  # Per-request
) -> QuizService:
    return QuizService(
        retriever_factory=get_retriever_factory(),  # Singleton
        mcq_generator=get_mcq_generator(),  # Singleton
        quiz_repository=quiz_repository,
        lesson_repository=lesson_repository
    )
```

### 3. LLM Output Parsing with 4-Strategy Fallback
```python
# src/services/quiz_service.py - MCQGenerator._parse_with_fallback()
# Strategy 1: Direct Pydantic parse
# Strategy 2: Extract from ```json...``` markdown block
# Strategy 3: Regex search for JSON object {.*}
# Strategy 4: Clean leading/trailing non-JSON (remove backticks)
# + Truncation detection: Check for unbalanced braces/brackets

parser = PydanticOutputParser(pydantic_object=QuizOutputInternal)
```

### 4. Dual Schema Design for Java Microservice Interoperability

- **Internal** (`src/schemas/external/quiz_llm.py`): `QuizOutputInternal` with Vietnamese field descriptions for LLM
  prompt
    - Uses Pydantic Field() descriptions to guide LLM output format
- **API** (`src/schemas/quiz.py`): `Question` + `Answer` schemas mirror Java entity structure
    - Ensures JSON response matches Java service expectations

### 5. Document Chunking with Vietnamese Regex Patterns
```python
# src/data/dataloader.py - Chapter/Section detection
# Pattern 1: "CHƯƠNG" prefix (line.upper().startswith("CHƯƠNG"))
# Pattern 2: Numbered sections (regex r"^\d+(\.\d+)*\.")
#   - Level ≤2: Section (1.1., 2.3.)
#   - Level >2: Subsection (1.1.1., 2.3.4.)
# Returns: DataFrame[Chapter, Section, Sub_section, Content]
```

## Development Commands

```powershell
# Start server (requires .env with google_api_key, openai_api_key)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Database migrations (Alembic)
alembic revision --autogenerate -m "description"
alembic upgrade head

# PostgreSQL with pgvector (used for vector storage, NOT for quiz retrieval)
docker run -d --name pgvector -e POSTGRES_PASSWORD=postgres -p 5432:5432 ankane/pgvector
```

## Key Configuration (`src/config.py` + `.env`)

| Setting             | Purpose                  | Default                  | Notes                                           |
|---------------------|--------------------------|--------------------------|-------------------------------------------------|
| `llm_provider`      | "google" or "openai"     | google                   | Switch via `LLMFactory.create()`                |
| `gemini_model_name` | Generation model         | gemini-2.0-flash         | Fast, Vietnamese-capable                        |
| `rrf_k`             | RRF smoothing parameter  | 60                       | Higher = more weight to top-ranked results      |
| `candidates_n`      | Passages per retriever   | 20                       | Total candidates = 20 (fused from 2 retrievers) |
| `QUIZ_MAX_TOKENS`   | MCQGenerator token limit | 4096                     | ~10-15 questions max per request                |
| `database_url`      | Async PostgreSQL URL     | postgresql+asyncpg://... | AsyncPG driver required                         |

## Project Conventions

1. **Vietnamese-First**: All prompts, LLM instructions, field descriptions in `src/services/prompt_service.py` are
   Vietnamese
2. **Database Persistence**: Questions ARE saved to DB (`quiz_repository.add_questions_to_quiz()` in
   `QuizService.generate_quiz()`)
3. **Factory Pattern**: `LLMFactory.create()` supports provider switching (google/openai) without code changes
4. **Eureka Registration**: Auto-registers as microservice on startup (`src/clients/eureka_client.py` → lifespan events)
5. **Exception Hierarchy**: Custom exceptions (`src/utils/exceptions.py`) mapped via `register_exception_handlers()` in
   `main.py`
6. **Async All The Way**: SQLAlchemy AsyncSession, FastAPI async endpoints, async DB operations

## Data Flow for Quiz Generation

```python
# src/services/quiz_service.py - QuizService.generate_quiz()
1.
quiz_repository.get_quiz_by_id(quiz_id) → Fetch
Quiz
entity(extends
Lesson)
2.
lesson_repository.get_lessons_with_course_context(section_id) → Course / Section / Lessons
metadata
3.
PromptService.build_course_context() → Format
context
string(Vietnamese)
4.
mcq_generator.generate(context, query) → LLM
call(Gemini)
5.
quiz_repository.add_questions_to_quiz() → Save
to
DB
6.
Return
questions_data(list
of
dicts)
```

## Common Pitfalls

| Issue                   | Cause                                    | Fix                                                                                    |
|-------------------------|------------------------------------------|----------------------------------------------------------------------------------------|
| `Unsupported file type` | Non-DOCX/PDF or inaccessible URL         | Check `dataloader.py` byte signature (PK for DOCX, %PDF- for PDF)                      |
| Empty retrieval results | Document not chunking properly           | Debug regex patterns in `dataloader.py` (Vietnamese "CHƯƠNG" detection)                |
| Pydantic parsing fails  | LLM output malformed                     | Check `MCQGenerator._parse_with_fallback()` 4-strategy logic + raw output in logs      |
| Truncated LLM response  | Too many questions requested             | Reduce count (5-10 max) or increase `MCQGenerator.QUIZ_MAX_TOKENS` (default 4096)      |
| DB session errors       | Using singleton for DB-dependent service | `QuizService` is per-request (not @lru_cache), but factories/generators are singletons |

## Key Files Reference

| File                               | Purpose                                                      | Lines |
|------------------------------------|--------------------------------------------------------------|-------|
| `src/services/quiz_service.py`     | Core logic: `QuizService`, `HybridRetriever`, `MCQGenerator` | 325   |
| `src/retriever/fusion.py`          | RRF algorithm (simple, readable)                             | 20    |
| `src/dependencies/services.py`     | DI wiring (singleton vs per-request pattern)                 | 104   |
| `src/schemas/external/quiz_llm.py` | LLM output schema (Vietnamese descriptions)                  | 40    |
| `src/services/prompt_service.py`   | Vietnamese prompt templates                                  | 111   |
| `src/data/dataloader.py`           | DOCX/PDF chunking with Vietnamese regex                      | 90    |
| `src/factory/LLMFactory.py`        | Provider-agnostic LLM creation                               | 52    |
| `src/model/quiz_models.py`         | SQLAlchemy models (Quiz, Question, Answer)                   | 134   |
