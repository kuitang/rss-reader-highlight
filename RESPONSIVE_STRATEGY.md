# RSS Reader - Test Fixing Strategy & Progress

## 🚀 Quick Start

```bash
# Start server (in one terminal)
source venv/bin/activate && MINIMAL_MODE=true python -m app

# Run all UI tests (in another terminal)
source venv/bin/activate && python -m pytest tests/ui/ -xvs

# Run specific test
python -m pytest tests/ui/test_ui_fixes.py::TestBackButtonFunctionality::test_back_button_mobile_navigation -xvs
```

## 📊 Test Status Summary

**Total UI Tests**: 91
- ✅ **Passing**: 75
- ❌ **Failing**: 16
- ⏭️ **Skipped**: 10 (need full database)

### Critical Failures to Fix (in order):
1. ❌ Mobile back button navigation (partially fixed, see below)
2. ❌ Main layout visibility on mobile article view
3. ❌ Dark mode test syntax error
4. ❌ Multiple tests timing out on mobile
5. ❌ Sidebar visibility test expectations wrong
6. ❌ Test selector issues (div#item-detail → #article-detail)

---

## ✅ COMPLETED FIXES

### 1. Nav Button Name Attribute Issue (FIXED ✅)
**Commits**: e0d0e9f, 50a0144

**Problem**: FastHTML auto-generates `name` attribute from `id`, causing form submission issues.

**Root Cause**:
```python
# FastHTML does this automatically:
Button("Test", id="my-btn")
# Outputs: <button id="my-btn" name="my-btn">  # ← Auto-added!
```

**Solution**: Add explicit `name=""` to prevent auto-generation:
```python
nav_button_attrs = {
    "id": ElementIDs.NAV_BUTTON,
    "name": "",  # ← Prevents FastHTML from auto-generating
    ...
}
```

**Tests Now Passing**:
- `TestHamburgerMenuHTMX::test_hamburger_no_form_submission` ✅
- `TestHamburgerMenuHTMX::test_search_nav_button_no_form_submission` ✅

**Files Modified**:
- `/home/kuitang/git/rss-reader-highlight/app/main.py` (lines 1691, 1758)

---

## 🔧 IN PROGRESS

### 2. Mobile Back Button Navigation (PARTIALLY FIXED)

**Test**: `tests/ui/test_ui_fixes.py::TestBackButtonFunctionality::test_back_button_mobile_navigation`

**Status**: HTTP request works, but classes not removed ❌

**What Works**:
- ✅ Back button makes HTTP request (verified in server logs)
- ✅ `htmx.process()` successfully registers HTMX attributes
- ✅ No duplicate event handlers anymore

**What Doesn't Work**:
- ❌ `active` class not removed from `#article-detail`
- ❌ `article-view` class not removed from `#feed-list`

**Root Causes Discovered**:

1. **HTMX Attribute Registration** (FIXED ✅):
   - Must call `htmx.process(element)` AFTER adding hx-* attributes
   - Must NOT call `htmx.process(element)` after removing attributes (un-registers behavior)

2. **Duplicate Event Handlers** (FIXED ✅):
   - `htmx-config.js` (lines 62-91) and `main.js` (lines 217-227) both handled afterSwap
   - Race condition: first handler removed class, second checked for it and did nothing
   - Solution: Removed duplicate in main.js

3. **Current Issue** (NOT FIXED ❌):
   - `hideArticle()` is called by htmx-config.js handler
   - Classes ARE removed
   - But something is adding them back or they're not persisting
   - Need to debug timing/order of HTMX swaps vs class changes

**Files Modified (uncommitted)**:
- `/home/kuitang/git/rss-reader-highlight/static/js/main.js`:
  - Line 73: Added `htmx.process(navButton)` after setting attributes
  - Line 109: Removed `htmx.process(navButton)` after removing attributes (was breaking it)
  - Lines 218-220: Removed duplicate afterSwap handler
  - Lines 85-107: Added debug logging to track class removal

**Next Steps**:
1. Use Playwright MCP subagent to watch class changes in real-time
2. Check if HTMX afterSettle is re-adding classes
3. Consider using server-side OOB swaps instead of client-side manipulation
4. May need to add hx-swap-oob to feed-list response to send nav button state

**Debug Command**:
```python
# Use subagent with Playwright MCP to debug:
Task(
    subagent_type="general-purpose",
    description="Debug back button classes",
    prompt="""
    At http://localhost:8080, mobile viewport (390x844):
    1. Inject MutationObserver to watch #article-detail class changes
    2. Click feed item → Click back button
    3. Report exact sequence of class additions/removals
    4. Check if classes removed then re-added
    5. Check console for hideArticle() debug logs
    """
)
```

---

## ❌ REMAINING ISSUES

### 3. Main Layout Visibility on Mobile
**Tests Failing**:
- `test_mobile_comprehensive_workflow`
- `test_responsive_layout_switching`

**Issue**: `#main-layout` stays visible (display: flex) when article is active on mobile. Should be hidden.

**Expected**: `#main-layout` display:none when `#article-detail.active` on mobile
**Actual**: `#main-layout` display:flex (always visible)

**Fix Needed**: Add CSS rule or HTMX swap to hide main-layout on mobile article view

---

### 4. Dark Mode Test Syntax Error
**Test**: `tests/ui/test_dark_mode.py::test_dark_mode_toggle_and_css_variables`

**Error**: `SyntaxError: Illegal return statement at eval (<anonymous>)`

**Root Cause**: Test is using `page.evaluate()` with a return statement outside function context.

**Fix**: Wrap evaluate code in IIFE:
```python
# Bad:
page.evaluate("return document.body.classList")

# Good:
page.evaluate("() => document.body.classList")
```

**File to Fix**: `/home/kuitang/git/rss-reader-highlight/tests/ui/test_dark_mode.py`

---

### 5. Mobile Flow Timeouts
**Tests Failing** (all timeout at 2000ms):
- `test_mobile_post_navigation_htmx`
- `test_mobile_feed_filter_preserved`
- `test_mobile_feed_title_persistence_after_article_navigation`

**Issue**: Using `page.wait_for_function()` with 2000ms timeout - too short for HTMX.

**Fix**: Use `wait_for_htmx_complete()` helper instead:
```python
# Bad:
page.wait_for_function("...", timeout=2000)

# Good:
wait_for_htmx_complete(page, timeout=5000)
```

---

### 6. Sidebar Visibility Test Issues
**Test**: `test_mobile_sidebar_and_navigation_flow`

**Issue**: Test expects sidebar to be `hidden` (CSS display:none), but it's positioned off-screen with CSS.

**Current Implementation**:
```css
/* Mobile sidebar is hidden via positioning, not display:none */
@media (max-width: 1023px) {
  #sidebar {
    position: fixed;
    left: -390px;  /* Off-screen */
    transform: translateX(0);
  }
  #sidebar.open {
    left: 0;  /* Slide in */
  }
}
```

**Test Expectation** (WRONG):
```python
expect(page.locator("#sidebar")).to_be_hidden()  # Fails - sidebar is visible, just positioned off-screen
```

**Fix Options**:
1. Update test to check for `open` class instead
2. OR change CSS to use display:none instead of positioning

---

### 7. Test Selector Issues
**Test**: `test_basic_functionality_flow`

**Error**: `waiting for locator("div#item-detail")` - element not found

**Issue**: Old selector `div#item-detail` doesn't exist. Should be `#article-detail`.

**Fix**: Update test selectors:
```python
# Bad:
page.locator("div#item-detail")

# Good:
page.locator("#article-detail")
```

**File to Fix**: `/home/kuitang/git/rss-reader-highlight/tests/ui/test_working_regression.py`

---

### 8. HTMX Mobile Handlers Routing
**Test**: `test_mobile_handlers_routing`

**Error**: `Timeout waiting for locator("#sidebar button[hx-on-click*='setAttribute']")`

**Issue**: Test looking for specific HTMX attribute that may not exist with current implementation.

**Fix**: Review what the test is trying to verify and update selector or implementation.

---

## 🔍 DEBUG PROCEDURES

### Using Subagents for Debugging

**ALWAYS use Playwright MCP subagent for interactive debugging:**

```python
Task(
    subagent_type="general-purpose",
    description="Debug UI issue",
    prompt="""
    At http://localhost:8080:

    1. Open in viewport: {"width": 390, "height": 844} (mobile)
    2. [Specific steps to reproduce]
    3. Use Playwright MCP to:
       - Inject JavaScript to monitor events
       - Check element attributes and classes
       - Take screenshots
       - Report console logs

    Return detailed report of:
    - Exact element states
    - Console output
    - Screenshots if helpful
    """
)
```

**Key Debugging Commands**:

1. **Check HTMX Events**:
```javascript
// Inject event logger
htmx.logger = function(elt, event, data) {
    console.log(event, data);
}
```

2. **Watch Class Changes**:
```javascript
const observer = new MutationObserver(mutations => {
    mutations.forEach(m => {
        if (m.attributeName === 'class') {
            console.log('Class changed:', m.target.className);
        }
    });
});
observer.observe(document.getElementById('article-detail'), {attributes: true});
```

3. **Check HTMX Attributes**:
```javascript
const btn = document.getElementById('nav-button');
console.log({
    hasHxGet: btn.hasAttribute('hx-get'),
    hxGet: btn.getAttribute('hx-get'),
    hxTarget: btn.getAttribute('hx-target')
});
```

---

## 🏗️ ARCHITECTURE NOTES

### Current Structure (Unified Responsive)

```
#app-container
  #sidebar (responsive via CSS positioning)
    - Mobile: fixed, left: -100%, slides in with .open class
    - Desktop: static, always visible

  #sidebar-overlay (mobile only)
    - Shows when sidebar.open on mobile

  #main-layout
    #chrome-container (hx-preserve="true")
      #nav-button (mobile only via CSS)
      #feed-name
      #icon-bar
      #search-bar (absolute positioned overlay)

    #content-area
      #feed-list
      #article-detail
        - Mobile: fixed fullscreen with .active class
        - Desktop: static side panel
```

### Key Files

**Python Backend**:
- `/home/kuitang/git/rss-reader-highlight/app/main.py` - Main app, chrome components, HTMX logic

**JavaScript**:
- `/home/kuitang/git/rss-reader-highlight/static/js/main.js` - Main JS, showArticle(), hideArticle()
- `/home/kuitang/git/rss-reader-highlight/static/js/htmx-config.js` - HTMX event handlers, mobile navigation

**CSS**:
- `/home/kuitang/git/rss-reader-highlight/static/css/main.css` - Responsive styles, mobile/desktop breakpoints

**Tests**:
- `/home/kuitang/git/rss-reader-highlight/tests/ui/test_ui_fixes.py` - Critical UI fixes
- `/home/kuitang/git/rss-reader-highlight/tests/ui/test_mobile_flows.py` - Mobile-specific tests
- `/home/kuitang/git/rss-reader-highlight/tests/ui/test_comprehensive_regression.py` - Full regression suite

### Mobile Navigation State Machine

```
[Feed List View]
  nav-button: onclick="toggleSidebar()", icon="menu"
  article-detail: no .active class
  feed-list: no .article-view class

  ↓ (Click feed item - HTMX request)

[Article View]
  nav-button: hx-get="/", hx-target="#feed-list", icon="arrow-left"
  article-detail: has .active class
  feed-list: has .article-view class

  ↓ (Click back button - HTMX request)

[Feed List View]
  (Should return to initial state, but classes not clearing!)
```

---

## 🎯 NEXT SESSION ACTION PLAN

### Priority 1: Fix Back Button (Current Focus)

**Immediate Debug Steps**:
1. Start server: `source venv/bin/activate && MINIMAL_MODE=true python -m app`
2. Run test with console output: `python -m pytest tests/ui/test_ui_fixes.py::TestBackButtonFunctionality::test_back_button_mobile_navigation -xvs`
3. Use Playwright MCP subagent to watch class changes during back navigation
4. Check server logs to confirm back request succeeds
5. Verify hideArticle() is called (check console logs added at line 85)

**Potential Solutions to Try**:
1. Check if afterSettle is re-adding classes
2. Use server-side OOB swap for nav button instead of client-side manipulation
3. Add explicit class removal in HTMX response
4. Check timing - may need to delay class removal until after swap completes

### Priority 2: Fix Other Critical Tests

1. **Main Layout Visibility**: Add CSS to hide #main-layout when article active on mobile
2. **Dark Mode Test**: Fix evaluate syntax in test
3. **Mobile Timeouts**: Replace wait_for_function with wait_for_htmx_complete
4. **Selector Updates**: Change div#item-detail → #article-detail

### Priority 3: Update Tests for New Architecture

Many tests expect old dual-layout (mobile-* and desktop-* elements). Need to:
1. Update all selectors to use unified element IDs
2. Remove viewport-specific checks where not needed
3. Update visibility expectations (CSS positioning vs display:none)

---

## 💡 KEY LEARNINGS

### FastHTML Gotchas

1. **Auto-Generated Attributes**: FastHTML adds `name="<id>"` automatically. Use `name=""` to prevent.
2. **Button Components**: Use explicit attributes dict to control output.

### HTMX Best Practices

1. **Dynamic Attributes**: Call `htmx.process(element)` after adding hx-* attributes
2. **Removing Attributes**: DON'T call `htmx.process()` after removing - it un-registers behavior
3. **Event Handlers**: Check for duplicate handlers in multiple JS files
4. **OOB Swaps**: Consider server-side swaps for complex state changes instead of client-side JS

### Testing Best Practices

1. **Wait Strategies**: Always use `wait_for_htmx_complete()`, never `time.sleep()` or short timeouts
2. **Selectors**: Use semantic selectors (IDs, roles) not styling classes
3. **Subagents**: Use Playwright MCP for complex debugging - don't guess, observe!
4. **Architecture**: Understand if element is hidden via display:none or positioning before writing assertions

---

## 📝 COMMIT LOG

**Committed**:
- e0d0e9f: Fix: Prevent FastHTML from auto-generating 'name' attributes on nav buttons
- 50a0144: Docs: Update RESPONSIVE_STRATEGY.md with nav button fix

**Uncommitted Changes**:
- static/js/main.js: Added htmx.process() calls, removed duplicate handler, added debug logging
- RESPONSIVE_STRATEGY.md: This comprehensive update

**Next Commit**: Once back button fully working, commit with message:
```
Fix: Mobile back button navigation with htmx.process()

- Add htmx.process() after setting hx-* attributes in showArticle()
- Remove htmx.process() call in hideArticle() (was un-registering)
- Remove duplicate afterSwap handler causing race condition
- Back button now makes HTTP request correctly

Tests passing:
- [List tests that pass]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## 🔄 TEST RUNNING GUIDE

```bash
# Run ALL tests (takes ~2 minutes)
python -m pytest tests/ui/ -xvs

# Run SPECIFIC test file
python -m pytest tests/ui/test_ui_fixes.py -xvs

# Run SPECIFIC test
python -m pytest tests/ui/test_ui_fixes.py::TestBackButtonFunctionality -xvs

# Run with match pattern
python -m pytest tests/ui/ -k "mobile" -xvs

# Skip tests needing full DB
python -m pytest tests/ui/ -m "not need_full_db" -xvs

# Check test output location
cat all_tests.txt  # If it exists
```

**Server Management**:
```bash
# Kill all Python servers
pkill -9 -f "python.*app"

# Start fresh
source venv/bin/activate && MINIMAL_MODE=true python -m app

# Check server
curl http://localhost:8080 | head -5
```

---

## END OF STRATEGY DOCUMENT

**Last Updated**: 2025-10-04 20:25 UTC
**Current Session Tokens Used**: ~121k/200k
**Status**: Back button partially fixed, 15 tests remaining

**On Next Session Start**:
1. Read this file completely
2. Start server
3. Focus on back button debug using Playwright MCP
4. Commit once working
5. Move to next critical failure
