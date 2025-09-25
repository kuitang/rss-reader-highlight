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
                const arrowIcon = document.createElement('div');
                arrowIcon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15,18 9,12 15,6"></polyline></svg>';
                navButton.innerHTML = '';
                navButton.appendChild(arrowIcon.firstChild);
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
                const menuIcon = document.createElement('div');
                menuIcon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>';
                navButton.innerHTML = '';
                navButton.appendChild(menuIcon.firstChild);
                navButton.removeAttribute('hx-get');
                navButton.removeAttribute('hx-target');
                navButton.setAttribute('onclick', 'toggleSidebar()');
            }
        }
    }

    if (window.innerWidth < 1024 && evt.detail.target && evt.detail.target.id === 'main-content') {
        // Body class management for mobile article view
        if (evt.detail.xhr && evt.detail.xhr.responseURL) {
            if (evt.detail.xhr.responseURL.includes('/item/')) {
                htmx.addClass(document.body, 'article-view');
            } else {
                htmx.removeClass(document.body, 'article-view');
            }
        }

        // Check if this is back navigation with scroll position to restore
        if (evt.detail.pathInfo && evt.detail.pathInfo.requestPath) {
            const match = evt.detail.pathInfo.requestPath.match(/_scroll=(\d+)/);
            if (match) {
                // Back navigation - restore scroll position
                const scrollPos = parseInt(match[1]);
                setTimeout(() => {
                    const mainContent = document.getElementById('main-content');
                    if (mainContent) {
                        mainContent.scrollTop = scrollPos;
                    }
                }, 50);
            } else {
                // Forward navigation - reset scroll to top
                setTimeout(() => {
                    const mainContent = document.getElementById('main-content');
                    if (mainContent) {
                        mainContent.scrollTop = 0;
                    }
                }, 50);
            }
        } else {
            // No path info - reset scroll to top
            setTimeout(() => {
                const mainContent = document.getElementById('main-content');
                if (mainContent) {
                    mainContent.scrollTop = 0;
                }
            }, 50);
        }
    } else if (window.innerWidth >= 1024 && evt.detail.target && evt.detail.target.id === 'desktop-feeds-content') {
        // Desktop pagination - reset scroll to top
        setTimeout(() => {
            const desktopFeeds = document.getElementById('desktop-feeds-content');
            if (desktopFeeds) {
                desktopFeeds.scrollTop = 0;
            }
        }, 50);
    }
});