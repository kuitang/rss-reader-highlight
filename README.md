# RSS Reader

A modern RSS reader built with FastHTML and MonsterUI, inspired by the email interface design pattern.

## Features

### Core Functionality
- **RSS/Atom Feed Support**: Parse and display both RSS and Atom feeds
- **Session-Based Users**: No login required - each browser session creates a unique user
- **Feed Management**: Add/remove RSS feeds with automatic feed discovery
- **Smart Feed Updates**: HTTP caching with ETags and Last-Modified headers
- **Read/Unread Tracking**: Mark items as read automatically when clicked
- **Starring System**: Star important items for later reference
- **Folder Organization**: Create custom folders to organize feed items

### User Interface
- **Three-Panel Layout**: Feeds sidebar, post list, and detail view (like email)
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Real-time Updates**: HTMX-powered interactions without page reloads
- **Search Functionality**: Filter posts by content
- **Time-Aware Display**: Human-readable timestamps ("2 hours ago")

### Default Feeds
The application comes pre-configured with:
- **Hacker News**: Front page stories
- **Reddit All**: Popular posts from all subreddits
- **WSJ Markets**: Financial market news

## Architecture

### Technology Stack
- **Backend**: FastHTML (Python web framework)
- **UI Framework**: MonsterUI (styled components)
- **Database**: SQLite with normalized schema
- **Feed Parsing**: feedparser library
- **HTTP Client**: httpx with proper caching
- **Frontend**: HTMX for dynamic interactions

### Database Schema
```sql
-- Global feeds (shared across all users)
feeds: id, url, title, description, last_updated, etag, last_modified

-- Feed items/posts
feed_items: id, feed_id, guid, title, link, description, content, published

-- Browser sessions (one per user)
sessions: id, created_at, last_accessed

-- User subscriptions (session-specific)
user_feeds: session_id, feed_id, added_at

-- User folders
folders: id, session_id, name

-- User item status (read/unread, starred, folder assignments)
user_items: session_id, item_id, is_read, starred, folder_id
```

## Installation & Setup

### Prerequisites
- Python 3.11+
- Virtual environment support  
- SQLite3 (usually included with Python)

### Quick Start

1. **Clone and setup environment**:
```bash
git clone <repository-url>
cd rss-reader-highlight
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Run the application**:
```bash
python app.py
```

3. **Open browser**:
   - Navigate to `http://localhost:5001`
   - The app will automatically set up default feeds on first run

### Development Setup

1. **Install development dependencies**:
```bash
source venv/bin/activate
pip install coverage pytest-cov pytest-html playwright
python -m playwright install  # For E2E tests
```

2. **Initialize empty database** (for testing):
```bash
python clear_db.py
```

3. **Run comprehensive tests**:
```bash
# Quick integration tests
python -m pytest test_comprehensive_integration.py -v

# Full test suite with coverage
coverage run --source=. -m pytest test_comprehensive_*.py -v
coverage report --show-missing

# E2E browser tests
python -m pytest test_comprehensive_e2e.py -v
```

### Fresh Installation Workflow

For a completely fresh installation:

```bash
# 1. Setup environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Clear any existing data
python clear_db.py  # Choose 'y' to confirm

# 3. Start application
python app.py

# 4. Open http://localhost:5001
# Default feeds (Hacker News, Reddit, WSJ) will auto-load
# First visitor automatically subscribed to all feeds
```

## Usage

### Adding Feeds
1. Enter RSS/Atom URL in the input field in the left sidebar
2. Click the `+` button
3. Feed will be parsed and items will appear in the main view

### Reading Posts
1. Click any post in the middle panel
2. Post content appears in the right panel
3. Post is automatically marked as read
4. Use action icons to star or organize posts

### Managing Content
- **Star Items**: Click star icon to save for later
- **Create Folders**: Click "Add Folder" button and enter folder name
- **Move to Folders**: Click folder icon when viewing a post
- **Mark Unread**: Click mail icon to mark post as unread

### Filtering
- **All Posts**: View all posts from subscribed feeds
- **Unread**: View only unread posts
- **Search**: Use search box to filter by content
- **By Feed**: Click feed name in sidebar to filter by specific feed

## API Endpoints

### Main Routes
- `GET /` - Homepage with full interface
- `GET /item/{id}` - Get item details and mark as read
- `GET /?feed_id={id}` - Filter by specific feed
- `GET /?unread=1` - Show only unread posts

### API Routes
- `POST /api/feed/add` - Add new RSS feed
- `POST /api/item/{id}/star` - Toggle star status
- `POST /api/item/{id}/read` - Toggle read status
- `POST /api/folder/add` - Create new folder

## Testing

### Comprehensive Test Suite

Our testing strategy focuses on **complex workflows that broke during development**, not trivial framework functionality.

### Optimized Test Suite Architecture

**Philosophy**: Test **complex workflows that broke during development**, not framework basics.

#### **Critical UI Flow Tests** (`test_critical_ui_flows.py`)
**622 lines, 16 tests** - Playwright automation targeting **exact bugs we debugged**:

**🐛 Specific Issues Tested:**
- **Form parameter bug**: `name="new_feed_url"` mapping → FastHTML parameters
- **BBC redirect handling**: 302 redirects → `follow_redirects=True` fix verification
- **Blue indicator HTMX**: Click article → Dot disappears → Multi-element updates
- **Unread view magic**: Click article → Item disappears from unread list
- **Session auto-subscription**: Fresh browser → Auto feeds → No "No posts available"
- **Full viewport height**: `h-screen` classes → Proper space utilization
- **Error handling UI**: Network errors → User feedback (not server crashes)

#### **HTTP Integration Tests** (`test_optimized_integration.py`)
**236 lines, 5 tests** - Black-box HTTP testing of complete server workflows:
- **Fresh start flow**: Empty DB → HTTP requests → Feed setup → Session creation
- **API endpoint verification**: All routes return proper HTTP responses  
- **Session persistence**: Cookie handling across requests
- **Pagination with parameters**: URL routing with complex parameter combinations
- **Form processing**: POST data → Server processing → Response verification

#### **Direct Function Tests** (`test_direct_functions.py`)
**204 lines, 8 tests** - Test internal logic supporting UI features:
- **Database workflow**: Session → Feeds → Subscribe → Read → Folders (complete flow)
- **Time formatting**: Human readable timestamps ("5 minutes ago")
- **Pagination logic**: Item slicing, page calculations (supports UI pagination)
- **Feed management**: Update logic, ETag handling (supports caching)

#### **Essential Mock Tests** (`test_essential_mocks.py`)
**240 lines, 8 tests** - Only for scenarios other tests **cannot safely cover**:
- **Network error simulation**: Timeouts, HTTP errors (dangerous to test live)
- **Database constraint violations**: FK violations (dangerous on real DB)
- **Malformed content handling**: Invalid RSS/XML (need controlled input)
- **Transaction rollbacks**: Error injection (need controlled failures)
- **Date parsing edge cases**: Invalid formats (need precise control)

### Test Coverage Strategy
- **Critical UI Flows**: Cover UI bugs that **actually broke** during development
- **HTTP Integration**: Cover server-side workflows with **real HTTP semantics**
- **Essential Mocks**: Cover **dangerous scenarios** HTTP tests cannot safely test
- **Combined Coverage**: 75%+ of critical application paths
- **Massive Optimization**: 70% fewer test lines (4,315 → 1,302) while **improving** focus on real issues

### Running Tests

#### **Quick Development Tests**
```bash
# Critical UI flows (recommended for development)
source venv/bin/activate
python -m pytest test_critical_ui_flows.py::TestFormParameterBugFlow -v

# HTTP integration (fast, no browser)
python -m pytest test_optimized_integration.py -v
```

#### **Full Test Suite**
```bash
# Complete optimized test suite
source venv/bin/activate

# All integration tests
python -m pytest test_optimized_integration.py test_essential_mocks.py -v

# All UI flow tests (requires browser setup time)
python -m pytest test_critical_ui_flows.py -v

# Everything with coverage
coverage run --source=. -m pytest test_optimized_integration.py test_essential_mocks.py -v
coverage report --show-missing
```

#### **Targeted Testing**
```bash
# Test specific bug categories
source venv/bin/activate

# Form and BBC redirect bugs
python -m pytest test_critical_ui_flows.py::TestFormParameterBugFlow test_critical_ui_flows.py::TestBBCRedirectHandlingFlow -v

# Blue indicator and HTMX updates
python -m pytest test_critical_ui_flows.py::TestBlueIndicatorHTMXFlow -v

# Session and auto-subscription 
python -m pytest test_critical_ui_flows.py::TestSessionAndSubscriptionFlow -v

# Error handling scenarios
python -m pytest test_essential_mocks.py::TestNetworkErrorScenarios -v
```

#### **Network Tests** (Optional)
```bash
# Test with real RSS feeds (requires internet)
NETWORK_TESTS=1 python -m pytest test_comprehensive_integration.py::TestRealWorldScenarios -v
```

### Database Management

#### **Reset Database**
```bash
source venv/bin/activate
python clear_db.py
```

#### **Manual Database Inspection**
```bash
sqlite3 data/rss.db
.tables
SELECT * FROM feeds;
SELECT COUNT(*) FROM feed_items;
SELECT * FROM sessions;
```

### Test-Driven Development Workflow

1. **Make changes** to application code
2. **Run quick tests** to catch regressions:
   ```bash
   python -m pytest test_comprehensive_integration.py::TestCriticalWorkflows -v
   ```
3. **Run full coverage** for major changes:
   ```bash
   coverage run --source=. -m pytest test_comprehensive_*.py -v && coverage report
   ```
4. **Run E2E tests** before releases:
   ```bash
   python -m pytest test_comprehensive_e2e.py::TestCompleteUserJourneys -v
   ```

## Configuration

### Environment Variables
- `RSS_DB_PATH`: Custom database path (default: `data/rss.db`)
- `INTEGRATION_TESTS`: Enable network-dependent tests

### Customization
- **Default Feeds**: Edit `setup_default_feeds()` in `feed_parser.py`
- **Update Frequency**: Modify `max_age_minutes` in feed update calls
- **UI Theme**: Change theme in `app.py` (e.g., `Theme.slate.headers()`)
- **Port**: Modify port in `serve()` call

## File Structure

```
rss-reader-highlight/
├── app.py                 # Main FastHTML application
├── models.py              # Database models and operations
├── feed_parser.py         # RSS/Atom parsing and HTTP handling
├── test_integration.py    # Integration tests with pytest + httpx
├── test_e2e.py           # End-to-end tests with Playwright
├── run_tests.py          # Test runner script
├── requirements.txt      # Python dependencies
├── mail-example.py       # MonsterUI reference implementation
├── data/                 # SQLite database storage
│   └── rss.db           # Main database file
├── tests/                # Test output and screenshots
└── venv/                 # Python virtual environment
```

## Design Decisions

### Why Session-Based Users?
- **Simplicity**: No authentication required
- **Privacy**: No personal data collection
- **Quick Start**: Users can immediately begin using the application

### Why SQLite?
- **Embedded**: No separate database server required
- **Reliable**: ACID transactions ensure data consistency
- **Performance**: Fast for read-heavy RSS workloads
- **Portable**: Single file database

### Why Three-Panel Layout?
- **Familiar**: Users understand email-like interfaces
- **Efficient**: Minimizes navigation between content
- **Scalable**: Works well with large numbers of feeds and items

## Performance Considerations

### Feed Updates
- **HTTP Caching**: Uses ETags and Last-Modified headers
- **Update Frequency**: Only updates feeds older than 1 minute
- **Background Processing**: Feed parsing happens asynchronously

### Database Optimization
- **Indexes**: Strategic indexes on commonly queried columns
- **Normalization**: Feeds shared across users, only status is per-user
- **Cascading Deletes**: Automatic cleanup when sessions expire

### Frontend Performance
- **HTMX**: Minimal JavaScript, server-side rendering
- **Selective Updates**: Only changed parts of UI are updated
- **Lazy Loading**: Items loaded as needed

## Contributing

### Development Workflow
1. Create feature branch
2. Write tests for new functionality
3. Implement feature following existing patterns
4. Run full test suite
5. Submit pull request

### Code Style
- Follow existing patterns in the codebase
- Use MonsterUI components for consistency
- Keep functions focused and testable
- Add docstrings for complex functionality

### Testing Requirements
- Add integration tests for new API endpoints
- Add E2E tests for new user interactions
- Ensure all tests pass before submitting changes

## Troubleshooting

### Common Issues

**Database Permission Errors**:
```bash
# Ensure data directory exists and is writable
mkdir -p data
chmod 755 data
```

**Feed Parsing Errors**:
```bash
# Check feed URL manually
curl -I "https://example.com/rss"
```

**Port Already in Use**:
```bash
# Change port in app.py serve() call
serve(port=5002, host="0.0.0.0")
```

**Missing Dependencies**:
```bash
# Reinstall requirements
pip install -r requirements.txt
```

### Logging
The application logs feed parsing activity to help with debugging:
- Feed update results
- HTTP response codes
- Parsing warnings

### Database Inspection
```bash
# View database contents
sqlite3 data/rss.db
.tables
SELECT * FROM feeds;
SELECT * FROM feed_items LIMIT 5;
```

## License

This project is built using open-source technologies:
- FastHTML: Apache 2.0 License
- MonsterUI: Open source UI framework
- feedparser: BSD License

The RSS Reader application code follows the same open-source spirit.

## Acknowledgments

- **MonsterUI Team**: For the excellent UI framework and mail example
- **FastHTML Team**: For the innovative Python-first web framework
- **feedparser**: For robust RSS/Atom parsing capabilities

---

*Built with ❤️ using FastHTML and MonsterUI*