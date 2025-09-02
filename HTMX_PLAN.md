# HTMX Decision Hoisting Implementation Plan (Revised)

## Key Revision: Embrace Architectural Differences

**Original Plan Problem**: Tried to unify mobile and desktop HTMX targeting when they are fundamentally different UX paradigms.

**Revised Approach**: Accept and make explicit that:
- Mobile uses `#main-content` for full-screen navigation
- Desktop uses `#desktop-feeds-content` and `#desktop-item-detail` for three-column email interface
- These differences are architectural, not accidental

## Overview

Transform the RSS Reader from scattered conditional logic to clear, readable HTMX architecture where all decisions are made at the route level. The goal is routes that read like architectural specifications while **accepting the architectural reality that mobile and desktop require different HTMX targets**.

## Target Pattern

```python
@rt('/')
def index(htmx: HtmxHeaders, sess, feed_id: int = None, unread: bool = True, page: int = 1):
    # ALL DECISIONS AT TOP - CRYSTAL CLEAR
    session_id = sess.get('session_id')
    data = PageData(session_id, feed_id, unread, page)
    
    # HTMX ROUTING - EXPLICIT ABOUT MOBILE VS DESKTOP
    if htmx:
        # Mobile and desktop have different targets by design
        if htmx.target == 'main-content':
            return mobile_content_handler(data)
        elif htmx.target == 'desktop-feeds-content':
            return desktop_feeds_handler(data)
        elif htmx.target == 'desktop-item-detail':
            return desktop_detail_handler(data)
        else:
            return unknown_target_error(htmx.target)
    
    # FULL PAGE - BOTH LAYOUTS RENDERED
    return full_page_with_dual_layouts(data)
```

## Step-by-Step Implementation

### Step 1: Extract All Configuration Constants ✅ **COMPLETED**

**Goal**: Move all magic strings and repeated values to the top of app.py

**Status**: ✅ Already implemented in app.py lines 31-67

**What Was Implemented**:
- HTMX targets: `Targets.MOBILE_CONTENT`, `Targets.DESKTOP_FEEDS`, etc.
- CSS classes: `Styling.MOBILE_LAYOUT`, `Styling.DESKTOP_LAYOUT`, etc.  
- Element IDs: `ElementIDs.MOBILE_SIDEBAR`, `ElementIDs.DESKTOP_LAYOUT`, etc.

**Additional Implementation Found**:
- `MINIMAL_MODE` feature for fast testing (models.py)
- Database path switching for minimal vs full mode

### Step 2: Use FastHTML's Built-in HTMX Helpers ❌ **NOT YET IMPLEMENTED**

**Goal**: Replace manual HTMX header parsing with FastHTML's built-in utilities

**Current Status**: Manual header parsing still used throughout app.py (lines 803, 944, 1049)

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
        # Route handling shown in Step 5
        return route_htmx_fragment(htmx, PageData(session_id, feed_id, unread, page))
    
    # FULL PAGE - FastHTML automatically adds HTML structure for non-HTMX
    return full_page_dual_layout(PageData(session_id, feed_id, unread, page))
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

### Step 3: Create Data Preparation Layer ❌ **NOT YET IMPLEMENTED**

**Goal**: Hoist all data fetching and preparation to route level

**Current Status**: Data fetching still scattered in route functions, no PageData class exists

**Implementation**:
1. Create data preparation class that explicitly supports dual layouts:

```python
class PageData:
    """Centralized data preparation - acknowledges mobile/desktop differences"""
    def __init__(self, session_id, feed_id=None, unread=True, page=1):
        self.session_id = session_id
        self.feed_id = feed_id
        self.unread = unread
        self.page = page
        
        # FETCH ALL DATA ONCE
        self.items = FeedItemModel.get_items_for_user(session_id, feed_id, unread, page)
        self.feeds = FeedModel.get_user_feeds(session_id)
        self.folders = FolderModel.get_folders(session_id)
        self.feed_name = self._get_feed_name()
        self.total_pages = self._calculate_total_pages()
        
        # EXPLICIT DUAL-LAYOUT SUPPORT
        # Mobile and desktop need different configs - this is by design
        self.mobile_config = {
            'target': Targets.MOBILE_CONTENT,  # Full-screen content swap
            'push_url': True,
            'show_summary': True,
            'layout': 'mobile',
            'id_prefix': 'mobile-'
        }
        
        self.desktop_config = {
            'feeds_target': Targets.DESKTOP_FEEDS,  # Middle column only
            'detail_target': Targets.DESKTOP_DETAIL,  # Right column only
            'push_url': True, 
            'show_summary': True,
            'layout': 'desktop',
            'id_prefix': 'desktop-'
        }
    
    def _get_feed_name(self):
        """Get current feed name for display"""
        if self.feed_id:
            feed = next((f for f in self.feeds if f['id'] == self.feed_id), None)
            return feed['title'] if feed else "Unknown Feed"
        return "All Feeds"
    
    def _calculate_total_pages(self):
        """Calculate pagination info"""
        # Implementation here
        pass
```

2. Update routes to use PageData instead of direct DB calls

**Test**: Verify same data is returned but through centralized preparation

### Step 4: Create Explicit Mobile/Desktop Fragment Architecture ❌ **NOT YET IMPLEMENTED**

**Goal**: Make the mobile/desktop split explicit and clear in the architecture

**Current Status**: Handler classes don't exist yet, routing is still inline in route functions

**Implementation**:
1. Create layout-specific fragment handlers that embrace the differences:

```python
# MOBILE FRAGMENT HANDLERS - Single-column, full-screen navigation
class MobileHandlers:
    """Mobile uses #main-content for full-screen swapping"""
    
    @staticmethod
    def content(data):
        """Mobile content area - feeds list or article detail"""
        return FeedsContent(data.session_id, data.feed_id, data.unread, 
                          data.page, for_desktop=False)
    
    @staticmethod
    def article(data, item_id):
        """Mobile article view - full screen replacement"""
        return ItemDetailView(data.get_item(item_id), show_back=False)
    
    @staticmethod
    def sidebar(data):
        """Mobile sidebar overlay"""
        return MobileSidebar(data.session_id)
    
    @staticmethod
    def navigation_restore(data):
        """Restore mobile navigation when returning from article"""
        return [
            FeedsContent(data.session_id, data.feed_id, data.unread, 
                        data.page, for_desktop=False),
            MobilePersistentHeader(data.session_id, data.feed_id, data.unread),
            mobile_nav_button_hamburger()
        ]

# DESKTOP FRAGMENT HANDLERS - Three-column email interface
class DesktopHandlers:
    """Desktop uses separate targets for each column"""
    
    @staticmethod
    def feeds_column(data):
        """Middle column - feeds list only"""
        return FeedsContent(data.session_id, data.feed_id, data.unread,
                          data.page, for_desktop=True)
    
    @staticmethod
    def detail_column(data, item_id):
        """Right column - article detail only"""
        return ItemDetailView(data.get_item(item_id), show_back=False)
    
    @staticmethod
    def sidebar_column(data):
        """Left column - feeds sidebar"""
        return Div(id=ElementIDs.SIDEBAR, cls=Styling.SIDEBAR_DESKTOP)(
            FeedsSidebar(data.session_id)
        )

# ROUTING MAP - Explicit about which handler for which target
HTMX_ROUTING = {
    # Mobile targets
    'main-content': MobileHandlers.content,
    'mobile-sidebar': MobileHandlers.sidebar,
    
    # Desktop targets
    'desktop-feeds-content': DesktopHandlers.feeds_column,
    'desktop-item-detail': DesktopHandlers.detail_column,
    'sidebar': DesktopHandlers.sidebar_column,
}
```

**Test**: Each target maps to exactly one handler, mobile and desktop are clearly separated

### Step 5: Refactor Main Routes with Explicit Layout Routing

**Goal**: Define how routes use the handler architecture from Step 4

**Implementation**:
1. Create routing function that uses the handlers:

```python
def route_htmx_fragment(htmx: HtmxHeaders, data: PageData):
    """Route HTMX requests using handlers from Step 4"""
    
    # Use the HTMX_ROUTING map from Step 4
    handler = HTMX_ROUTING.get(htmx.target)
    if not handler:
        return Alert(f"Unknown target: {htmx.target}", type='error', cls='m-4')
    
    # Special case for mobile navigation restore
    if htmx.target == 'main-content' and is_returning_from_article(htmx):
        return MobileHandlers.navigation_restore(data)
    
    # Otherwise use the mapped handler
    return handler(data)
```

2. Define the full page layout:

```python
def full_page_dual_layout(data):
    """Complete page with both mobile and desktop layouts"""
    return [
        # Chrome elements (modals, headers)
        mobile_chrome(data.session_id),
        
        # BOTH LAYOUTS RENDERED - CSS handles visibility
        mobile_layout(data),
        desktop_layout(data),
        
        # Global styles for viewport management
        viewport_styles()
    ]

def mobile_chrome(session_id):
    """Mobile-specific chrome elements"""
    return [
        Div(id='mobile-header')(MobileHeader(session_id, show_back=False)),
        MobileSidebar(session_id)
    ]

def mobile_layout(data):
    """Mobile layout - single column, full-screen navigation"""
    return Div(cls=Styling.MOBILE_LAYOUT, id="mobile-layout")(
        Div(cls="h-20 flex-shrink-0"),  # Header spacer
        MobilePersistentHeader(data.session_id, data.feed_id, data.unread),
        Div(cls="flex-1 overflow-y-auto", id="main-content")(
            MobileHandlers.content(data)
        )
    )

def desktop_layout(data):
    """Desktop layout - three-column email interface"""
    return Div(cls=Styling.DESKTOP_LAYOUT, id="desktop-layout")(
        Grid(
            DesktopHandlers.sidebar_column(data),
            Div(cls='col-span-2 h-screen flex flex-col overflow-hidden border-r px-4', 
                id="desktop-feeds-content")(
                DesktopHandlers.feeds_column(data)
            ),
            Div(id="desktop-item-detail", cls='col-span-2 h-screen overflow-y-auto px-6')(
                ItemDetailView(None)  # Empty on initial load
            ),
            cols_lg=5, cols_xl=5, gap=4, cls='h-screen gap-4'
        )
    )
```

3. Example of show_item route implementation:

```python
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

### Step 6: Keep Existing Component Pattern with Partial Unification ✅ **MOSTLY COMPLETED**

**Goal**: Acknowledge that components handle layout differences appropriately, but unify where possible

**Current Status**: 
- ✅ FeedItem() already uses `for_desktop` parameter effectively (app.py:398-459)
- 🔶 Tab containers still have some duplication but mobile navigation was simplified

**What to Keep As-Is**:
```python
def FeedItem(item, unread_view=False, for_desktop=False, feed_id=None):
    """Component that explicitly handles layout differences"""
    # Different IDs for mobile vs desktop (necessary for valid HTML)
    item_id = f"{'desktop-' if for_desktop else 'mobile-'}feed-item-{item['id']}"
    
    # Different HTMX targets (architectural requirement)
    if for_desktop:
        target = Targets.DESKTOP_DETAIL
    else:
        target = Targets.MOBILE_CONTENT
    
    # Rest of component logic...
```

**What to Unify - Tab Containers**:
```python
def create_tab_container(feed_name, feed_id, unread_only, for_mobile=False):
    """Create All Posts/Unread tabs with layout-appropriate attributes
    
    Mobile needs HTMX attributes to preserve persistent header during navigation.
    Desktop can use regular links since the three-column layout persists.
    """
    # Build base URL for navigation
    url_params = []
    if feed_id:
        url_params.append(f"feed_id={feed_id}")
    base_url = "/?" + "&".join(url_params) if url_params else "/"
    
    # Common tab structure with conditional HTMX attributes
    return TabContainer(
        Li(A("All Posts", 
             href=f"{base_url}{'&' if url_params else '?'}unread=0" if base_url != "/" else "/?unread=0",
             # Mobile-only: HTMX attributes for partial updates
             **({'hx_get': f"{base_url}{'&' if url_params else '?'}unread=0" if base_url != "/" else "/?unread=0",
                'hx_target': Targets.MOBILE_CONTENT,
                'hx_push_url': "true"} if for_mobile else {}),
             role='button'),
           cls='uk-active' if not unread_only else ''),
        Li(A("Unread",
             href=base_url if base_url != "/" else "/",
             # Mobile-only: HTMX attributes for partial updates
             **({'hx_get': base_url if base_url != "/" else "/",
                'hx_target': Targets.MOBILE_CONTENT,
                'hx_push_url': "true"} if for_mobile else {}),
             role='button'),
           cls='uk-active' if unread_only else ''),
        alt=True, cls='ml-auto max-w-40'
    )
```

**Why This Partial Unification Works**:
1. Reduces code duplication for tab generation
2. Makes the mobile/desktop difference explicit and documented
3. Preserves the architectural requirement that mobile needs HTMX while desktop doesn't
4. Single source of truth for URL generation logic

**What NOT to Unify**:
- Feed items must keep separate IDs and targets
- Mobile persistent header vs desktop header remain separate
- Different navigation patterns (full-screen vs column updates)

**Test**: Tab behavior remains identical, but with less code duplication

### Step 7: Complete Route Implementation

**Goal**: Show the complete route structure using all previous steps

**Implementation**:
1. Main index route combining Steps 2-5:

```python
@rt('/')
def index(htmx: HtmxHeaders, sess, feed_id: int = None, unread: bool = True, page: int = 1):
    """Main route using all previous steps"""
    session_id = sess.get('session_id')
    data = PageData(session_id, feed_id, unread, page)  # Step 3
    
    # BACKGROUND WORK
    queue_user_feeds_for_update(session_id)
    
    # HTMX - Use routing from Step 5
    if htmx:  # Step 2 - FastHTML helper
        return route_htmx_fragment(htmx, data)  # Step 5
    
    # FULL PAGE - From Step 5
    return full_page_dual_layout(data)
```

2. Show item route pattern:

```python
@rt('/item/{item_id}')
def show_item(item_id: int, htmx: HtmxHeaders, sess, unread_view: bool = False, feed_id: int = None):
    """Item detail route following same pattern"""
    session_id = sess.get('session_id')
    
    # Prepare item data
    item_data = prepare_item_data(session_id, item_id, feed_id, unread_view)
    
    if not item_data.item:
        if htmx:
            return Alert("Item not found", type='error', cls='m-4')
        else:
            return Redirect("/")  # FastHTML Redirect class
    
    # Mark as read
    mark_item_read_and_refresh(item_data)
    
    # Route response
    if htmx:
        return htmx_item_response(htmx.target, item_data)
    else:
        return full_page_item_response(item_data)
```

**Test**: Routes clearly show decision flow and use all components from previous steps

### Step 8: Handle Out-of-Band Updates Appropriately ✅ **PARTIALLY COMPLETED**

**Goal**: Keep out-of-band swaps where they make architectural sense

**Status**: 🔶 Mobile navigation has been significantly simplified using `hx-preserve`

**What Was Implemented**:
- **Mobile persistent header**: Now uses `hx_preserve="true"` instead of manual OOB swaps
- **Simplified navigation**: Mobile navigation back no longer requires complex OOB updates
- **URL push handling**: Proper URL state management for mobile article navigation

**Current Implementation** (app.py lines 498-502):
```python
# Mobile persistent header with hx-preserve
return Div(
    cls='flex-shrink-0 bg-background border-b z-10 lg:hidden',
    id='mobile-persistent-header',
    hx_preserve="true",  # ✅ New - HTMX preserves state automatically
    onwheel="event.preventDefault(); event.stopPropagation(); return false;"
)
```

**What Still Uses OOB** (appropriate):
- Mobile navigation button swap (hamburger ↔ back arrow) 
- Desktop item list appearance updates when marked read

**Remaining Work**:
- Consider if navigation button swap can use `hx-preserve` approach too

**Test**: Simplified navigation works with `hx-preserve` approach

### Step 9: Keep JavaScript for Simple UI Interactions

**Goal**: Use JavaScript for simple UI state, HTMX for data operations

**Current Reality**: Some JavaScript is appropriate for immediate UI feedback

**What to Keep**:
- Mobile sidebar show/hide (immediate, no server data needed)
- Accordion/dropdown toggles
- Loading indicators

**What to Convert to HTMX**:
- Data operations (adding feeds, marking read/unread)
- Navigation between views
- Form submissions

**Example of Appropriate JavaScript**:
```python
# Mobile sidebar toggle - immediate UI feedback
Button(
    UkIcon('menu'),
    onclick="document.getElementById('mobile-sidebar').removeAttribute('hidden')",
    cls="p-2 rounded border hover:bg-secondary"
)
```

**Example of HTMX Conversion**:
```python
# Adding a feed - server operation
Form(
    Input(name="new_feed_url", placeholder="Enter RSS URL"),
    Button(UkIcon('plus'), type="submit"),
    hx_post="/api/feed/add",
    hx_target="#sidebar",  # or "#mobile-sidebar" based on context
    hx_swap="outerHTML"
)
```

**Why This Balance**:
1. Immediate UI feedback improves user experience
2. Server operations ensure data consistency
3. Clear separation of concerns

**Test**: JavaScript only for UI state, HTMX for data operations

### Step 10: Document the Dual-Layout Architecture

**Goal**: Make the architectural decisions explicit in code comments

**Implementation**:
```python
# =============================================================================
# ARCHITECTURAL DECISIONS
# =============================================================================
# This app uses different HTMX targets for mobile and desktop BY DESIGN:
#
# MOBILE (Single-column, full-screen navigation):
#   - Target: #main-content (entire content area swaps)
#   - Navigation: List view ↔ Article view (full replacement)
#   - Tabs: Use HTMX to preserve header state
#
# DESKTOP (Three-column email interface):
#   - Targets: #desktop-feeds-content (middle), #desktop-item-detail (right)
#   - Navigation: Columns update independently
#   - Tabs: Regular links (full page navigation acceptable)
#
# This is NOT accidental complexity - it reflects fundamental UX differences
# =============================================================================
```

**Documentation in Components**:
```python
def FeedItem(item, for_desktop=False):
    """Feed item component
    
    Args:
        for_desktop: True for desktop layout (targets #desktop-item-detail),
                    False for mobile (targets #main-content)
    
    The different targets are architectural - mobile swaps full screen,
    desktop updates only the detail column.
    """
    # Component implementation...
```

**Test**: Code clearly documents why mobile and desktop differ

## Final Architecture: Explicit Dual-Layout Design

After implementation, the code should clearly show the mobile/desktop split:

```python
# =============================================================================
# CONFIGURATION - Explicit about dual layouts
# =============================================================================
class Targets:
    """HTMX targets for mobile and desktop layouts"""
    MOBILE_CONTENT = '#main-content'  # Full-screen swapping
    DESKTOP_FEEDS = '#desktop-feeds-content'  # Middle column only
    DESKTOP_DETAIL = '#desktop-item-detail'  # Right column only

# =============================================================================
# LAYOUT HANDLERS - Separate mobile and desktop logic
# =============================================================================
class MobileHandlers: ...  # Single-column, full-screen
class DesktopHandlers: ...  # Three-column email interface

# =============================================================================
# ROUTES - Clear architectural decisions
# =============================================================================
@rt('/')
def index(htmx: HtmxHeaders, sess, **params):
    """Main route - explicit about layout differences"""
    session_id = sess.get('session_id')
    data = PageData(session_id, **params)
    
    # HTMX - Route to layout-specific handlers
    if htmx:
        return route_htmx_fragment(htmx, data)
    
    # FULL PAGE - Both layouts present
    return full_page_dual_layout(data)

# =============================================================================
# COMPONENTS - Accept the for_desktop parameter
# =============================================================================
def FeedItem(item, for_desktop=False):
    """Component that explicitly handles layout differences"""
    # Different targets and IDs by design
    target = Targets.DESKTOP_DETAIL if for_desktop else Targets.MOBILE_CONTENT
    item_id = f"{'desktop-' if for_desktop else 'mobile-'}feed-item-{item['id']}"
    # Component implementation...
```

### Key Architectural Principles:

1. **Embrace the Difference**: Mobile and desktop are fundamentally different UX paradigms
2. **Make it Explicit**: Clear separation between mobile and desktop handlers
3. **Document Why**: Comments explain architectural decisions
4. **FastHTML Benefits**: Use `htmx: HtmxHeaders` and automatic fragment handling
5. **Keep What Works**: Current `for_desktop` pattern is already clean

## Current Implementation Status

### ✅ **COMPLETED**:
1. **Configuration Constants** - All targets, IDs, and styling classes extracted
2. **MINIMAL_MODE Support** - Fast testing with minimal database
3. **Mobile Navigation Simplification** - Uses `hx-preserve` instead of complex OOB swaps
4. **Component Pattern** - `for_desktop` parameter working well

### 🔶 **PARTIALLY COMPLETED**:
1. **Out-of-Band Updates** - Simplified but still some OOB usage
2. **Tab Container Unification** - Mobile navigation improved but duplication remains

### ❌ **NOT YET IMPLEMENTED**:
1. **FastHTML HTMX Helpers** - Still using manual header parsing
2. **PageData Layer** - No centralized data preparation yet
3. **Handler Architecture** - No MobileHandlers/DesktopHandlers classes
4. **Route Refactoring** - Routes still have inline logic

## Success Criteria (Revised)

- ✅ **Configuration visible**: All constants extracted to top of file
- ❌ **FastHTML integration**: Need to implement `htmx: HtmxHeaders` parameter
- ✅ **Mobile navigation**: Simplified with `hx-preserve` 
- ❌ **Handler separation**: Need explicit mobile/desktop handler classes
- ✅ **Component pattern**: `for_desktop` parameter is clear and working
- 🔶 **Appropriate technology use**: Some JavaScript kept, HTMX for data ops

## Testing Approach (Revised)

1. **Constants test**: Verify all magic strings replaced with named constants (Step 1)
2. **Layout separation test**: Verify mobile and desktop handlers are clearly separated
3. **Target mapping test**: Each HTMX target maps to exactly one handler
4. **Documentation test**: Code includes comments explaining layout differences
5. **Current functionality test**: All existing tests continue to pass
6. **FastHTML integration test**: `htmx: HtmxHeaders` parameter works correctly