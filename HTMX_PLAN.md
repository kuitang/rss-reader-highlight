# HTMX Decision Hoisting Implementation Plan

## Overview

Transform the RSS Reader from scattered conditional logic to clear, readable HTMX architecture where all decisions are made at the route level. The goal is routes that read like architectural specifications.

## Target Pattern

```python
@rt('/')
def index():
    # ALL DECISIONS AT TOP - CRYSTAL CLEAR
    session_id = get_session_id()
    data = prepare_page_data(session_id, feed_id, unread, page)
    
    # HTMX ROUTING OBVIOUS
    if is_htmx_request():
        return HTMX_FRAGMENTS[target](data)
    
    # FULL PAGE STRUCTURE OBVIOUS
    return chrome(session_id) + article_view(
        mobile_feeds=data.mobile_items,
        desktop_feeds=data.desktop_items
    )
```

## Step-by-Step Implementation

### Step 1: Extract All Configuration Constants

**Goal**: Move all magic strings and repeated values to the top of app.py

**What to Extract from Current Code**:
- HTMX targets: `#main-content`, `#desktop-item-detail`, `#sidebar`, etc.
- CSS classes: `lg:hidden`, `fixed inset-0`, feed item styling
- Element IDs: `mobile-sidebar`, `desktop-layout`, etc.

**Implementation**:
1. Add this block at the top of app.py after imports:

```python
# =============================================================================
# CONFIGURATION - All decisions and constants visible here
# =============================================================================

class Targets:
    """HTMX update targets - what gets swapped"""
    MOBILE_CONTENT = '#main-content'
    DESKTOP_FEEDS = '#desktop-feeds-content' 
    DESKTOP_DETAIL = '#desktop-item-detail'
    MOBILE_SIDEBAR = '#mobile-sidebar'
    DESKTOP_SIDEBAR = '#sidebar'

class ElementIDs:
    """DOM element identifiers"""
    MOBILE_SIDEBAR = 'mobile-sidebar'
    MOBILE_HEADER = 'mobile-header'
    MOBILE_PERSISTENT_HEADER = 'mobile-persistent-header'
    MOBILE_NAV_BUTTON = 'mobile-nav-button'

class Styling:
    """CSS classes for layouts and components"""
    MOBILE_LAYOUT = 'lg:hidden fixed inset-0 flex flex-col overflow-hidden'
    DESKTOP_LAYOUT = 'hidden lg:grid h-screen pt-4'
    FEED_ITEM_BASE = 'relative rounded-lg border border-border p-3 text-sm hover:bg-secondary space-y-2 cursor-pointer'
    FEED_ITEM_READ = 'bg-muted tag-read'
    FEED_ITEM_UNREAD = 'tag-unread'
```

2. Replace all hardcoded strings throughout app.py with these constants

**Test**: Verify app still works after replacing magic strings with constants

### Step 2: Use FastHTML's Built-in HTMX Helpers

**Goal**: Replace manual HTMX header parsing with FastHTML's built-in utilities

**Current Problem**: Manual header parsing like `request.headers.get('HX-Request') == 'true'` repeated throughout

**FastHTML Built-in Helpers**:
- **`htmx` parameter**: FastHTML automatically injects `HtmxHeaders` object
- **`HtmxHeaders` type annotation**: Alternative injection method
- **`Redirect` class**: Intelligent redirects for HTMX vs normal requests  
- **Automatic fragment handling**: FastHTML returns only HTML fragments for HTMX requests

**Implementation**:
1. Use FastHTML's `htmx` parameter in routes:

```python
# BEFORE: Manual header parsing
@rt('/')
def index(request, feed_id: int = None, unread: bool = True, page: int = 1):
    session_id = request.scope['session_id']
    is_htmx = request.headers.get('HX-Request') == 'true'
    hx_target = request.headers.get('HX-Target', '')

# AFTER: FastHTML built-in helpers
@rt('/')
def index(htmx: HtmxHeaders, sess, feed_id: int = None, unread: bool = True, page: int = 1):
    """FastHTML automatically detects HTMX and provides session"""
    session_id = sess.get('session_id')
    
    # CLEAR HTMX DETECTION - No manual header parsing
    if htmx:  # FastHTML's HtmxHeaders evaluates to True for HTMX requests
        fragment_handler = HTMX_FRAGMENTS.get(htmx.target)
        if not fragment_handler:
            return Div(f"Unknown target: {htmx.target}", cls='text-red-500 p-4')
        return fragment_handler(PageData(session_id, feed_id, unread, page))
    
    # FULL PAGE - FastHTML automatically adds HTML structure for non-HTMX
    return chrome(session_id) + article_view(PageData(session_id, feed_id, unread, page))
```

2. Update all routes to use `htmx` parameter instead of manual header checks:

```python
# Item detail route using FastHTML helpers
@rt('/item/{item_id}')
def show_item(item_id: int, htmx: HtmxHeaders, sess, unread_view: bool = False, feed_id: int = None):
    """Item detail using FastHTML's built-in HTMX detection"""
    session_id = sess.get('session_id')
    item_data = prepare_item_data(session_id, item_id, feed_id, unread_view)
    
    if not item_data.item:
        return handle_item_not_found(htmx, feed_id, unread_view)
    
    mark_item_read_and_refresh(item_data)
    
    # FastHTML automatically handles fragment vs full page response
    if htmx:
        return htmx_item_response(htmx.target, item_data)
    else:
        return full_page_item_response(item_data)  # FastHTML adds HTML structure
```

3. Use `Redirect` class for intelligent redirects:

```python
# BEFORE: Manual redirect logic
if some_condition:
    if is_htmx:
        return SomeFragment()
    else:
        return RedirectResponse("/somewhere")

# AFTER: FastHTML Redirect class handles both cases
if some_condition:
    return Redirect("/somewhere")  # Automatically HX-Redirect for HTMX, HTTP redirect for normal
```

**Test**: HTMX detection works through FastHTML's built-in `htmx` parameter

### Step 3: Create Data Preparation Layer

**Goal**: Hoist all data fetching and preparation to route level

**Current Problem**: Data fetching scattered throughout components

**Implementation**:
1. Create data preparation class:

```python
class PageData:
    """Centralized data preparation - all DB queries here"""
    def __init__(self, session_id, feed_id=None, unread=True, page=1):
        self.session_id = session_id
        self.feed_id = feed_id
        self.unread = unread
        self.page = page
        
        # FETCH ALL DATA ONCE
        self.items = FeedItemModel.get_items_for_user(session_id, feed_id, unread, page)
        self.feeds = FeedModel.get_user_feeds(session_id)
        self.folders = FolderModel.get_folders(session_id)
        
        # PRE-CONFIGURE FOR DIFFERENT CONTEXTS
        self.mobile_config = {
            'target': Targets.MOBILE_CONTENT,
            'push_url': True,
            'show_summary': True,
            'layout': 'mobile'
        }
        
        self.desktop_config = {
            'target': Targets.DESKTOP_DETAIL,
            'push_url': True, 
            'show_summary': True,
            'layout': 'desktop'
        }
```

2. Update routes to use PageData instead of direct DB calls

**Test**: Verify same data is returned but through centralized preparation

### Step 4: Create HTMX Fragment Map

**Goal**: Make all HTMX update targets explicit and visible

**Implementation**:
1. Add fragment map after PageData class:

```python
# HTMX FRAGMENT ARCHITECTURE - What gets updated by HTMX
HTMX_FRAGMENTS = {
    'main-content': lambda data: mobile_feeds_view(data),
    'desktop-feeds-content': lambda data: desktop_feeds_view(data),
    'desktop-item-detail': lambda data: ItemDetailView(data.selected_item),
    'mobile-sidebar': lambda data: MobileSidebar(data.session_id),
    'sidebar': lambda data: desktop_sidebar_view(data),
}

def mobile_feeds_view(data):
    """Mobile feeds list fragment"""
    return FeedsContent(data.session_id, data.mobile_config, data.feed_id, data.unread, data.page)

def desktop_feeds_view(data):
    """Desktop feeds list fragment"""  
    return FeedsContent(data.session_id, data.desktop_config, data.feed_id, data.unread, data.page)

def desktop_sidebar_view(data):
    """Desktop sidebar fragment using MonsterUI patterns"""
    return Container(
        FeedsSidebar(data.session_id),
        id='sidebar',  # Use semantic ID directly
        cls='col-span-1 h-screen overflow-y-auto border-r px-2'
    )
```

**Test**: All HTMX targets in components should exist in HTMX_FRAGMENTS map

### Step 5: Refactor Main Routes to Use Decision Hoisting

**Goal**: Transform index() and show_item() to show clear structure

**Implementation**:
1. Refactor index() route (app.py:728-887):

```python
@rt('/')
def index(htmx: HtmxHeaders, sess, feed_id: int = None, unread: bool = True, page: int = 1):
    """Main page using FastHTML native patterns"""
    session_id = sess.get('session_id')
    data = PageData(session_id, feed_id, unread, page)
    
    # QUEUE BACKGROUND UPDATES
    queue_user_feeds_for_update(session_id)
    
    # HTMX FRAGMENT ROUTING - FastHTML native
    if htmx:
        fragment_fn = HTMX_FRAGMENTS.get(htmx.target)
        if not fragment_fn:
            return Alert(f"Unknown target: {htmx.target}", type='error', cls='m-4')
        
        # SPECIAL CASE: Mobile navigation back - handle with FastHTML
        if htmx.target == 'main-content' and 'returning_from_article' in str(htmx.current_url):
            return mobile_navigation_restore(data)
        
        return fragment_fn(data)
    
    # FULL PAGE - FastHTML handles HTML structure automatically
    return full_page_layout(data)

def mobile_navigation_restore(data):
    """Handle mobile back navigation - restore list + header"""
    return [
        mobile_feeds_view(data),
        mobile_persistent_header_restore(data),
        mobile_nav_button_restore(data)
    ]

def full_page_layout(data):
    """Complete page structure - FastHTML handles Title/Body automatically"""
    return [
        chrome(data.session_id),
        article_view(data)
    ]

def chrome(session_id):
    """Shell components using MonsterUI patterns"""
    return [
        Container(MobileHeader(session_id), id='mobile-header'),
        MobileSidebar(session_id)
    ]

def article_view(data):
    """Content areas with both mobile and desktop"""
    return [
        # Mobile layout (responsive CSS handles visibility)
        Div(cls=Styling.MOBILE_LAYOUT, id="mobile-layout")(
            Div(cls="h-20 flex-shrink-0"),  # Header spacer
            MobilePersistentHeader(data.session_id, data.feed_id, data.unread),
            Div(cls="flex-1 overflow-y-auto", id="main-content")(
                mobile_feeds_view(data)
            )
        ),
        # Desktop layout  
        Div(cls=Styling.DESKTOP_LAYOUT, id="desktop-layout")(
            Grid(
                desktop_sidebar_view(data),
                Div(cls='col-span-2 h-screen flex flex-col overflow-hidden border-r px-4', id="desktop-feeds-content")(
                    desktop_feeds_view(data)
                ),
                Div(id="desktop-item-detail", cls='col-span-2 h-screen overflow-y-auto px-6')(
                    ItemDetailView(None)
                ),
                cols_lg=5, cols_xl=5, gap=4, cls='h-screen gap-4'
            )
        )
    ]
```

2. Refactor show_item() route (app.py:889-1102) using same pattern:

```python
@rt('/item/{item_id}')
def show_item(item_id: int, htmx: HtmxHeaders, sess, unread_view: bool = False, feed_id: int = None):
    """Item detail using FastHTML native patterns"""
    session_id = sess.get('session_id')
    
    # DATA PREPARATION
    item_data = prepare_item_data(session_id, item_id, feed_id, unread_view)
    
    if not item_data.item:
        if htmx:
            return Alert("Item not found", type='error', cls='m-4')
        else:
            return Redirect("/")  # FastHTML handles HTMX vs HTTP redirect
    
    # MARK AS READ
    mark_item_read_and_refresh(item_data)
    
    # RESPONSE ROUTING - FastHTML automatic
    if htmx:
        return htmx_item_response(htmx.target, item_data)
    else:
        return full_page_item_response(item_data)  # FastHTML adds HTML structure

def prepare_item_data(session_id, item_id, feed_id, unread_view):
    """Centralized item data preparation"""
    class ItemData:
        def __init__(self):
            self.item = FeedItemModel.get_item_for_user(session_id, item_id)
            self.was_unread = not self.item.get('is_read', 0) if self.item else False
            self.feed_id = feed_id
            self.unread_view = unread_view
        
        def refresh_after_read(self):
            self.item = FeedItemModel.get_item_for_user(session_id, item_id)
    
    return ItemData()

def htmx_item_response(target, item_data):
    """HTMX item response using FastHTML patterns"""
    responses = [ItemDetailView(item_data.item)]
    
    # MOBILE UPDATES - FastHTML handles fragment formatting
    if target == 'main-content':
        responses.extend(mobile_article_view_updates(item_data))
    
    # DESKTOP UPDATES - single element return preferred
    if target == 'desktop-item-detail' and item_data.was_unread:
        responses.append(desktop_item_list_update(item_data))
    
    return responses[0] if len(responses) == 1 else tuple(responses)
```

**Test**: Route logic should be readable and show clear decision points

### Step 6: Simplify Components to Use Configuration

**Goal**: Remove all conditional logic from components

**Current Problem**: FeedItem() has complex branching (app.py:356-417)

**Implementation**:
1. Refactor FeedItem to be pure:

```python
def FeedItem(item, config):
    """Pure component - no decisions, just renders config"""
    read_state = item.get('is_read', 0)
    
    return Li(
        # Title with read state styling
        Strong(item['title']) if not read_state else Span(item['title']),
        
        # Source and time
        DivFullySpaced(
            Small(item.get('feed_title', 'Unknown'), cls=TextPresets.muted_sm),
            Time(human_time_diff(item.get('published')), cls='text-xs text-muted-foreground')
        ),
        
        # Summary (controlled by config)
        Div(NotStr(smart_truncate_html(item.get('description', ''), max_length=300))) if config['show_summary'] else None,
        
        # HTMX attributes from config
        hx_get=f"/item/{item['id']}?feed_id={config.get('feed_id')}&unread_view={config.get('unread_view')}",
        hx_target=config['target'],
        hx_push_url=str(config['push_url']),
        cls=f"{Styling.FEED_ITEM_BASE} {Styling.FEED_ITEM_READ if read_state else Styling.FEED_ITEM_UNREAD}",
        id=f"{config['layout']}-feed-item-{item['id']}"
    )
```

2. Refactor FeedsContent to use config:

```python
def FeedsContent(data, config):
    """Pure feeds content - behavior determined by config"""
    # Configure each item with context
    configured_items = [
        {**item, **config, 'feed_id': data.feed_id, 'unread_view': data.unread}
        for item in data.items
    ]
    
    return Div(cls=f'{config["layout"]}-feeds-container')(
        Ul(cls='js-filter space-y-2 p-4 pt-0')(
            *[FeedItem(item, config) for item in configured_items]
        )
    )
```

**Test**: Components should render identically with same inputs

### Step 7: Create Fragment Dispatcher System Using FastHTML Patterns

**Goal**: Centralize HTMX routing using FastHTML's automatic fragment handling

**FastHTML's Automatic Behavior**:
- FastHTML automatically returns HTML fragments (no `<html>`, `<head>`, `<body>`) for HTMX requests
- Non-HTMX requests get full HTML document structure automatically
- No need to manually check request type for response formatting

**Implementation**:
1. Create clean fragment map leveraging FastHTML's automatic behavior:

```python
# HTMX FRAGMENT ARCHITECTURE - FastHTML handles fragment vs full page automatically
HTMX_FRAGMENTS = {
    'main-content': handle_mobile_content,
    'desktop-feeds-content': handle_desktop_feeds,
    'desktop-item-detail': handle_desktop_detail,
    'mobile-sidebar': handle_mobile_sidebar,
    'sidebar': handle_desktop_sidebar,
}

def handle_mobile_content(data):
    """Mobile content fragment - FastHTML handles fragment formatting"""
    if hasattr(data, 'selected_item'):
        return ItemDetailView(data.selected_item)
    else:
        return FeedsContent(data, data.mobile_config)

def handle_desktop_feeds(data):
    """Desktop feeds fragment - no manual HTML structure needed"""
    return FeedsContent(data, data.desktop_config)

def handle_desktop_detail(data):
    """Desktop detail fragment - FastHTML handles the rest"""
    return ItemDetailView(data.selected_item)

def handle_mobile_sidebar(data):
    """Mobile sidebar - clean component return"""
    return MobileSidebar(data.session_id)

def handle_desktop_sidebar(data):
    """Desktop sidebar - simplified with FastHTML patterns"""
    return FeedsSidebar(data.session_id)  # FastHTML will wrap in proper container if needed
```

2. Simplified route pattern using FastHTML helpers:

```python
@rt('/')
def index(htmx: HtmxHeaders, sess, feed_id: int = None, unread: bool = True, page: int = 1):
    """Clean route using FastHTML's HTMX integration"""
    session_id = sess.get('session_id')
    data = PageData(session_id, feed_id, unread, page)
    
    # FRAGMENT ROUTING - FastHTML handles HTML structure automatically
    if htmx:
        fragment_handler = HTMX_FRAGMENTS.get(htmx.target)
        return fragment_handler(data) if fragment_handler else Div("Unknown target", cls='text-red-500 p-4')
    
    # FULL PAGE - FastHTML adds Title, Body automatically if needed
    return [
        chrome(session_id),
        article_view(data)
    ]
```

**Test**: All HTMX requests route through fragment handlers with FastHTML's automatic formatting

### Step 8: Refactor Main Routes

**Goal**: Make routes read like architectural specifications

**Implementation**:
1. Refactor index() route using FastHTML native patterns (same as Step 7):

```python
@rt('/')
def index(htmx: HtmxHeaders, sess, feed_id: int = None, unread: bool = True, page: int = 1):
    """Main page using FastHTML native HTMX helpers"""
    
    # DATA PREPARATION - ALL AT TOP
    session_id = sess.get('session_id') 
    data = PageData(session_id, feed_id, unread, page)
    queue_user_feeds_for_update(session_id)
    
    # HTMX FRAGMENT ROUTING - FastHTML native
    if htmx:
        fragment_handler = HTMX_FRAGMENTS.get(htmx.target)
        if not fragment_handler:
            return Alert(f"Unknown target: {htmx.target}", type='error', cls='m-4')
        return fragment_handler(data)
    
    # FULL PAGE - FastHTML adds HTML structure automatically
    return full_page_layout(data)

def full_page_layout(data):
    """Complete page structure - FastHTML handles Title/Body automatically"""
    return [
        chrome(data.session_id),
        article_view(data),
        global_styles()
    ]

def chrome(session_id):
    """Shell components - don't change during HTMX updates"""
    return [
        Div(id=ElementIDs.MOBILE_HEADER)(MobileHeader(session_id)),
        MobileSidebar(session_id)
    ]

def article_view(data):
    """Content areas - both mobile and desktop present"""
    return [
        # Mobile layout
        Div(cls=Styling.MOBILE_LAYOUT, id="mobile-layout")(
            Div(cls="h-20 flex-shrink-0"),
            MobilePersistentHeader(data.session_id, data.feed_id, data.unread),
            Div(cls="flex-1 overflow-y-auto", id="main-content")(
                handle_mobile_content(data)
            )
        ),
        # Desktop layout
        Div(cls=Styling.DESKTOP_LAYOUT, id="desktop-layout")(
            Grid(
                handle_desktop_sidebar(data),
                Div(cls='col-span-2 h-screen flex flex-col overflow-hidden border-r px-4', id="desktop-feeds-content")(
                    handle_desktop_feeds(data)
                ),
                Div(id="desktop-item-detail", cls='col-span-2 h-screen overflow-y-auto px-6')(
                    ItemDetailView(None)
                ),
                cols_lg=5, cols_xl=5, gap=4, cls='h-screen gap-4'
            )
        )
    ]
```

2. Refactor show_item() route similarly:

```python
@rt('/item/{item_id}')
def show_item(item_id: int, request, unread_view: bool = False, feed_id: int = None):
    """Item detail - decisions hoisted to top"""
    
    # CONTEXT AND DATA
    ctx = get_request_context(request)
    item_data = ItemPageData(ctx['session_id'], item_id, feed_id, unread_view)
    
    if not item_data.item:
        return handle_item_not_found(ctx, feed_id, unread_view)
    
    # SIDE EFFECTS
    mark_item_read_and_refresh(item_data)
    
    # ROUTING - CLEAR
    if ctx['is_htmx']:
        return htmx_item_view(ctx, item_data)
    else:
        return full_page_item_view(item_data)
```

**Test**: Routes should be readable and show clear structure at the top

### Step 9: Eliminate Out-of-Band Swaps

**Goal**: Replace tuple responses with single container updates

**Current Problem**: Multiple `hx_swap_oob` responses (app.py:776, 811, 1038)

**Implementation**:
1. Create container-based update endpoints:

```python
@rt('/ui/mobile-navigation')
def mobile_navigation_container(htmx: HtmxHeaders, sess, feed_id: int = None, unread: bool = True, show_back: bool = False):
    """Update entire mobile navigation using FastHTML patterns"""
    session_id = sess.get('session_id')
    
    # FastHTML automatically handles fragment response
    return Container(
        MobileHeader(session_id, show_back=show_back, feed_id=feed_id),
        MobilePersistentHeader(session_id, feed_id, unread, show_chrome=not show_back),
        id="mobile-navigation-container"
    )
```

2. Update HTML structure to use containers:

```html
<!-- Replace scattered elements with single containers -->
<div id="mobile-navigation-container">
  <!-- All mobile navigation updated as one unit -->
</div>
```

3. Replace tuple returns with single element returns

**Test**: Each HTMX request should update exactly one DOM container

### Step 10: Eliminate JavaScript State Management

**Goal**: Replace onclick handlers with HTMX endpoints

**Current Problem**: onclick handlers for sidebar open/close (app.py:609, 618, 659)

**Implementation**:
1. Create state management endpoints:

```python
@rt('/ui/sidebar/{action}')
def sidebar_action(action: str, htmx: HtmxHeaders, sess):
    """Server-controlled sidebar using FastHTML native patterns"""
    session_id = sess.get('session_id')
    
    if action == 'open':
        return MobileSidebarOpen(session_id)
    elif action == 'close':
        return MobileSidebarClosed()
    else:
        return Div(id='mobile-sidebar')  # Default closed state
```

2. Replace onclick with HTMX using FastHTML patterns:

```python
# Replace: onclick="document.getElementById('mobile-sidebar').removeAttribute('hidden')"
Button(
    UkIcon('menu'),
    hx_get="/ui/sidebar/open",
    hx_target=Targets.MOBILE_SIDEBAR,
    cls="p-2 rounded border hover:bg-secondary"
)

# Replace: onclick="document.getElementById('mobile-sidebar').setAttribute('hidden', 'true')"  
Button(
    UkIcon('x'),
    hx_get="/ui/sidebar/close",
    hx_target=Targets.MOBILE_SIDEBAR,
    cls="p-1 rounded hover:bg-secondary"
)

# Sidebar state routes using FastHTML helpers
@rt('/ui/sidebar/{action}')
def sidebar_action(action: str, htmx: HtmxHeaders, sess):
    """Server-controlled sidebar using FastHTML HTMX helpers"""
    session_id = sess.get('session_id')
    
    if action == 'open':
        return MobileSidebarOpen(session_id)  # FastHTML handles fragment formatting
    elif action == 'close':
        return MobileSidebarClosed()  # FastHTML handles fragment formatting
    else:
        return Div(id='mobile-sidebar')  # Default state - no need for ElementIDs class
```

**Test**: All UI state changes trigger HTMX requests, FastHTML handles response formatting

## Final Architecture Using FastHTML HTMX Helpers

After implementation, the code should read like this:

```python
# CONFIGURATION (top of file) 
class Targets: ...
class Styling: ...
HTMX_FRAGMENTS = {...}

# ROUTES (architectural specifications using FastHTML helpers)
@rt('/')
def index(htmx: HtmxHeaders, sess, **params):
    """Clean route using FastHTML's built-in HTMX detection"""
    session_id = sess.get('session_id')
    data = PageData(session_id, **params)
    
    # HTMX FRAGMENT ROUTING - FastHTML handles response formatting
    if htmx:
        return HTMX_FRAGMENTS[htmx.target](data)
    
    # FULL PAGE - FastHTML adds HTML structure automatically
    return chrome(session_id) + article_view(data)

@rt('/api/feed/add')
def add_feed(htmx: HtmxHeaders, sess, new_feed_url: str = ""):
    """Form handler using FastHTML HTMX helpers"""
    session_id = sess.get('session_id')
    
    # Process feed addition
    process_feed_addition(session_id, new_feed_url)
    
    # FastHTML automatically formats response as fragment
    return HTMX_FRAGMENTS[htmx.target](PageData(session_id))

# COMPONENTS (pure functions)
def FeedItem(item, config): ...
def chrome(session_id): ...  
def article_view(data): ...
```

### Key FastHTML Benefits Applied:

1. **`htmx: HtmxHeaders` parameter**: Eliminates manual header parsing
2. **`sess` parameter**: Built-in session access
3. **Automatic fragment handling**: FastHTML returns fragments for HTMX, full HTML for normal requests
4. **`Redirect` class**: Intelligent redirects (HX-Redirect for HTMX, HTTP redirect for normal)
5. **No manual Title/Body wrapping**: FastHTML adds HTML structure automatically for non-HTMX requests

## Success Criteria

- **Readable routes**: Architecture visible at route level
- **Zero conditional logic in components**: All decisions made at route/data level
- **Explicit HTMX targets**: Fragment map shows what gets updated
- **No JavaScript state**: All state managed server-side via HTMX
- **Single responsibility**: Each function has one clear purpose
- **Testable units**: Components are pure functions with predictable outputs

## Testing Approach

1. **Constants test**: Verify all magic strings replaced with named constants
2. **Fragment coverage test**: Ensure HTMX_FRAGMENTS covers all targets used in components  
3. **Route architecture test**: Verify routes follow the prescribed pattern
4. **Component purity test**: Components with same inputs return same HTML
5. **HTMX integration test**: All user interactions trigger expected server requests