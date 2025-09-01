# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Setup
```bash
# Setup virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# For E2E tests - install Playwright browsers
python -m playwright install
```

### Running the Application
```bash
# Start main application (default port 5001)
python app.py

# Clear and reset database
python clear_db.py
```

### Testing Commands

#### Quick Development Tests (Fast, Core Logic)
```bash
# Run core logic tests - always work, no browser needed
python -m pytest tests/test_optimized_integration.py tests/test_essential_mocks.py tests/test_direct_functions.py -v

# Single test for quick feedback
python -m pytest tests/test_direct_functions.py::test_session_and_feed_workflow -v

# Test feed ingestion (Reddit, RSS autodiscovery, parsing)
python -m pytest tests/test_feed_ingestion.py -v
```

#### UI Flow Tests (Require Running Server)
```bash
# Start server first in separate terminal: python app.py
# Then run UI tests targeting specific bugs we debugged
python -m pytest tests/test_critical_ui_flows.py::TestFormParameterBugFlow -v
python -m pytest tests/test_critical_ui_flows.py::TestBBCRedirectHandlingFlow -v
python -m pytest tests/test_critical_ui_flows.py::TestBlueIndicatorHTMXFlow -v

# Test add feed flows (mobile + desktop)
python -m pytest tests/test_add_feed_flows.py -v

# Test mobile-specific flows (navigation, forms, scrolling, URL sharing)
python -m pytest tests/test_mobile_flows.py -v
```

#### Test Coverage
```bash
# Run with coverage reporting
coverage run --source=. -m pytest tests/test_optimized_integration.py tests/test_essential_mocks.py -v
coverage report --show-missing

# Full test suite coverage
coverage run --source=. -m pytest tests/ -v
coverage report --show-missing
```

### Database Management
```bash
# Reset database completely
python clear_db.py

# Manual database inspection
sqlite3 data/rss.db
.tables
SELECT * FROM feeds;
SELECT COUNT(*) FROM feed_items;
```

## Framework Documentation

### FastHTML and MonsterUI LLM Context Files
The following framework documentation files are included in this project for reference:
- **`fasthtml-llm.txt`**: Complete FastHTML framework documentation and API reference
- **`monsterui-llm.txt`**: MonsterUI component library documentation and examples

These files provide comprehensive information about the frameworks used in this application.

## Architecture

### High-Level Structure
- **FastHTML + MonsterUI**: Python-first web framework with styled components
- **Session-Based Users**: No authentication - each browser gets unique session
- **Background Worker System**: Async feed updates with domain rate limiting
- **SQLite Database**: Normalized schema with feeds shared across users
- **HTMX Frontend**: Server-side rendering with selective UI updates

### Core Components

#### Application Entry (`app.py`)
- Main FastHTML application with middleware for timing and session management
- Three-panel email-like UI: feeds sidebar, post list, detail view
- Routes for feed management, item interaction, and API endpoints
- Integrates background worker for async feed updates

#### Database Layer (`models.py`)
- SQLite schema: `feeds` (global), `feed_items`, `sessions`, `user_feeds`, `folders`, `user_items`
- Context managers for database operations
- Optimized for read-heavy RSS workloads with strategic indexes

#### Feed Processing (`feed_parser.py`)
- RSS/Atom parsing with `feedparser` library
- HTTP caching using ETags and Last-Modified headers
- Content extraction with `trafilatura` for full article text
- Handles redirects, malformed feeds, and various date formats

#### Background Worker (`background_worker.py`)
- Async feed updates with domain-based rate limiting
- Queue-based processing to avoid blocking main application
- Automatic setup of default feeds (Hacker News, Reddit, WSJ)
- Configurable update intervals and retry logic

### Key Design Patterns

#### Session Management
- UUID-based sessions stored in cookies
- Automatic subscription to default feeds for new sessions
- Per-user state (read/unread, starred, folders) without authentication

#### HTMX Integration
- Partial page updates for dynamic interactions
- Form handling with FastHTML parameter mapping
- Real-time UI updates without JavaScript

#### Feed Updates
- Background processing prevents UI blocking
- HTTP caching reduces bandwidth and respects server policies
- Domain rate limiting prevents overwhelming RSS sources

## Testing Strategy

### Philosophy
Tests focus on **complex workflows that broke during development**, not trivial framework functionality.

### Test Categories

#### Critical UI Flow Tests (`tests/test_critical_ui_flows.py`) 
**Comprehensive Playwright automation** targeting exact bugs we debugged:
- Form parameter mapping issues
- BBC redirect handling (302 → `follow_redirects=True`)
- Blue indicator HTMX updates (click article → dot disappears)
- Unread view behavior (click article → item disappears from list)
- Session auto-subscription flow
- Full viewport height utilization
- **Updated selectors** to match current app.py implementation

#### Consolidated Feature Tests
- **`tests/test_add_feed_flows.py`** - Mobile + desktop add feed functionality, duplicate handling
- **`tests/test_mobile_flows.py`** - Navigation, form persistence, scrolling, URL sharing
- **`tests/test_feed_ingestion.py`** - Reddit special cases, RSS autodiscovery, format parsing

#### HTTP Integration Tests (`tests/test_optimized_integration.py`)
**Black-box server testing**:
- Fresh start workflow (empty DB → feed setup → session creation)
- API endpoint verification with proper HTTP semantics
- Session persistence across requests
- Form processing and response validation

#### Essential Mock Tests (`tests/test_essential_mocks.py`)
**Dangerous scenarios** other tests cannot safely cover:
- Network error simulation (timeouts, HTTP errors)
- Database constraint violations
- Malformed RSS/XML handling
- Transaction rollback scenarios

### Development Workflow

#### Before Making Changes
```bash
# Run quick core logic tests
python -m pytest tests/test_optimized_integration.py tests/test_essential_mocks.py tests/test_direct_functions.py -v
```

#### After Major Changes
```bash
# Full coverage verification
coverage run --source=. -m pytest tests/test_optimized_integration.py tests/test_essential_mocks.py -v
coverage report --show-missing
```

#### UI Feature Development
```bash
# Start server: python app.py
# Test specific UI flows
python -m pytest tests/test_critical_ui_flows.py -v
```

## Database Schema

### Global Shared Data
- `feeds`: RSS source metadata with HTTP caching headers
- `feed_items`: Parsed articles linked to feeds via foreign key

### Session-Specific Data
- `sessions`: Browser session tracking
- `user_feeds`: Per-session feed subscriptions
- `user_items`: Read/unread status, starring, folder assignments
- `folders`: User-created organization categories

## Docker and Deployment

### Local Docker
```bash
# Build and run with Docker
docker build -t rss-reader .
docker run -p 8080:8080 -v ./data:/data rss-reader
```

### Fly.io Deployment
```bash
# Deploy to Fly.io
fly deploy
```

## Worktree Development

The project supports parallel development with isolated environments:

```bash
# Create feature branch with isolated database
./create-worktree.sh feature-name

# Create with copied data for testing
./create-worktree.sh feature-name --copy-db

# List and manage worktrees
./manage-worktrees.sh list
./manage-worktrees.sh remove feature-name
```

Each worktree provides isolated app (ports 5002+), database, and test environment.