# Viewport & Padding Fixes Summary

**Date:** 2025-10-11
**Branch:** br/refactor-spec

---

## 🐛 **BUGS FIXED**

### **Bug #1: Mobile Has Too Much Horizontal Padding**

**Problem:**
- Mobile feed list had 16px horizontal padding (`px-4`)
- Production has 0px horizontal padding
- Made content area narrower than it should be

**Root Cause:**
```css
/* BEFORE (wrong): */
#feed-list: "h-full overflow-y-auto px-4 lg:border-r"
/* px-4 applied on ALL viewports including mobile */

#article-detail: "... max-lg:p-4 ..."
/* p-4 applied top/bottom/left/right on mobile */
```

**Fix:**
```css
/* AFTER (correct): */
#feed-list: "h-full overflow-y-auto lg:px-4 lg:border-r"
/* px-4 only on desktop (lg:), mobile has 0px */

#article-detail: "... max-lg:px-4 ..."
/* Only horizontal padding on mobile, not vertical */
```

**Result:**
- Mobile: Feed list has 0px horizontal padding ✅
- Mobile: Article has 16px horizontal padding ✅
- Desktop: Feed list has 16px horizontal padding ✅
- Desktop: Article has 24px horizontal padding ✅
- **Matches production exactly!**

---

### **Bug #2: Viewport Resize Makes App Grey and Unclickable**

**Problem:**
When you resize from mobile to desktop with sidebar open:
1. Mobile sidebar overlay (`#sidebar-overlay`) is visible (grey background)
2. You resize to desktop (drag window wider)
3. Overlay stays visible with `display: block`
4. Overlay blocks ALL clicks - entire app becomes grey and unusable

**Root Cause:**
```html
<!-- Overlay element: -->
<div id="sidebar-overlay"
     class="hidden fixed inset-0 bg-black/50 z-40">
</div>
```

When JavaScript opens sidebar on mobile:
```javascript
overlay.classList.add('block');  // Adds 'block' class
```

On desktop, the `block` class overrides `hidden`, so overlay stays visible!

**Fix:**
```html
<!-- Add lg:!hidden to FORCE hide on desktop: -->
<div id="sidebar-overlay"
     class="hidden lg:!hidden fixed inset-0 bg-black/50 z-40">
     <!--         ^^^^^^^^^^
                 This forces display:none on desktop
                 even if 'block' class exists! -->
</div>
```

The `!` makes it `!important` in Tailwind, overriding the `block` class.

**Result:**
- Mobile with sidebar open: Overlay visible ✅
- Desktop (any time): Overlay ALWAYS hidden ✅
- Resize mobile→desktop: Overlay auto-hides ✅
- App stays clickable ✅

---

## 📋 **FILES CHANGED**

### **1. app/main.py** (3 changes)

**Change 1 & 2: Add `lg:!hidden` to sidebar overlay (lines 201, 955)**
```python
# BEFORE:
Div(id="sidebar-overlay", cls="hidden fixed inset-0 bg-black/50 z-40", ...)

# AFTER:
Div(id="sidebar-overlay", cls="hidden lg:!hidden fixed inset-0 bg-black/50 z-40", ...)
```

**Change 3: Remove mobile horizontal padding from feed-list (lines 215, 969)**
```python
# BEFORE:
Div(id=ElementIDs.FEED_LIST, cls="h-full overflow-y-auto px-4 lg:border-r")

# AFTER:
Div(id=ElementIDs.FEED_LIST, cls="h-full overflow-y-auto lg:px-4 lg:border-r")
```

**Change 4: Fix article detail mobile padding (lines 220, 974)**
```python
# BEFORE:
cls="... max-lg:p-4 hidden"

# AFTER:
cls="... max-lg:px-4 hidden"
```

---

## ✅ **TEST COVERAGE**

### **New Test File:** `tests/ui/test_viewport_resize.py`

**5 comprehensive tests:**

1. ✅ **test_mobile_to_desktop_resize_with_sidebar_open**
   - Reproduces the exact bug scenario
   - Verifies overlay is hidden on desktop
   - Verifies app remains clickable

2. ✅ **test_desktop_to_mobile_resize**
   - Tests reverse transition
   - Verifies sidebar hides off-screen on mobile

3. ✅ **test_mobile_padding_removed**
   - Verifies mobile has 0px horizontal padding on feed list

4. ✅ **test_desktop_padding_preserved**
   - Verifies desktop has correct padding (16px feed, 24px article)

5. ✅ **test_multiple_resize_cycles**
   - Tests mobile↔desktop transitions multiple times
   - Ensures no state pollution

**All 5 tests pass!**

---

## 📊 **BEFORE vs AFTER**

### Mobile Padding (390px viewport)

| Element | Before | After | Production |
|---------|--------|-------|------------|
| Feed List | 16px L/R | **0px L/R** | 0px L/R ✅ |
| Article | 16px all sides | **16px L/R only** | 16px L/R ✅ |

### Desktop Padding (1400px viewport)

| Element | Before | After | Production |
|---------|--------|-------|------------|
| Feed List | 16px L/R | 16px L/R | 16px L/R ✅ |
| Article | 24px L/R | 24px L/R | 24px L/R ✅ |

### Viewport Resize Bug

| Scenario | Before | After |
|----------|--------|-------|
| Resize with sidebar open | ❌ Grey screen, unclickable | ✅ Works perfectly |
| Overlay on desktop | ❌ Visible (blocks clicks) | ✅ Hidden |
| Multiple resize cycles | ❌ Unpredictable | ✅ Stable |

---

## 🎯 **ULTRATHINKING INSIGHTS**

**Why was this hard to catch?**

1. **The overlay bug only happens during viewport resize**
   - Normal usage doesn't trigger it
   - You have to resize from mobile→desktop WITH sidebar open
   - Playwright tests usually test one viewport at a time

2. **CSS specificity gotcha:**
   - Adding the `block` class via JavaScript overrides `hidden`
   - Need `!important` (via `lg:!hidden`) to force hide on desktop
   - This is a common Tailwind responsive design trap

3. **Mobile padding was subtle:**
   - 16px padding doesn't look obviously wrong
   - Only noticeable when comparing side-by-side with production
   - Required precise measurement with Playwright

**The fix was elegant:**
- Single character change: `px-4` → `lg:px-4` (3 chars added)
- Single class addition: `lg:!hidden` (11 chars added)
- **Total: 14 characters fixed 2 critical bugs!**

---

## 🚀 **TESTING**

### Automated Tests
```bash
source venv/bin/activate
python -m pytest tests/ui/test_viewport_resize.py -v
```

### Manual Testing
1. **Mobile padding:** Open on phone or 390px viewport - feed list should go edge-to-edge
2. **Resize bug:**
   - Start at 390px width
   - Open sidebar
   - Drag window to 1400px width
   - App should still be clickable (not grey)

---

## 📱 **MOBILE TESTING CHECKLIST**

Use your iPhone to verify:

1. ✅ Feed list goes edge-to-edge (no horizontal padding)
2. ✅ Article has small horizontal padding (16px)
3. ✅ Rotating from portrait to landscape works
4. ✅ App never gets stuck in grey unclickable state

---

## 🎉 **SUMMARY**

**Before:**
- Mobile had too much padding (16px when it should be 0px)
- Resizing from mobile to desktop broke the app (grey screen)

**After:**
- Mobile padding matches production exactly
- Viewport resize works flawlessly in any direction
- Comprehensive test coverage ensures it stays fixed

**Impact:**
- Better mobile UX (more content visible)
- No more "grey screen of death" when resizing
- Production parity achieved
