# Plan to Restore Missing Header Buttons

## Visual Comparison

### Production Version (main branch)
The production header at https://rss-reader-highlight.fly.dev/ shows:
- Left: Hamburger menu button + "All Feeds" title
- Right: Three action buttons:
  - 📋 "All Posts" button (list icon)
  - ✉️ "Unread" button (mail icon)
  - 🔍 "Search" button (magnifying glass icon)

### Current Refactored Version
The current header only shows:
- Left: Hamburger/Back button + Feed name
- Right: (Empty - missing action buttons!)

## Missing Components Analysis

### 1. Visibility Toggle Buttons (All Posts/Unread)

From `main` branch's `UnifiedChrome` function:
```python
# Action buttons - with proper layout targeting
action_buttons = Div(
    cls="flex items-center space-x-2",
    id=f"{'mobile' if for_mobile else 'desktop'}-icon-bar"
)(
    Button(
        UkIcon('list'),
        hx_get=all_posts_url,
        hx_target=target,
        hx_push_url="true",
        cls="p-2 rounded hover:bg-secondary",
        title="All Posts"
    ),
    Button(
        UkIcon('mail'),
        hx_get=unread_url,
        hx_target=target,
        hx_push_url="true",
        cls="p-2 rounded hover:bg-secondary",
        title="Unread"
    ),
    Button(
        UkIcon('search'),
        hx_on_click=f"var bar = document.getElementById('{'mobile' if for_mobile else 'desktop'}-icon-bar'); var search = document.getElementById('{'mobile' if for_mobile else 'desktop'}-search-bar'); bar.style.display='none'; search.style.display='flex'; search.querySelector('input').focus();",
        cls="p-2 rounded hover:bg-secondary",
        title="Search"
    )
)
```

URLs were built based on current context:
```python
# Build URLs for action buttons
all_posts_url = f"/?feed_id={feed_id}&unread=0" if feed_id else "/?unread=0"
unread_url = f"/?feed_id={feed_id}" if feed_id else "/"
```

### 2. Expandable Search Bar

From `main` branch:
```python
# Expandable search bar
search_bar = Div(
    cls="flex items-center flex-1 ml-4",
    id=f"{'mobile' if for_mobile else 'desktop'}-search-bar",
    style="display: none;"
)(
    Div(cls="uk-inline w-full")(
        Input(
            placeholder="Search posts",
            cls="w-full pr-8",
            id=f"{'mobile' if for_mobile else 'desktop'}-search-input",
            uk_filter_control=""
        ),
        Button(
            UkIcon('x', cls="w-4 h-4"),
            hx_on_click=f"var bar = document.getElementById('{'mobile' if for_mobile else 'desktop'}-icon-bar'); var search = document.getElementById('{'mobile' if for_mobile else 'desktop'}-search-bar'); search.style.display='none'; bar.style.display='flex';",
            cls="uk-form-icon uk-form-icon-flip p-1 hover:text-red-500 cursor-pointer absolute right-1 top-1/2 -translate-y-1/2",
            title="Close search"
        )
    )
)
```

### 3. Click Outside Handler

From `main` branch:
```javascript
// Click outside handler script
const searchBar = document.getElementById('{'mobile' if for_mobile else 'desktop'}-search-bar');
const iconBar = document.getElementById('{'mobile' if for_mobile else 'desktop'}-icon-bar');
const searchInput = document.getElementById('{'mobile' if for_mobile else 'desktop'}-search-input');

document.addEventListener('click', function(event) {
    if (searchBar && iconBar) {
        const isSearchVisible = searchBar.style.display !== 'none';
        const clickedInsideSearch = searchBar.contains(event.target);
        const clickedSearchButton = event.target.closest('button[title="Search"]');

        if (isSearchVisible && !clickedInsideSearch && !clickedSearchButton) {
            searchBar.style.display = 'none';
            iconBar.style.display = 'flex';
        }
    }
});
```

## Implementation Plan for Unified Layout

### Step 1: Modify the `three_pane_layout` function

Current structure (lines 144-176):
```python
def three_pane_layout(data, detail_content=None):
    """Unified three-pane layout for all viewports"""
    feed_name = data.feed_name if hasattr(data, 'feed_name') else "All Feeds"

    # Create universal header for both mobile and desktop
    universal_header = Div(
        id="universal-header",
        cls="bg-background border-b p-4"
    )(
        Div(cls="flex items-center gap-4")(
            # Button container with overlapping buttons
            Div(cls="relative")(
                # Hamburger menu button
                # Back button
            ),
            # Feed name/title
            H1(feed_name, cls="text-lg font-semibold")
        )
    )
```

### Step 2: Add Action Buttons Section

Add after the feed name (line 174), before closing the flex container:

```python
# Add flex-1 to push buttons to the right
H1(feed_name, cls="text-lg font-semibold flex-1"),

# Action buttons container
Div(
    cls="flex items-center space-x-2",
    id="icon-bar"
)(
    Button(
        UkIcon('list'),
        hx_get=f"/?feed_id={data.feed_id}&unread=0" if data.feed_id else "/?unread=0",
        hx_target="#summary",
        hx_push_url="true",
        cls="p-2 rounded hover:bg-secondary",
        title="All Posts",
        data_testid="all-posts-btn"
    ),
    Button(
        UkIcon('mail'),
        hx_get=f"/?feed_id={data.feed_id}" if data.feed_id else "/",
        hx_target="#summary",
        hx_push_url="true",
        cls="p-2 rounded hover:bg-secondary",
        title="Unread",
        data_testid="unread-btn"
    ),
    Button(
        UkIcon('search'),
        onclick="var bar = document.getElementById('icon-bar'); var search = document.getElementById('search-bar'); bar.style.display='none'; search.style.display='flex'; search.querySelector('input').focus();",
        cls="p-2 rounded hover:bg-secondary",
        title="Search",
        data_testid="search-btn"
    )
),

# Expandable search bar (hidden by default)
Div(
    cls="items-center flex-1 ml-4",
    id="search-bar",
    style="display: none;"
)(
    Div(cls="uk-inline w-full")(
        Input(
            placeholder="Search posts",
            cls="w-full pr-8",
            id="search-input",
            uk_filter_control=""
        ),
        Button(
            UkIcon('x', cls="w-4 h-4"),
            onclick="var bar = document.getElementById('icon-bar'); var search = document.getElementById('search-bar'); search.style.display='none'; bar.style.display='flex';",
            cls="uk-form-icon uk-form-icon-flip p-1 hover:text-red-500 cursor-pointer absolute right-1 top-1/2 -translate-y-1/2",
            title="Close search"
        )
    )
)
```

### Step 3: Add Click-Outside Handler

Add a Script element to handle click-outside for search bar. This should be added to the app initialization or as part of the viewport_styles():

```javascript
document.addEventListener('DOMContentLoaded', function() {
    document.addEventListener('click', function(event) {
        const searchBar = document.getElementById('search-bar');
        const iconBar = document.getElementById('icon-bar');

        if (searchBar && iconBar) {
            const isSearchVisible = searchBar.style.display !== 'none';
            const clickedInsideSearch = searchBar.contains(event.target);
            const clickedSearchButton = event.target.closest('button[title="Search"]');

            if (isSearchVisible && !clickedInsideSearch && !clickedSearchButton) {
                searchBar.style.display = 'none';
                iconBar.style.display = 'flex';
            }
        }
    });
});
```

### Step 4: Update CSS for Responsive Behavior

Add to `viewport_styles()` function:

```css
/* Icon bar and search bar responsive behavior */
@media (max-width: 1023px) {
    /* Mobile: Show icon bar by default */
    #icon-bar {
        display: flex !important;
    }

    /* Mobile: Hide search bar by default, show via JS */
    #search-bar {
        display: none;
    }

    /* When search is active */
    #search-bar[style*="display: flex"] {
        display: flex !important;
    }
}

@media (min-width: 1024px) {
    /* Desktop: Same behavior as mobile for consistency */
    #icon-bar {
        display: flex !important;
    }

    #search-bar {
        display: none;
    }
}
```

### Step 5: Visual Indicator for Active View

Add visual feedback to show which view is active (All Posts vs Unread):

```python
# In the action buttons section, add conditional styling
Button(
    UkIcon('list'),
    hx_get=f"/?feed_id={data.feed_id}&unread=0" if data.feed_id else "/?unread=0",
    hx_target="#summary",
    hx_push_url="true",
    cls=f"p-2 rounded hover:bg-secondary {'bg-secondary' if not data.unread else ''}",
    title="All Posts",
    data_testid="all-posts-btn"
),
Button(
    UkIcon('mail'),
    hx_get=f"/?feed_id={data.feed_id}" if data.feed_id else "/",
    hx_target="#summary",
    hx_push_url="true",
    cls=f"p-2 rounded hover:bg-secondary {'bg-secondary' if data.unread else ''}",
    title="Unread",
    data_testid="unread-btn"
)
```

## Testing Requirements

After implementation, verify:

1. **Desktop behavior**:
   - All three buttons visible in header
   - Clicking "All Posts" shows all items (read and unread)
   - Clicking "Unread" shows only unread items
   - Search expands and replaces icon bar
   - Clicking outside search closes it

2. **Mobile behavior**:
   - Same button functionality as desktop
   - Buttons remain accessible in both list and article views
   - Search works correctly on mobile viewport

3. **State preservation**:
   - Current feed context maintained when toggling views
   - URL parameters correctly updated
   - Visual indicators show active view

## Files to Modify

1. `/home/kuitang/git/rss-reader-highlight/app/main.py`:
   - Update `three_pane_layout` function (lines 144-176)
   - Add click-outside handler to app initialization scripts
   - Update `viewport_styles` if needed for CSS adjustments

## Expected Outcome

The header will match production with:
- Hamburger/Back button (left)
- Feed name (center-left)
- Action buttons: All Posts | Unread | Search (right)
- Expandable search that replaces the action buttons when activated

This maintains the unified layout architecture while restoring the missing functionality that users expect from the production version.