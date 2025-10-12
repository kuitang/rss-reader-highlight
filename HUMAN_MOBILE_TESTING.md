# Human Mobile Testing Guide

## Overview

This guide is for **real iOS device testing** after the Tailwind CSS migration. Automated Playwright tests can only simulate mobile viewports on desktop, not real device behavior.

**Your role:** Test the layout and interactions on your actual iPhone to catch issues that viewport emulation can't detect.

---

## Prerequisites

- iOS device (iPhone)
- Access to:
  - Production: https://rss-reader-highlight.fly.dev
  - Localhost: http://[your-local-ip]:8080 (if testing pre-deployment)

---

## Testing Checklist

### 1. Visual Layout Comparison

**Goal:** Verify localhost matches production spacing and layout

#### Step 1A: Open Production on iPhone
1. Open Safari on iPhone
2. Navigate to https://rss-reader-highlight.fly.dev
3. Observe the layout:
   - Note the spacing between UI elements
   - Note the padding around the sidebar content
   - Note the chrome header height and padding
   - Note the overall "feel" of spacing

#### Step 1B: Open Localhost on iPhone
1. Find your computer's local IP: `ifconfig | grep "inet "` (on Mac/Linux)
2. Open Safari on iPhone
3. Navigate to http://[your-ip]:8080
4. Observe the layout using same criteria as production

#### Step 1C: Compare
- **Does the sidebar padding look the same?** (8px from edges)
- **Does the top spacing look the same?** (16px from top)
- **Does the chrome header look the same?** (padding above/below content)
- **Do the columns have gaps between them?** (16px gaps in desktop view when rotated)

**If different:** Fill out Bug Report Form below

---

### 2. Touch Target Testing

**Goal:** Verify all buttons are tappable on touch screen

#### Test Each Button:
- [ ] Hamburger menu button (top left)
- [ ] Search button (top right area)
- [ ] All Posts button (if visible)
- [ ] Unread button (if visible)
- [ ] Feed items in the list
- [ ] Back button (when in article view)
- [ ] Star/folder/mail action buttons (in article view)

**For each button:**
- Can you tap it reliably?
- Does it respond immediately?
- Is the touch target large enough? (Should feel like at least 44px)

**If issues:** Fill out Bug Report Form below

---

### 3. Sidebar Interaction

**Goal:** Test mobile sidebar open/close behavior

#### Test Steps:
1. Tap hamburger menu button (top left)
2. **Expected:** Sidebar slides in from left
3. **Expected:** Dark overlay appears behind sidebar
4. Tap a feed in the sidebar
5. **Expected:** Sidebar closes automatically
6. **Expected:** Feed list updates

#### Additional Checks:
- [ ] Sidebar animation is smooth (not janky)
- [ ] Overlay is visible and semi-transparent
- [ ] Tapping overlay closes sidebar
- [ ] Sidebar content is not cut off
- [ ] Sidebar has padding from edges (8px - content shouldn't touch edges)

**If issues:** Fill out Bug Report Form below

---

### 4. Scrolling Behavior

**Goal:** Verify no bounce scrolling on body, only content scrolls

#### Test Steps:
1. On the main feed list, try to scroll
2. **Expected:** Content scrolls smoothly
3. **Expected:** No rubber-band bounce effect on the body/background
4. Open an article
5. Scroll within the article
6. **Expected:** Article content scrolls, not the whole page

#### Additional Checks:
- [ ] No horizontal scrolling (content never goes off-screen sideways)
- [ ] Chrome header stays fixed at top while scrolling
- [ ] Scrolling feels responsive (not laggy)

**If issues:** Fill out Bug Report Form below

---

### 5. Chrome Header & Search

**Goal:** Test header remains fixed and search expands correctly

#### Test Steps:
1. Scroll down in feed list
2. **Expected:** Chrome header stays at top (doesn't scroll away)
3. Tap search button
4. **Expected:** Search bar expands
5. **Expected:** Header height doesn't change (height invariant)
6. Type in search box
7. **Expected:** Keyboard doesn't break layout
8. Tap outside search or close button
9. **Expected:** Search collapses back to icon bar

#### Additional Checks:
- [ ] Chrome header has padding above and below content (16px)
- [ ] Border below chrome is visible and prominent
- [ ] Search input is wide enough to type in
- [ ] Keyboard appearance doesn't cause jumpy layout

**If issues:** Fill out Bug Report Form below

---

### 6. Article View Navigation

**Goal:** Test article view and back button

#### Test Steps:
1. Tap an article in the feed list
2. **Expected:** Article opens full-screen
3. **Expected:** Back button appears (top left, replaces hamburger)
4. **Expected:** Feed list is hidden
5. Scroll within article
6. **Expected:** Article content scrolls smoothly
7. Tap back button
8. **Expected:** Returns to feed list
9. **Expected:** Hamburger menu button is back (top left)

#### Additional Checks:
- [ ] Article has padding from edges (16px)
- [ ] Action buttons (star, folder, mail) are tappable
- [ ] Back button is obvious and easy to tap
- [ ] Transition is smooth (not abrupt)

**If issues:** Fill out Bug Report Form below

---

### 7. Rotation Test (Landscape)

**Goal:** Verify layout adapts when rotating device

#### Test Steps:
1. Rotate device to landscape
2. **Expected:** Layout switches to desktop view (if wide enough)
3. **Expected:** Three columns visible: sidebar, feed list, article
4. **Expected:** Gaps between columns (16px)
5. Rotate back to portrait
6. **Expected:** Layout switches back to mobile view
7. **Expected:** Sidebar hidden, single column layout

**If issues:** Fill out Bug Report Form below

---

### 8. Performance & Stability

**Goal:** Test for memory leaks and performance issues

#### Test Steps:
1. Use the app for 5-10 minutes:
   - Navigate between feeds
   - Open multiple articles
   - Use search
   - Open/close sidebar multiple times
2. **Expected:** App remains responsive
3. **Expected:** No crashes or freezes
4. **Expected:** No visual glitches

**If issues:** Fill out Bug Report Form below

---

## Bug Report Form

Copy this template and fill it out for each issue you find. Send to developer or create GitHub issue.

```markdown
## Bug Report

**Date:** [YYYY-MM-DD]
**Device:** iPhone [model] (iOS [version])
**Browser:** Safari [version]
**URL:** [Production or Localhost]

### Issue Category
- [ ] Visual Layout (spacing, padding, alignment)
- [ ] Touch Target (button too small or unresponsive)
- [ ] Sidebar Interaction (opening, closing, animation)
- [ ] Scrolling Behavior (bounce, lag, horizontal scroll)
- [ ] Chrome Header & Search (fixed positioning, height, search expansion)
- [ ] Article View Navigation (back button, transitions)
- [ ] Rotation/Landscape (layout adaptation)
- [ ] Performance & Stability (crashes, slowness)

### What I Expected
[Describe what should happen]

### What Actually Happened
[Describe what actually happened]

### Steps to Reproduce
1. [First step]
2. [Second step]
3. [etc.]

### Screenshots
[If possible, take screenshots]
- [Attach or describe what you see]

### Severity
- [ ] Critical - App is unusable
- [ ] High - Major feature broken
- [ ] Medium - Annoying but workaround exists
- [ ] Low - Cosmetic issue only

### Additional Context
[Any other relevant information]

### Comparison to Production (if applicable)
- [ ] This issue exists on production too
- [ ] This issue is NEW (not on production)
- [ ] This issue is BETTER than production
```

---

## Quick Reference: Key Visual Checks

Use this checklist for fast visual verification:

### Spacing (compared to production)
- [ ] Sidebar content has 8px padding from edges (not touching edges)
- [ ] Top of layout has 16px padding from top edge
- [ ] Chrome header has 16px padding above and below content (not tight)
- [ ] Columns have 16px gaps between them (in landscape)

### Touch Targets
- [ ] All buttons feel large enough (44px minimum)
- [ ] No accidental taps on wrong elements
- [ ] Tap areas are generous and forgiving

### Animations
- [ ] Sidebar slide-in is smooth (not janky)
- [ ] Article open/close is smooth
- [ ] No stuttering or lag during transitions

### Scrolling
- [ ] No body bounce (rubber-band effect)
- [ ] Content scrolls smoothly
- [ ] No horizontal scrolling
- [ ] Chrome stays fixed at top

---

## Developer Notes

### Why Human Testing is Needed

Automated Playwright tests **cannot** detect:
1. **Touch interaction feel** - 44px target looks different on real device vs simulated viewport
2. **Webkit quirks** - Safari iOS behaves differently than desktop Chrome
3. **Actual scrolling physics** - Momentum scrolling, bounce, and smoothness
4. **Keyboard behavior** - iOS keyboard appearance and how it affects layout
5. **Performance on device** - Memory constraints, GPU performance
6. **Real-world UX** - Does it "feel right" to use?

### What to Focus On

The **most critical layout changes** to verify:
1. **Chrome padding: `px-4` → `p-4`** (16px all sides, makes border prominent)
2. **Sidebar padding: `px-2`** (8px horizontal, content has breathing room)
3. **Top padding: `pt-4`** (16px from top, matches production)
4. **Column gaps: `gap-4`** (16px between columns in landscape)

If these four items look correct, the migration is successful.
