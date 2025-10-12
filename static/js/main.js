/* RSS Reader Main JavaScript */

// Sidebar toggle
window.toggleSidebar = function() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar.classList.contains('left-0')) {
        sidebar.classList.remove('left-0');
        sidebar.classList.add('-left-full');
        overlay.classList.remove('block');
        overlay.classList.add('hidden');
    } else {
        sidebar.classList.remove('-left-full');
        sidebar.classList.add('left-0');
        overlay.classList.remove('hidden');
        overlay.classList.add('block');
    }
};

// Search toggle - improved with proper state management
window.toggleSearch = function() {
    // Unified elements - single source of truth
    const searchBar = document.getElementById('search-bar');
    const iconBar = document.getElementById('icon-bar');
    const searchInput = document.getElementById('search-input');

    if (searchBar && searchBar.classList.contains('flex')) {
        // Close search
        searchBar.classList.remove('flex');
        searchBar.classList.add('hidden');
        if (iconBar) {
            iconBar.classList.remove('hidden');
            iconBar.classList.add('flex');
        }
    } else if (searchBar) {
        // Open search
        searchBar.classList.remove('hidden');
        searchBar.classList.add('flex');
        if (iconBar) {
            iconBar.classList.remove('flex');
            iconBar.classList.add('hidden');
        }
        // Focus input after animation
        setTimeout(() => {
            if (searchInput) searchInput.focus();
        }, 50);
    }
};

// Article view management for mobile with race condition prevention
window.articleTransitioning = false;
window.currentArticleRequest = null;

window.showArticle = function(itemId) {
    if (window.innerWidth < 1024) {
        // Prevent race conditions - abort any pending transition
        if (window.articleTransitioning) {
            console.log('Article transition already in progress, blocking new request');
            return;
        }
        window.articleTransitioning = true;

        const articleDetail = document.getElementById('article-detail');
        const feedList = document.getElementById('feed-list');
        const navButton = document.getElementById('nav-button');

        if (articleDetail) {
            articleDetail.classList.remove('hidden');
            articleDetail.classList.add('block');
        }
        if (feedList) {
            feedList.classList.add('hidden');
        }

        // Update nav button to back
        if (navButton) {
            navButton.dataset.mode = 'back';
            const arrowIcon = document.createElement('uk-icon');
            arrowIcon.setAttribute('icon', 'arrow-left');
            navButton.innerHTML = '';
            navButton.appendChild(arrowIcon);

            // Get scroll position from current URL (passed via hx-vals)
            const urlParams = new URLSearchParams(window.location.search);
            const scrollPos = urlParams.get('_scroll') || '0';

            // Create back URL with scroll parameter, preserving existing params
            let backUrl = navButton.dataset.returnUrl || window.location.pathname;

            // Parse URL to preserve existing parameters (like feed_id)
            const urlParts = backUrl.split('?');
            const basePath = urlParts[0];
            const existingParams = new URLSearchParams(urlParts[1] || '');

            // Update/add _scroll parameter
            existingParams.set('_scroll', scrollPos);

            // Rebuild URL
            backUrl = `${basePath}?${existingParams.toString()}`;

            navButton.setAttribute('hx-get', backUrl);
            navButton.setAttribute('data-return-url', backUrl);
            navButton.setAttribute('hx-target', '#feed-list');
            navButton.setAttribute('hx-push-url', 'true');
            navButton.removeAttribute('onclick');
            // MUST call htmx.process() when ADDING attributes (unlike hideArticle where we REMOVE them)
            htmx.process(navButton);
        }

        // Release lock after transition completes
        setTimeout(() => {
            window.articleTransitioning = false;
        }, 300);
    }
};

window.hideArticle = function() {
    console.log('[hideArticle] Called, innerWidth:', window.innerWidth);
    if (window.innerWidth < 1024) {
        // Prevent race conditions during hide
        window.articleTransitioning = true;
        const articleDetail = document.getElementById('article-detail');
        const feedList = document.getElementById('feed-list');
        const navButton = document.getElementById('nav-button');

        console.log('[hideArticle] Elements:', {
            articleDetail: articleDetail?.id,
            hasBlockClass: articleDetail?.classList.contains('block'),
            feedList: feedList?.id,
            hasHiddenClass: feedList?.classList.contains('hidden')
        });

        if (articleDetail) {
            articleDetail.classList.remove('block');
            articleDetail.classList.add('hidden');
            console.log('[hideArticle] Added hidden class, removed block class from article-detail');
        }
        if (feedList) {
            feedList.classList.remove('hidden');
            console.log('[hideArticle] Removed hidden class from feed-list');
        }

        // Update nav button to menu
        if (navButton) {
            navButton.dataset.mode = 'menu';
            const menuIcon = document.createElement('uk-icon');
            menuIcon.setAttribute('icon', 'menu');
            navButton.innerHTML = '';
            navButton.appendChild(menuIcon);
            navButton.removeAttribute('hx-get');
            navButton.removeAttribute('hx-target');
            navButton.setAttribute('onclick', 'toggleSidebar()');
            // DON'T call htmx.process() here - removing attributes and calling process
            // will un-register HTMX behavior. Just remove the attributes.
        }

        // Release lock after transition completes
        setTimeout(() => {
            window.articleTransitioning = false;
        }, 300);
    }
};

// Click outside to close search - improved robustness
document.addEventListener('click', function(event) {
    // Unified elements - single source of truth
    const searchBar = document.getElementById('search-bar');
    const iconBar = document.getElementById('icon-bar');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    // Close sidebar if clicked outside (mobile only)
    if (window.innerWidth < 1024 && sidebar && sidebar.classList.contains('left-0')) {
        const clickedInsideSidebar = sidebar.contains(event.target);
        const clickedHamburger = event.target.closest('#nav-button');
        const clickedSidebarLink = event.target.closest('#sidebar a, #sidebar button');

        // Only close if clicked outside sidebar AND not on hamburger AND not on sidebar link
        // (sidebar links have their own hx-on-click toggle handlers)
        if (!clickedInsideSidebar && !clickedHamburger && !clickedSidebarLink) {
            toggleSidebar();
        }
    }

    if (searchBar && searchBar.classList.contains('flex')) {
        const clickedInsideSearch = searchBar.contains(event.target);
        const clickedSearchButton = event.target.closest('button[title="Search"]');
        const clickedCloseButton = event.target.closest('button[title="Close search"]');

        // Don't close if clicked on search elements
        if (!clickedInsideSearch && !clickedSearchButton && !clickedCloseButton) {
            searchBar.classList.remove('flex');
            searchBar.classList.add('hidden');
            if (iconBar) {
                iconBar.classList.remove('hidden');
                iconBar.classList.add('flex');
            }
        }
    }
});

// Escape key to close search
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        // Unified elements - single source of truth
        const searchBar = document.getElementById('search-bar');
        const iconBar = document.getElementById('icon-bar');

        if (searchBar && searchBar.classList.contains('flex')) {
            searchBar.classList.remove('flex');
            searchBar.classList.add('hidden');
            if (iconBar) {
                iconBar.classList.remove('hidden');
                iconBar.classList.add('flex');
            }
        }
    }
});

// HTMX configuration
htmx.logAll();
htmx.config.includeIndicatorStyles = false;

// Handle article click with race condition prevention
htmx.on('htmx:beforeRequest', function(evt) {
    console.log('HTMX request intercepted:', evt.detail);

    // Block concurrent article-detail requests on mobile
    if (evt.detail.target && evt.detail.target.id === 'article-detail' && window.innerWidth < 1024) {
        if (window.articleTransitioning) {
            console.log('Blocking HTMX request - transition in progress');
            evt.preventDefault();
            return false;
        }
        window.currentArticleRequest = evt.detail.xhr;
    }

    // Handle mobile context - ensure correct element targeting
    const triggerElement = evt.detail.elt;
    const target = evt.detail.target;

    // If it's an add feed request from mobile sidebar, make sure it targets the right element
    if (triggerElement && triggerElement.classList.contains('add-feed-button')) {
        const parentForm = triggerElement.closest('.add-feed-form');
        const mobileSidebar = triggerElement.closest('#mobile-sidebar');

        if (mobileSidebar && parentForm) {
            // For mobile sidebar add feed, target the mobile feeds content
            const targetSelector = '#mobile-feeds-content';
            const newTarget = document.querySelector(targetSelector);
            if (newTarget && evt.detail.requestConfig) {
                evt.detail.requestConfig.target = targetSelector;
                console.log('Retargeted mobile add feed to:', targetSelector);
            }
        }
    }

    // Add unread filter from global toggle if present
    const form = triggerElement ? triggerElement.closest('form') : null;
    const formData = form ? new FormData(form) : null;
    const newFeedUrl = formData ? formData.get('new_feed_url') : null;

    if (newFeedUrl) {
        const unreadToggle = document.getElementById('unread-toggle');
        if (unreadToggle && unreadToggle.checked) {
            const url = new URL(evt.detail.path, window.location.origin);
            url.searchParams.set('unread_only', 'true');
            evt.detail.path = url.pathname + url.search;
            console.log('Added unread filter to add feed request');
        }
    }
});

// Handle afterSwap
htmx.on('htmx:afterSwap', function(evt) {
    console.log('HTMX afterSwap event:', evt.detail);

    const target = evt.detail.target;

    // Handle article detail swap on mobile
    if (target && target.id === 'article-detail' && window.innerWidth < 1024) {
        showArticle();
    }

    // Note: Mobile back navigation is handled in htmx-config.js (lines 62-91)
    // That handler calls hideArticle() when feed-list is swapped on mobile
    // We don't need duplicate logic here

    // Clear any article request tracking
    if (target && target.id === 'article-detail') {
        window.currentArticleRequest = null;
    }

    // Prevent horizontal scrolling
    const feedList = document.getElementById('feed-list');
    if (feedList) {
        feedList.scrollLeft = 0;
    }

    // Reset scroll position on pagination
    if (evt.detail.pathInfo && evt.detail.pathInfo.requestPath && evt.detail.pathInfo.requestPath.includes('page=')) {
        const targetEl = evt.detail.target;
        if (targetEl && targetEl.id === 'feed-list') {
            console.log('Pagination detected - resetting scroll position');
            targetEl.scrollTop = 0;
        }
    }
});

// Handle afterSettle
htmx.on('htmx:afterSettle', function(evt) {
    const target = evt.detail.target;

    // Refresh Lucide icons if needed
    if (target && lucide) {
        lucide.createIcons();
    }

    // Handle mobile article view
    if (target && target.id === 'article-detail' && window.innerWidth < 1024) {
        // Ensure article is visible
        const articleDetail = document.getElementById('article-detail');
        const feedList = document.getElementById('feed-list');
        if (articleDetail && !articleDetail.classList.contains('block')) {
            showArticle();
        }
    }
});

// Handle form reset after successful feed add
htmx.on('htmx:afterRequest', function(evt) {
    if (evt.detail.successful && evt.detail.elt && evt.detail.elt.classList.contains('add-feed-button')) {
        const form = evt.detail.elt.closest('form');
        if (form) {
            const input = form.querySelector('input[name="new_feed_url"]');
            if (input) {
                input.value = '';
                console.log('Cleared feed URL input after successful add');
            }
        }
    }
});

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    // Set up sidebar overlay click handler
    const overlay = document.getElementById('sidebar-overlay');
    if (overlay) {
        overlay.addEventListener('click', function() {
            toggleSidebar();
        });
    }

    // Initialize Lucide icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // Handle resize to ensure proper layout
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            // Reset mobile states on desktop resize
            if (window.innerWidth >= 1024) {
                const articleDetail = document.getElementById('article-detail');
                const feedList = document.getElementById('feed-list');
                if (articleDetail) {
                    articleDetail.classList.remove('block');
                    articleDetail.classList.add('hidden');
                }
                if (feedList) {
                    feedList.classList.remove('hidden');
                }
            }
        }, 250);
    });
});