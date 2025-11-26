# Chatbot Service - AI Agent Instructions

## Architecture Overview

**FastAPI microservice** for AI-powered educational features:
1. **Quiz Generation** - Generate MCQ questions from documents using Hybrid RAG (BM25 + Dense + RRF Fusion)
2. **Course Chatbot** - RAG-based course recommendation using pgvector

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUIZ GENERATION FLOW                              │
│  POST /api/v1/quiz/create                                                   │
│                                                                             │
│  Document URL → DataLoader (DOCX/PDF) → PassageBuilder → DataFrame          │
│       ↓                                                                     │
│  RetrieverPipeline ─┬─→ BM25Retriever (rank_bm25)                          │
│                     ├─→ DenseRetriever (OpenAI embeddings + FAISS)          │
│                     └─→ RRFFusion (Reciprocal Rank Fusion, k=60)            │
│       ↓                                                                     │
│  MCQGenerator (Google Gemini) → PydanticOutputParser → Quiz JSON            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Stack**: FastAPI + SQLAlchemy (async) + LangChain + pgvector + FAISS + Eureka

## Project Structure

```
src/
├── api/v1/
│   ├── router.py           # Main router aggregator
│   ├── schemas.py          # Pydantic request/response models
│   └── endpoints/
│       └── quiz.py         # Quiz generation endpoint
├── services/
│   ├── quiz_service.py     # Quiz orchestration (RetrieverPipeline + MCQGenerator)
│   ├── langchain_service.py # LLM interaction wrapper
│   └── prompt_service.py   # Prompt templates
├── retriever/              # Hybrid RAG components
│   ├── passages.py         # PassageBuilder: DataFrame → passage dicts
│   ├── bm25_retrieval.py   # BM25Okapi sparse retriever
│   ├── dense_retrieval.py  # OpenAI embeddings + FAISS dense retriever
│   └── fusion.py           # RRFFusion: combines BM25 + Dense results
├── data/
│   └── dataloader.py       # Document loading (DOCX/PDF → DataFrame)
├── factory/
│   └── LLMFactory.py       # Multi-provider LLM instantiation
├── config.py               # Settings (pydantic-settings)
└── main.py                 # FastAPI app + Eureka lifecycle
```

## Critical Architecture Patterns

### 1. Hybrid RAG Pipeline (Quiz Service)
The quiz feature uses **Hybrid Retrieval** - NOT pgvector:
```python
# src/services/quiz_service.py - RetrieverPipeline
retriever = RetrieverPipeline(passages)  # Takes passage dicts
candidates = retriever.retrieve(prompt)   # Returns top-k texts

# Under the hood:
# 1. BM25Retriever: Keyword-based sparse retrieval (rank_bm25)
# 2. DenseRetriever: Semantic search (OpenAI embeddings → FAISS)
# 3. RRFFusion: Reciprocal Rank Fusion combines both rankings
```

**Key settings** (`config.py`):
```python
top_k: int = 10           # Final results count
rrf_k: int = 60           # RRF smoothing parameter
candidates_n: int = 20    # Candidates per retriever
```

### 2. Multi-LLM Provider Support via Factory
```python
# src/factory/LLMFactory.py
settings.llm_provider = "google"  # or "openai"
llm = LLMFactory.create()  # Returns ChatGoogleGenerativeAI or ChatOpenAI
```
**Current setup**: Google Gemini for generation, OpenAI for embeddings only.

### 3. Document Processing Pipeline
```python
# src/data/dataloader.py
df = load_document_to_dataframe(url)  # Auto-detects DOCX/PDF
# Returns DataFrame: [Chapter, Section, Sub_section, Content]

# src/retriever/passages.py  
passages = PassageBuilder.build_passages_from_records(df)
# Returns: [{"id": 1, "content": "..."}, ...]
```

### 4. Pydantic Output Parsing for LLM
```python
# src/services/quiz_service.py - MCQGenerator
parser = PydanticOutputParser(pydantic_object=QuizOutputInternal)
prompt = f"... {parser.get_format_instructions()}"  # Inject JSON schema
raw_output = llm.invoke(prompt)
parsed: QuizOutputInternal = parser.parse(raw_output)
```

### 5. Async Session Management
```python
# Services are singletons via @lru_cache in dependencies/services.py
# DB sessions are per-request via dependencies/db.py
# Repositories take AsyncSession in __init__ (request-scoped)
```

## API Endpoints

### Quiz Generation
```
POST /api/v1/quiz/create
{
  "prompt": "Tạo 10 câu hỏi về Chương 1",
  "skills": ["phân tích", "lập trình"],
  "document_url": "https://example.com/document.docx"
}
```
Response matches Java entity structure: `Question` with `answers[]`, `question_type` (SINGLE_CHOICE, MULTIPLE_CHOICE, TRUE_FALSE).

## Development Workflows

### Quick Start
```powershell
# 1. Setup PostgreSQL with pgvector
docker run -d --name pgvector -e POSTGRES_PASSWORD=postgres -p 5432:5432 ankane/pgvector

# 2. Configure .env (copy from .env.example)
# Required: google_api_key, openai_api_key

# 3. Run migrations & start server
alembic upgrade head
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing Quiz API
```powershell
# Via curl/Postman
curl -X POST "http://localhost:8000/api/v1/quiz/create" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Tạo 5 câu hỏi","skills":["kiến thức cơ bản"],"document_url":"..."}'
```

## Configuration (`src/config.py`)

| Setting | Description | Default |
|---------|-------------|---------|
| `llm_provider` | "google" or "openai" | google |
| `gemini_model_name` | Gemini model for generation | gemini-2.0-flash |
| `embedding_model` | OpenAI embedding model | text-embedding-3-small |
| `rrf_k` | RRF fusion parameter | 60 |
| `candidates_n` | Candidates per retriever | 20 |

## Key Conventions

1. **Vietnamese prompts**: All LLM prompts and user messages are in Vietnamese
2. **Schema mirroring**: API schemas (`src/api/v1/schemas.py`) mirror Java entity structure for interoperability
3. **Stateless quiz**: Quiz generation doesn't persist to DB - returns JSON directly
4. **Dual retrieval**: BM25 for keywords + Dense for semantics, combined via RRF

## Common Issues

1. **"Unsupported file type"**: Only DOCX and PDF supported. Check document URL accessibility.
2. **Empty candidates**: Document may not chunk properly. Check `dataloader.py` regex patterns.
3. **FAISS index errors**: Dense retriever builds index on first query. Ensure OpenAI API key is set.
4. **Pydantic parsing fails**: LLM output didn't match schema. Check `MCQGenerator` prompt instructions.

## Key Files to Read First

1. `src/services/quiz_service.py` - Full quiz generation pipeline
2. `src/retriever/fusion.py` - RRF algorithm implementation
3. `src/data/dataloader.py` - Document parsing logic
4. `src/api/v1/schemas.py` - API contract definitions
