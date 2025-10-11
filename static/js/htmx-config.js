/* HTMX Configuration and Event Handlers */

// Enable HTMX debugging
htmx.logAll();
htmx.config.includeIndicatorStyles = false;

// Prevent race conditions - block concurrent article requests
htmx.on('htmx:beforeRequest', function(evt) {
    // Only block if this is an article detail request on mobile
    if (evt.detail.target && evt.detail.target.id === 'article-detail' && window.innerWidth < 1024) {
        if (window.articleTransitioning) {
            console.log('Blocking concurrent article request');
            evt.preventDefault();
            return false;
        }
    }
});

// Scroll restoration using hx-vals (configured per FeedItem)
// Restore scroll position after navigating back, reset to top for forward navigation
htmx.on('htmx:afterSwap', function(evt) {
    // Handle article navigation on mobile (consolidated logic)
    if (evt.detail.target && evt.detail.target.id === 'article-detail' && window.innerWidth < 1024) {
        if (window.showArticle) {
            window.showArticle();
        } else {
            // Fallback: complete mobile article view logic
            const articleDetail = document.getElementById('article-detail');
            const feedList = document.getElementById('feed-list');
            const navButton = document.getElementById('nav-button');

            if (articleDetail) {
                articleDetail.classList.add('active');
            }
            if (feedList) {
                feedList.classList.add('article-view');
            }

            // Update nav button to back mode
            if (navButton) {
                navButton.dataset.mode = 'back';
                const arrowIcon = document.createElement('uk-icon');
                arrowIcon.setAttribute('icon', 'arrow-left');
                navButton.innerHTML = '';
                navButton.appendChild(arrowIcon);
                navButton.setAttribute('hx-get', '/');
                navButton.setAttribute('hx-target', '#feed-list');
                navButton.removeAttribute('onclick');
                // Reprocess the element so HTMX recognizes the new attributes
                htmx.process(navButton);
                console.log('Nav button reprocessed, HTMX attributes:', {
                    hasHxGet: navButton.hasAttribute('hx-get'),
                    hasHxTarget: navButton.hasAttribute('hx-target'),
                    hxGet: navButton.getAttribute('hx-get'),
                    hxTarget: navButton.getAttribute('hx-target')
                });
            }
        }
    }

    // Handle returning to feed list on mobile (back navigation)
    if (evt.detail.target && evt.detail.target.id === 'feed-list' && window.innerWidth < 1024) {
        // Always try to hide the article view when swapping feed-list content
        if (window.hideArticle) {
            window.hideArticle();
        } else {
            // Fallback: complete mobile feed list restoration logic
            const articleDetail = document.getElementById('article-detail');
            const feedList = document.getElementById('feed-list');
            const navButton = document.getElementById('nav-button');

            if (articleDetail) {
                articleDetail.classList.remove('active');
            }
            if (feedList) {
                feedList.classList.remove('article-view');
            }

            // Update nav button back to menu
            if (navButton) {
                navButton.dataset.mode = 'menu';
                const menuIcon = document.createElement('uk-icon');
                menuIcon.setAttribute('icon', 'menu');
                navButton.innerHTML = '';
                navButton.appendChild(menuIcon);
                navButton.removeAttribute('hx-get');
                navButton.removeAttribute('hx-target');
                navButton.setAttribute('onclick', 'toggleSidebar()');
            }
        }
    }

    if (window.innerWidth < 1024 && evt.detail.target && (evt.detail.target.id === 'main-content' || evt.detail.target.id === 'feed-list')) {
        // Body class management for mobile article view
        if (evt.detail.xhr && evt.detail.xhr.responseURL) {
            if (evt.detail.xhr.responseURL.includes('/item/')) {
                htmx.addClass(document.body, 'article-view');
            } else {
                htmx.removeClass(document.body, 'article-view');
                // Call hideArticle when navigating away from article
                if (window.hideArticle) {
                    window.hideArticle();
                }
            }
        }

        // Check if this is back navigation with scroll position to restore
        if (evt.detail.pathInfo && evt.detail.pathInfo.requestPath) {
            const match = evt.detail.pathInfo.requestPath.match(/_scroll=(\d+)/);
            if (match) {
                // Back navigation - restore scroll position
                const scrollPos = parseInt(match[1]);
                setTimeout(() => {
                    const feedList = document.getElementById('feed-list');
                    if (feedList) {
                        feedList.scrollTop = scrollPos;
                    }
                }, 50);
            } else {
                // Forward navigation - reset scroll to top
                setTimeout(() => {
                    const feedList = document.getElementById('feed-list');
                    if (feedList) {
                        feedList.scrollTop = 0;
                    }
                }, 50);
            }
        } else {
            // No path info - reset scroll to top
            setTimeout(() => {
                const feedList = document.getElementById('feed-list');
                if (feedList) {
                    feedList.scrollTop = 0;
                }
            }, 50);
        }
    }

    // Pagination scroll reset - unified for mobile and desktop
    // When #feed-list is swapped (pagination target), reset scroll to top
    if (evt.detail.target && evt.detail.target.id === 'feed-list') {
        // Check if this is pagination (not article navigation with scroll restore)
        const requestPath = evt.detail.pathInfo?.requestPath || '';
        const hasScrollRestore = requestPath.includes('_scroll=');
        const isArticleView = requestPath.includes('/item/');

        // Reset scroll for pagination, feed changes, or non-article navigations
        // But skip if this is scroll restoration (back button)
        if (!hasScrollRestore && !isArticleView) {
            console.log('Resetting #feed-list scroll to top', {path: requestPath});
            setTimeout(() => {
                const feedList = document.getElementById('feed-list');
                if (feedList) {
                    console.log('Scroll before:', feedList.scrollTop);
                    feedList.scrollTop = 0;
                    console.log('Scroll after:', feedList.scrollTop);
                }
            }, 100);  // Increased timeout for mobile
        }
    }
});