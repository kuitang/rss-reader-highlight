# FastHTML Development Notes

## Key FastHTML Concepts

### Basic Usage Pattern
```python
from fasthtml.common import *

app, rt = fast_app()

@rt('/')
def get(): 
    return Div(P('Hello World!'), hx_get="/change")

serve()
```

### Session Management
FastHTML apps support built-in session handling - perfect for our RSS reader requirements.

### Core Features for RSS Reader
1. **HTML Components**: Direct mapping from Python to HTML
2. **HTMX Integration**: For dynamic content updates without full page reloads
3. **Session Support**: Built-in session management
4. **Database Integration**: Compatible with SQLite and other databases
5. **Routing**: Simple decorator-based routing system

### Project Architecture Plan
- Use `fast_app()` with session support enabled
- SQLite database with normalized schema
- HTMX for dynamic feed updates and read/unread marking
- Session-based user data (no login required)
- Feed parsing with `feedparser` library

### Key Libraries Needed
- `python-fasthtml` - Main framework  
- `feedparser` - RSS/Atom parsing
- `httpx` - HTTP client for feed fetching
- `monsterui` - UI components
- `pytest` - Testing
- `playwright` - E2E testing

### MonsterUI Integration
FastHTML works seamlessly with MonsterUI by importing both:
```python
from fasthtml.common import *
from monsterui.all import *

app, rt = fast_app(hdrs=Theme.blue.headers())
```

This gives us all the styled components from the mail example we studied.