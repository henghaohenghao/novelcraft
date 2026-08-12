# NovelCraft Test Suite

Comprehensive test suite for NovelCraft backend APIs and frontend integration.

## Test Structure

```
tests/
├── conftest.py                      # Pytest configuration and fixtures
├── test_projects_api.py             # Projects CRUD tests
├── test_outlines_api.py             # Outlines and AI generation tests
├── test_characters_api.py           # Characters, relationships, factions, locations, events tests
├── test_writing_api.py              # Chapters and writing workflow tests
├── test_health_api.py               # Health check and system tests
└── test_frontend_integration.py    # Frontend workflow integration tests
```

## Prerequisites

Install test dependencies:

```bash
pip install pytest pytest-asyncio httpx
```

## Running Tests

### Run all tests
```bash
# From project root
pytest tests/ -v

# Or with coverage
pytest tests/ -v --cov=backend --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_projects_api.py -v
pytest tests/test_characters_api.py -v
```

### Run specific test class
```bash
pytest tests/test_projects_api.py::TestProjectsAPI -v
```

### Run specific test method
```bash
pytest tests/test_projects_api.py::TestProjectsAPI::test_create_project -v
```

### Run with output
```bash
pytest tests/ -v -s  # -s shows print statements
```

## Test Coverage

### Backend API Endpoints

#### Projects API (`/api/projects`)
- ✅ POST /api/projects - Create project
- ✅ GET /api/projects - List projects
- ✅ GET /api/projects/{id} - Get project details
- ✅ PUT /api/projects/{id} - Update project
- ✅ DELETE /api/projects/{id} - Delete project

#### Outlines API (`/api/outlines`)
- ✅ POST /api/outlines - Create outline node
- ✅ GET /api/outlines/project/{id} - Get flat outline list
- ✅ GET /api/outlines/project/{id}/tree - Get tree structure
- ✅ POST /api/outlines/generate - AI generate outline
- ✅ GET /api/outlines/{id} - Get outline details
- ✅ PUT /api/outlines/{id} - Update outline
- ✅ DELETE /api/outlines/{id} - Delete outline

#### Characters API (`/api/characters`)
- ✅ POST /api/characters - Create character
- ✅ GET /api/characters/project/{id} - List characters
- ✅ GET /api/characters/{id} - Get character details
- ✅ PUT /api/characters/{id} - Update character
- ✅ DELETE /api/characters/{id} - Delete character
- ✅ POST /api/characters/relationships - Create relationship
- ✅ GET /api/characters/{id}/relations - Get character relations
- ✅ DELETE /api/characters/relationships - Delete relationship
- ✅ GET /api/characters/project/{id}/graph - Get project graph
- ✅ POST /api/characters/generate-from-synopsis - AI generate characters
- ✅ POST /api/characters/factions - Create faction
- ✅ GET /api/characters/factions/project/{id} - List factions
- ✅ POST /api/characters/locations - Create location
- ✅ GET /api/characters/locations/project/{id} - List locations
- ✅ POST /api/characters/events - Create event
- ✅ GET /api/characters/events/project/{id} - List events

#### Writing API (`/api/writing`)
- ✅ POST /api/writing/chapters - Create chapter
- ✅ GET /api/writing/chapters/project/{id} - List chapters
- ✅ GET /api/writing/chapters/{id} - Get chapter details
- ✅ PUT /api/writing/chapters/{id} - Update chapter
- ✅ DELETE /api/writing/chapters/{id} - Delete chapter
- ✅ POST /api/writing/chapters/generate - Stream generate chapter (SSE)
- ✅ POST /api/writing/chapters/generate-sync - Sync generate chapter

#### Health API
- ✅ GET /api/health - Health check

### Frontend Integration Tests
- ✅ Complete project workflow (create → outline → characters → chapter)
- ✅ Project list page workflow
- ✅ Project detail page with all tabs
- ✅ Outline creation from UI
- ✅ Chapter creation and generation workflow
- ✅ Character management workflow
- ✅ Multi-project data isolation
- ✅ Error handling scenarios

## Test Features

### Database Isolation
- Each test uses an in-memory SQLite database
- Database is created fresh for each test function
- No test pollution between runs

### Async Support
- All tests use `pytest-asyncio` for async/await support
- Tests use `AsyncClient` for HTTP requests

### Fixtures
- `client`: Test HTTP client with database override
- `sample_project_data`: Sample project data
- `sample_outline_data`: Sample outline data
- `sample_character_data`: Sample character data
- `sample_chapter_data`: Sample chapter data

### LLM-Dependent Tests
Some tests involve AI generation endpoints that require LLM configuration:
- Outline generation
- Character generation from synopsis
- Chapter generation (sync and stream)

These tests are designed to accept both success (200) and failure (500) status codes, since they depend on external LLM services.

## Test Configuration

Tests use in-memory SQLite database by default. To test with PostgreSQL:

1. Set up test database:
```sql
CREATE DATABASE novelcraft_test;
```

2. Modify `conftest.py`:
```python
TEST_DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/novelcraft_test"
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx pytest-cov
      - name: Run tests
        run: pytest tests/ -v --cov=backend --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Notes

### Neo4j Tests
Tests involving Neo4j (relationships, graph) will gracefully handle Neo4j being unavailable:
- Tests accept both 200 (success) and 500 (service unavailable) status codes
- Graph endpoints return empty nodes/edges when Neo4j is down

### Qdrant Tests
Vector search functionality is not directly tested, but the system gracefully degrades when Qdrant is unavailable.

### SSE Streaming Tests
The streaming chapter generation endpoint (`/api/writing/chapters/generate`) uses Server-Sent Events (SSE). Full SSE testing requires special handling and is simplified in these tests.

## Troubleshooting

### Import Errors
If you get import errors, ensure `PYTHONPATH` includes the project root:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/ -v
```

### Database Errors
If you get database errors, ensure SQLAlchemy and aiosqlite are installed:
```bash
pip install sqlalchemy aiosqlite
```

### Async Errors
If you get async-related errors, ensure pytest-asyncio is installed:
```bash
pip install pytest-asyncio
```

## Future Enhancements

- [ ] Add performance tests
- [ ] Add load tests for concurrent requests
- [ ] Add full SSE streaming tests
- [ ] Add frontend E2E tests with Playwright
- [ ] Add API contract tests
- [ ] Add security tests (SQL injection, XSS, etc.)
- [ ] Add mutation testing
- [ ] Add snapshot testing for API responses
