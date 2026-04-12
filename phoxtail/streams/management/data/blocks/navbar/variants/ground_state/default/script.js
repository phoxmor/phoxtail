document.addEventListener("DOMContentLoaded", function () {
    var nav = document.querySelector('#nb-{{ block.id }}');
    if (!nav) return;

    /* --- NEW: Spacer Logic (Replaces body padding) --- */
    var spacer = document.querySelector('#nb-spacer-{{ block.id }}');
    
    // This watches the navbar size and updates the spacer height automatically
    if (spacer) {
        var resizeObserver = new ResizeObserver(function(entries) {
            for (var entry of entries) {
                spacer.style.height = entry.contentRect.height + 'px';
            }
        });
        resizeObserver.observe(nav);
    }
    /* ------------------------------------------------- */

    var toggle = nav.querySelector('.nb-toggle');
    var sidebar = nav.querySelector('.nb-sidebar');
    var backdrop = nav.querySelector('.nb-backdrop');
    var closeBtn = nav.querySelector('.nb-sidebar-close');

    /* Smart scroll behavior */
    var lastScrollY = window.scrollY;
    var ticking = false;

    function updateNav() {
        var currentScrollY = window.scrollY;
        
        // Only hide if scrolled down past 100px and moving down
        if (currentScrollY > lastScrollY && currentScrollY > 100) {
            nav.classList.add('nb-scrolled-down');
            nav.querySelectorAll('.nb-dropdown-open').forEach(function(d) {
                d.classList.remove('nb-dropdown-open');
            });
        } 
        else if (currentScrollY < lastScrollY || currentScrollY <= 100) {
            nav.classList.remove('nb-scrolled-down');
        }
        
        lastScrollY = currentScrollY;
        ticking = false;
    }

    window.addEventListener('scroll', function() {
        if (!ticking) {
            window.requestAnimationFrame(updateNav);
            ticking = true;
        }
    });

    /* Sidebar open/close */
    function openSidebar() {
        backdrop.classList.add('nb-open');
        setTimeout(function () {
            sidebar.classList.add('nb-open');
        }, 50);
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('nb-open');
        setTimeout(function () {
            backdrop.classList.remove('nb-open');
        }, 300);
        document.body.style.overflow = '';
    }

    if (toggle) toggle.addEventListener('click', openSidebar);
    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (backdrop) backdrop.addEventListener('click', closeSidebar);

    /* Escape key closes sidebar */
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && sidebar.classList.contains('nb-open')) {
            closeSidebar();
        }
    });

    /* Sidebar accordion toggle */
    nav.querySelectorAll('.nb-accordion-trigger').forEach(function (trigger) {
        var content = trigger.nextElementSibling;
        var chevron = trigger.querySelector('.nb-accordion-chevron');

        trigger.addEventListener('click', function () {
            var expanded = content.classList.contains('nb-expanded');
            
            if (expanded) {
                content.style.maxHeight = content.scrollHeight + 'px';
                content.offsetHeight; // Force reflow
                content.style.maxHeight = '0px';
                setTimeout(function () {
                    content.classList.remove('nb-expanded');
                    content.style.maxHeight = '';
                }, 300);
                if (chevron) chevron.classList.remove('nb-rotated');
            } else {
                content.style.maxHeight = '0px';
                content.offsetHeight; // Force reflow
                content.style.maxHeight = content.scrollHeight + 'px';
                setTimeout(function () {
                    content.classList.add('nb-expanded');
                    content.style.maxHeight = '';
                }, 300);
                if (chevron) chevron.classList.add('nb-rotated');
            }
        });
    });

    /* Desktop dropdown click toggle */
    var dropdowns = nav.querySelectorAll('.nb-dropdown');
    dropdowns.forEach(function (dropdown) {
        var trigger = dropdown.querySelector('.nb-dropdown-trigger');
        if (!trigger) return;

        trigger.addEventListener('click', function (e) {
            e.preventDefault();
            var wasOpen = dropdown.classList.contains('nb-dropdown-open');
            dropdowns.forEach(function (d) {
                d.classList.remove('nb-dropdown-open');
            });
            if (!wasOpen) {
                dropdown.classList.add('nb-dropdown-open');
            }
        });
    });

        /* Close dropdowns on outside click */

        document.addEventListener('click', function (e) {

            if (!nav.contains(e.target)) {

                dropdowns.forEach(function (d) {

                    d.classList.remove('nb-dropdown-open');

                });

            }

        });

    

        /* Scroll to Top Logic */

        var scrollTopBtn = document.querySelector('#nb-scroll-top-{{ block.id }}');

        if (scrollTopBtn) {

            window.addEventListener('scroll', function() {

                if (window.scrollY > 500) {

                    scrollTopBtn.classList.add('nb-visible');

                } else {

                    scrollTopBtn.classList.remove('nb-visible');

                }

            });

    

            scrollTopBtn.addEventListener('click', function() {

                window.scrollTo({

                    top: 0,

                    behavior: 'smooth'

                });

            });

        }

    });