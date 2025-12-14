# Chatbot Service - AI Agent Instructions

## Architecture Overview

**FastAPI microservice** with TWO AI-powered features in a Spring Cloud microservices ecosystem:

1. **Conversational Chatbot** (LangGraph Agents + Tools) - Context-aware Vietnamese educational assistant
2. **Quiz Generation** (Hybrid RAG) - BM25 + Dense retrieval + RRF Fusion for MCQ creation

```
┌─ Chatbot Flow ─────────────────────────────────────────────┐
│ POST /api/v1/chatbot/chat/stream (SSE)                     │
│   → LangGraph Agent → Tools (search_courses, get_lesson)   │
│       ├─ Tool 1: Eureka→VECTOR-SEARCH-SERVICE (semantic)   │
│       └─ Tool 2: DB→LessonRepo (course context)            │
└─────────────────────────────────────────────────────────────┘

┌─ Quiz Generation Flow ──────────────────────────────────────┐
│ POST /api/v1/quiz/create (Async + Redis Lock)              │
│   → Redis Lock → Background Task → QuizService             │
│       → HybridRetriever (BM25 + Dense→FAISS + RRF k=60)    │
│       → MCQGenerator (Gemini) → DB Save → Progress Updates │
└─────────────────────────────────────────────────────────────┘
```

**Stack**: FastAPI + LangChain + LangGraph + SQLAlchemy (AsyncPG) + FAISS + Redis + Eureka  
**LLM**: Google Gemini (generation, 4096 tokens) + OpenAI (embeddings only, text-embedding-3-small)

## Critical Patterns

### 1. LangGraph Agent Architecture with Custom Tools (Chatbot Feature)

```python
# src/services/chatbot_service.py - ChatbotService uses LangGraph create_agent()
# Tools are defined as closures in AgentToolsService.create_langchain_tools()

@tool
async def search_courses(query: str) -> str:
  """Semantic search via Eureka service discovery"""
  # Discovers VECTOR-SEARCH-SERVICE, calls /api/v1/courses/aisearch


@tool
async def get_lesson_context(lesson_id: str, runtime: ToolRuntime) -> str:
  """Fetches course/section/lesson metadata from DB"""
  # Uses runtime.context to access ChatContext (user_id, lesson_id, course_id)


# Agent streams responses with tool activity visibility:
async for token, metadata in agent.astream(input, stream_mode="messages"):
  if metadata['langgraph_node'] == 'tools':
    yield {"type": "tool_call", "text": "Đang tìm kiếm..."}
  else:
    yield {"type": "text", "text": block['text']}
```

**Key Points:**

- Tools use **async closures** capturing `self` (AgentToolsService instance) for DB access
- **PostgresSaver checkpointer** (disabled in current code) for conversation persistence
- **ChatContext** tracks user navigation state (lesson_id, course_id) passed via `runtime.context`
- **Eureka integration**: `py_eureka_client.do_service_async()` for dynamic service discovery
- **SSE streaming**: `/chatbot/chat/stream` endpoint uses `StreamingResponse` with `text/event-stream`

### 2. Hybrid RAG Pipeline (Quiz Feature - In-Memory FAISS, NOT pgvector)
```python
# src/services/quiz_service.py - HybridRetriever orchestrates:
# 1. BM25Retriever (rank_bm25) - keyword sparse retrieval
# 2. DenseRetriever (OpenAI embeddings → FAISS in-memory) - semantic search  
# 3. RRFFusion - Reciprocal Rank Fusion: score = Σ(1/(k + rank + 1)), k=60

retriever = self._retriever_factory.create(passages)  # Returns HybridRetriever
candidates = retriever.retrieve(query, top_k=20)  # Returns list of passage texts
```

### 3. Two-Level Dependency Injection (Singleton + Per-Request)
```python
# src/dependencies/services.py - Singletons cached with @lru_cache()
@lru_cache()  # Cached: RetrieverFactory, MCQGenerator
def get_retriever_factory() -> RetrieverFactory: ...


# Singleton with manual connection: RedisClient (global _redis_client_instance)
async def get_redis_client() -> RedisClient:
  global _redis_client_instance
  if _redis_client_instance is None:
    _redis_client_instance = RedisClient(settings)
    await _redis_client_instance.connect()
  return _redis_client_instance


# Per-request: QuizService, ChatbotService (requires database session)
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

### 4. Redis-Based Async Task Pattern with Distributed Locking

```python
# src/api/v1/endpoints/quiz_controller.py - Synchronous validation BEFORE background task
async def create_quiz_async(...):
  # 1. Validate request synchronously (prompt, permissions, quiz existence)
  await quiz_service.validate_quiz_request(prompt, quiz_id, user_id)

  # 2. Acquire Redis lock (non-blocking, fail fast if already locked)
  async with redis_client.acquire_quiz_lock(str(request.quiz_id)):
    # 3. Queue background task
    background_tasks.add_task(
      task_service.generate_quiz_async,
      quiz_service, request.prompt, request.quiz_id, user_id
    )

  # 4. Return immediately with polling endpoint
  return {"quiz_id": quiz_id, "status": "PENDING"}


# Client polls GET /quiz/progress/{quiz_id} for status updates
# src/clients/redis_client.py - Progress stored with 24h TTL
await redis_client.set_progress(quiz_id, status="PROCESSING", progress=40, ...)
```

**Critical**: Validation happens BEFORE background task to fail fast. Task only handles generation + progress updates.

### 5. LLM Output Parsing with 4-Strategy Fallback
```python
# src/services/quiz_service.py - MCQGenerator._parse_with_fallback()
# Strategy 1: Direct Pydantic parse
# Strategy 2: Extract from ```json...``` markdown block
# Strategy 3: Regex search for JSON object {.*}
# Strategy 4: Clean leading/trailing non-JSON (remove backticks)
# + Truncation detection: Check for unbalanced braces/brackets

parser = PydanticOutputParser(pydantic_object=QuizOutputInternal)
```

### 6. Dual Schema Design for Java Microservice Interoperability

- **Internal** (`src/schemas/external/quiz_llm.py`): `QuizOutputInternal` with Vietnamese field descriptions for LLM
  prompt
    - Uses Pydantic Field() descriptions to guide LLM output format
- **API** (`src/schemas/quiz.py`): `Question` + `Answer` schemas mirror Java entity structure
    - Ensures JSON response matches Java service expectations

### 7. Document Chunking with Vietnamese Regex Patterns
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
| `embedding_model`   | OpenAI embedding model   | text-embedding-3-small   | Used for dense retrieval only                   |
| `rrf_k`             | RRF smoothing parameter  | 60                       | Higher = more weight to top-ranked results      |
| `candidates_n`      | Passages per retriever   | 20                       | Total candidates = 20 (fused from 2 retrievers) |
| `QUIZ_MAX_TOKENS`   | MCQGenerator token limit | 4096                     | ~10-15 questions max per request                |
| `database_url`      | Async PostgreSQL URL     | postgresql+asyncpg://... | AsyncPG driver required                         |
| `eureka_server_url` | Eureka registry          | http://localhost:8761... | For service discovery                           |
| `redis_url`         | Redis connection         | redis://localhost:6379/0 | For distributed locking + progress tracking     |

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
7. **JWT Auth Without Verification**: `AuthService.get_current_user()` decodes JWT tokens without signature
   verification (trusts API Gateway)
8. **Tool Closures**: LangChain `@tool` decorated functions use closures to capture service instances (avoid pickling
   issues)

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

| Issue                            | Cause                                        | Fix                                                                                     |
|----------------------------------|----------------------------------------------|-----------------------------------------------------------------------------------------|
| `Unsupported file type`          | Non-DOCX/PDF or inaccessible URL             | Check `dataloader.py` byte signature (PK for DOCX, %PDF- for PDF)                       |
| Empty retrieval results          | Document not chunking properly               | Debug regex patterns in `dataloader.py` (Vietnamese "CHƯƠNG" detection)                 |
| Pydantic parsing fails           | LLM output malformed                         | Check `MCQGenerator._parse_with_fallback()` 4-strategy logic + raw output in logs       |
| Truncated LLM response           | Too many questions requested                 | Reduce count (5-10 max) or increase `MCQGenerator.QUIZ_MAX_TOKENS` (default 4096)       |
| DB session errors                | Using singleton for DB-dependent service     | `QuizService` is per-request (not @lru_cache), but factories/generators are singletons  |
| Agent tool not accessible        | Tool closure not capturing service instance  | Tools defined in `create_langchain_tools()` must use `service = self` closure pattern   |
| SSE stream not working           | Missing `text/event-stream` media type       | Use `StreamingResponse(event_stream(), media_type="text/event-stream")`                 |
| Redis lock timeout               | Quiz generation exceeds 1 hour               | Increase `RedisClient.LOCK_TTL` or optimize generation                                  |
| Eureka service discovery failure | Service not registered or wrong `app_name`   | Check `eureka_client.do_service_async(app_name="VECTOR-SEARCH-SERVICE")`                |
| JWT decode error                 | Missing "userId" field in token              | Verify token structure from API Gateway (expects `{"userId": "..."}`)                   |
| Background task validation error | Validation logic in task instead of endpoint | Move validation to endpoint BEFORE `background_tasks.add_task()` for immediate feedback |
| PostgresSaver checkpointer error | Connection pool issues with sync DB          | Currently disabled (commented out in `ChatbotService._create_agent()`)                  |

## Key Files Reference

| File                                         | Purpose                                                            | Lines |
|----------------------------------------------|--------------------------------------------------------------------|-------|
| `src/services/chatbot_service.py`            | LangGraph agent orchestration, SSE streaming, ChatContext tracking | 145   |
| `src/services/agent_tools_service.py`        | LangChain tool definitions (search_courses, get_lesson_context)    | 252   |
| `src/services/quiz_service.py`               | Core logic: `QuizService`, `HybridRetriever`, `MCQGenerator`       | 325   |
| `src/services/task_service.py`               | Background quiz generation with progress tracking                  | 186   |
| `src/clients/redis_client.py`                | Distributed locking + progress updates (24h TTL)                   | 218   |
| `src/clients/eureka_client.py`               | Microservice registration/deregistration                           | 30    |
| `src/api/v1/endpoints/chatbot_controller.py` | SSE chat endpoint (`/chatbot/chat/stream`)                         | 137   |
| `src/api/v1/endpoints/quiz_controller.py`    | Async quiz endpoint with Redis locking                             | 226   |
| `src/dependencies/services.py`               | DI wiring (singleton vs per-request pattern)                       | 142   |
| `src/retriever/fusion.py`                    | RRF algorithm (simple, readable)                                   | 20    |
| `src/schemas/external/quiz_llm.py`           | LLM output schema (Vietnamese descriptions)                        | 40    |
| `src/services/prompt_service.py`             | Vietnamese prompt templates                                        | 111   |
| `src/services/auth_service.py`               | JWT decoding without verification (API Gateway trust)              | 35    |
| `src/data/dataloader.py`                     | DOCX/PDF chunking with Vietnamese regex                            | 90    |
| `src/factory/LLMFactory.py`                  | Provider-agnostic LLM creation                                     | 52    |
| `src/model/quiz_models.py`                   | SQLAlchemy models (Quiz, Question, Answer)                         | 134   |
| `src/utils/exception_handlers.py`            | Global exception → ApiResponse mapping                             | 109   |
