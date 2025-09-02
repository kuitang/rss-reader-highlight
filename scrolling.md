# Mobile Scroll Restoration Solution & Advanced HTMX Techniques

## Executive Summary

This document details our scroll restoration solution for the RSS reader mobile interface and explores advanced HTMX techniques that could improve both scrolling and other interactivity challenges in the application.

## The Problem We Solved

### Core Challenge
- **Custom scroll container**: Our `#main-content` div uses `overflow-y:auto` instead of the viewport scroll
- **HTMX limitation**: HTMX's built-in history management only handles window scroll, not custom containers
- **Mobile UX requirement**: Users expect scroll position to be preserved when navigating back from articles

### Why It Was Hard
1. HTMX automatically saves/restores window scroll position but ignores custom containers
2. FastHTML's abstractions (Python → HTML attribute conversion) added debugging complexity
3. Previous complex JavaScript solutions with SessionStorage failed due to timing issues

## Our Solution: URL-Based Scroll State

### Implementation Overview
```javascript
// Capture scroll position when navigating to article
htmx.on('htmx:configRequest', function(evt) {
    if (window.innerWidth < 1024 && evt.detail.path?.includes('/item/')) {
        const mainContent = document.getElementById('main-content');
        if (mainContent) {
            evt.detail.parameters._scroll = Math.round(mainContent.scrollTop);
        }
    }
});

// Restore scroll position when returning to list
htmx.on('htmx:afterSwap', function(evt) {
    if (window.innerWidth < 1024 && evt.detail.target?.id === 'main-content') {
        const match = evt.detail.pathInfo?.requestPath?.match(/_scroll=(\d+)/);
        if (match) {
            setTimeout(() => {
                const mainContent = document.getElementById('main-content');
                if (mainContent) mainContent.scrollTop = parseInt(match[1]);
            }, 50);
        }
    }
});
```

### Python/FastHTML Side
```python
@rt('/item/{item_id}')
def show_item(item_id: int, _scroll: int = None):
    # FastHTML automatically extracts _scroll parameter
    back_url = "/"
    if _scroll:
        back_url += f"?_scroll={_scroll}"
    # Back button includes scroll position
```

### Key Insights
- **URL parameters are reliable**: Work with browser history, bookmarks, and sharing
- **Underscore prefix convention**: `_scroll` indicates a "hidden" parameter
- **HTMX event system is powerful**: `configRequest` allows parameter injection before request
- **FastHTML parameter extraction**: Seamlessly converts URL params to Python function args

## Advanced HTMX Techniques We Could Use

### 1. Cleaner Implementation with `hx-vals` and `hx-on`

#### Current Approach (Global Event Listeners)
```javascript
htmx.on('htmx:configRequest', function(evt) { /* ... */ });
```

#### Better: Inline with `hx-on`
```html
<li class="feed-item"
    hx-get="/item/123"
    hx-on:htmx:config-request="
        if (window.innerWidth < 1024) {
            event.detail.parameters._scroll = 
                document.getElementById('main-content').scrollTop;
        }
    ">
```

#### Alternative: Dynamic `hx-vals`
```html
<li class="feed-item"
    hx-get="/item/123"
    hx-vals='js:{_scroll: document.getElementById("main-content").scrollTop}'
    hx-trigger="click">
```

**Benefits:**
- **Locality of Behavior**: Logic lives with the element
- **Easier debugging**: See behavior in HTML inspector
- **No global state**: Each element self-contained

### 2. Morphing for State Preservation

#### Install Idiomorph Extension
```html
<script src="https://unpkg.com/idiomorph/dist/idiomorph-ext.min.js"></script>
<body hx-ext="morph">
```

#### Use Morphing Swaps
```python
# In FastHTML
Div(
    hx_swap="morph:innerHTML",  # Instead of innerHTML
    id="main-content"
)
```

**What Morphing Could Help With:**
- **Form inputs**: Preserve focus, cursor position, and text selection
- **Video/audio state**: Keep playback position during updates
- **Expanded/collapsed states**: Maintain UI toggles
- **Animation continuity**: Smoother transitions

**Limitations for Scroll:**
- Idiomorph has open issue #26 for scroll preservation in custom containers
- Would need `im-preserve='true'` attribute + custom JavaScript

### 3. `hx-preserve` for Stateful Components

```html
<!-- Video player that survives content swaps -->
<video id="intro-video" hx-preserve="true">
    <source src="intro.mp4">
</video>

<!-- Complex chart that shouldn't re-render -->
<div id="analytics-chart" hx-preserve="true">
    <!-- D3.js visualization -->
</div>
```

**Use Cases in RSS Reader:**
- Preserve folder expand/collapse state
- Keep "Add Feed" form populated during navigation
- Maintain filter/sort selections

### 4. Scroll Modifiers for Controlled Navigation

```python
# FastHTML syntax
Button(
    "Load More",
    hx_get="/api/feeds/page/2",
    hx_swap="beforeend scroll:#main-content:bottom"
)
```

**Scroll Options:**
- `scroll:top` / `scroll:bottom` - Jump to position
- `show:top` / `show:bottom` - Scroll into view
- `scroll:#element:top` - Target specific container

### 5. Combined Approach for Perfect Scroll

```html
<!-- Feed item with all techniques combined -->
<li id="item-123"
    class="feed-item"
    hx-get="/item/123"
    hx-trigger="click"
    hx-target="#main-content"
    hx-swap="morph:innerHTML"
    hx-vals='js:{
        _scroll: document.getElementById("main-content").scrollTop,
        _expanded: Array.from(document.querySelectorAll(".folder.expanded"))
                       .map(f => f.id)
    }'
    hx-on:htmx:after-swap="
        // Restore any custom state after morphing
        const expanded = event.detail.requestConfig.parameters._expanded;
        if (expanded) {
            expanded.forEach(id => 
                document.getElementById(id)?.classList.add('expanded')
            );
        }
    ">
    Article Title
</li>
```

## Recommendations for Our App

### Immediate Improvements
1. **Add Idiomorph** for smoother updates (especially feed list refreshes)
2. **Use `hx-preserve`** on the search box and filter controls
3. **Convert to `hx-on`** for better code organization

### Future Enhancements
1. **Capture more state** in URL params:
   - Folder expansion: `_folders=folder1,folder2`
   - Search query: `_search=keyword`
   - Sort order: `_sort=date-desc`

2. **Progressive Enhancement Pattern**:
   ```python
   # FastHTML component
   def FeedItem(item, session_id):
       return Li(
           # Content
           Div(item['title']),
           # Inline behavior
           hx_get=f"/item/{item['id']}",
           hx_on__config_request="captureScroll(event)",
           hx_on__after_swap="restoreState(event)",
           cls="feed-item"
       )
   ```

3. **State Management Library**:
   ```javascript
   // Small state manager for HTMX apps
   const AppState = {
       capture() {
           return {
               scroll: document.getElementById('main-content').scrollTop,
               expanded: this.getExpandedFolders(),
               filters: this.getActiveFilters()
           };
       },
       restore(state) {
           // Restore each piece of state
       }
   };
   ```

## Lessons Learned

### What Worked
- **URL parameters** for critical state (scroll position)
- **HTMX events** for intercepting/modifying requests
- **FastHTML parameter extraction** for clean Python code
- **Simple solutions** over complex state management

### What Didn't Work
- **SessionStorage/localStorage**: Race conditions with HTMX swaps
- **Complex JavaScript state machines**: Over-engineered for the problem
- **Modifying DOM attributes after click**: HTMX already captured original values

### FastHTML vs Plain HTMX Trade-offs

**FastHTML Benefits:**
- Python-first development
- Automatic parameter extraction
- Clean routing decorators
- Built-in session management

**FastHTML Limitations:**
- No special scroll handling helpers
- Limited HTMX configuration options
- Must write raw JavaScript for advanced features
- Debugging through Python → HTML transformation

## Conclusion

Our scroll solution is elegant and works reliably. While advanced HTMX features like morphing and `hx-on` could make the code cleaner, the fundamental challenge (custom container scroll) would remain. The URL-based approach we implemented is actually a best practice that works with browser history, bookmarks, and sharing—making it superior to many "modern" SPA solutions.

### Next Steps
1. Consider adding Idiomorph for smoother feed updates
2. Migrate global event handlers to `hx-on` attributes
3. Document state preservation patterns for future features
4. Create reusable FastHTML components with built-in scroll handling