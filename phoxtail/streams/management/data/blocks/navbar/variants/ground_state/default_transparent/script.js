document.addEventListener("DOMContentLoaded", function () {
    var nav = document.querySelector('#nb-{{ block.id }}');
    if (!nav) return;

    var toggle = nav.querySelector('.nb-glass-toggle');
    var sidebar = nav.querySelector('.nb-glass-sidebar');
    var backdrop = nav.querySelector('.nb-glass-backdrop');
    var closeBtn = nav.querySelector('.nb-glass-sidebar-close');

    /* Smart scroll behavior */
    var lastScrollY = window.scrollY;
    var ticking = false;

    function updateNav() {
        var currentScrollY = window.scrollY;

        // Only hide if scrolled down past 100px and moving down
        if (currentScrollY > lastScrollY && currentScrollY > 100) {
            nav.classList.add('nb-scrolled-down');
            // Close open dropdowns when hiding nav
            nav.querySelectorAll('.nb-glass-dropdown-open').forEach(function(d) {
                d.classList.remove('nb-glass-dropdown-open');
            });
        }
        // Show if scrolling up or near top
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
        backdrop.classList.add('nb-glass-open');
        setTimeout(function () {
            sidebar.classList.add('nb-glass-open');
        }, 50);
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('nb-glass-open');
        setTimeout(function () {
            backdrop.classList.remove('nb-glass-open');
        }, 300);
        document.body.style.overflow = '';
    }

    if (toggle) toggle.addEventListener('click', openSidebar);
    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (backdrop) backdrop.addEventListener('click', closeSidebar);

    /* Escape key closes sidebar */
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && sidebar.classList.contains('nb-glass-open')) {
            closeSidebar();
        }
    });

    /* Sidebar accordion toggle */
    nav.querySelectorAll('.nb-glass-accordion-trigger').forEach(function (trigger) {
        var content = trigger.nextElementSibling;
        var chevron = trigger.querySelector('.nb-glass-accordion-chevron');

        trigger.addEventListener('click', function () {
            var expanded = content.classList.contains('nb-glass-expanded');

            if (expanded) {
                content.style.maxHeight = content.scrollHeight + 'px';
                content.offsetHeight;
                content.style.maxHeight = '0px';

                setTimeout(function () {
                    content.classList.remove('nb-glass-expanded');
                    content.style.maxHeight = '';
                }, 300);

                if (chevron) chevron.classList.remove('nb-glass-rotated');
            } else {
                content.style.maxHeight = '0px';
                content.offsetHeight;
                content.style.maxHeight = content.scrollHeight + 'px';

                setTimeout(function () {
                    content.classList.add('nb-glass-expanded');
                    content.style.maxHeight = '';
                }, 300);

                if (chevron) chevron.classList.add('nb-glass-rotated');
            }
        });
    });

    /* Desktop dropdown click toggle (supplements CSS hover) */
    var dropdowns = nav.querySelectorAll('.nb-glass-dropdown');
    dropdowns.forEach(function (dropdown) {
        var trigger = dropdown.querySelector('.nb-glass-dropdown-trigger');
        if (!trigger) return;

        trigger.addEventListener('click', function (e) {
            e.preventDefault();
            var wasOpen = dropdown.classList.contains('nb-glass-dropdown-open');

            dropdowns.forEach(function (d) {
                d.classList.remove('nb-glass-dropdown-open');
            });

            if (!wasOpen) {
                dropdown.classList.add('nb-glass-dropdown-open');
            }
        });
    });

    /* Close dropdowns on outside click */
    document.addEventListener('click', function (e) {
        if (!nav.contains(e.target)) {
            dropdowns.forEach(function (d) {
                d.classList.remove('nb-glass-dropdown-open');
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