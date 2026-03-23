(function () {
    var root = document.getElementById("image-cards-{{ block.id }}");
    if (!root) return;

    var items = root.querySelectorAll(".ic-item");
    if (!items.length) return;

    var total = items.length;
    var carouselWrapper = root.querySelector(".ic-carousel-wrapper");
    var viewport = root.querySelector(".ic-carousel-viewport");
    var grid = root.querySelector(".ic-grid");
    var pagination = root.querySelector(".ic-pagination");
    var dots = root.querySelectorAll(".ic-dot");
    var autoplayInterval = null;
    var isCarouselActive = false;
    var isAnimatingCarousel = false;
    var TRANSITION_STYLE = "transform 500ms cubic-bezier(0.25, 1, 0.5, 1)";

    var originalNodes = [];
    for (var i = 0; i < total; i++) {
        originalNodes.push(items[i]);
    }

    function getVisibleColumns() {
        if (window.innerWidth >= 1024) return 3;
        if (window.innerWidth >= 640) return 2;
        return 1;
    }

    function startAutoplay() {
        if (autoplayInterval) clearInterval(autoplayInterval);
        if (isCarouselActive) {
            autoplayInterval = setInterval(function() {
                moveCarousel(1);
            }, 5000);
        }
    }

    function stopAutoplay() {
        if (autoplayInterval) clearInterval(autoplayInterval);
        autoplayInterval = null;
    }

    function updateActiveDot() {
        if (!isCarouselActive) return;
        var currentLeftmost = parseInt(grid.firstElementChild.dataset.index, 10);
        dots.forEach(function(dot) {
            dot.classList.remove("ic-dot--active");
            dot.removeAttribute("aria-current");
        });
        if (dots[currentLeftmost]) {
            dots[currentLeftmost].classList.add("ic-dot--active");
            dots[currentLeftmost].setAttribute("aria-current", "step");
        }
    }

    function getSlideWidth() {
        var gap = parseFloat(window.getComputedStyle(grid).gap) || 20;
        return originalNodes[0].offsetWidth + gap;
    }

    function moveCarousel(steps) {
        if (!isCarouselActive || isAnimatingCarousel || steps === 0) return;
        var children = grid.children;
        var totalSlides = children.length;
        steps = steps % totalSlides;
        if (steps === 0) return;

        isAnimatingCarousel = true;
        var slideWidth = getSlideWidth();

        if (steps > 0) {
            grid.style.transition = TRANSITION_STYLE;
            grid.style.transform = "translateX(-" + (slideWidth * steps) + "px)";

            grid.addEventListener("transitionend", function handler(e) {
                if (e.target !== grid || e.propertyName !== 'transform') return;
                grid.removeEventListener("transitionend", handler);
                grid.style.transition = "none";
                for(var k = 0; k < steps; k++) {
                    grid.appendChild(grid.firstElementChild);
                }
                grid.style.transform = "translateX(0)";
                void grid.offsetWidth; 
                updateActiveDot();
                isAnimatingCarousel = false;
            });
        } else {
            var absSteps = Math.abs(steps);
            grid.style.transition = "none";
            for(var k = 0; k < absSteps; k++) {
                grid.prepend(grid.lastElementChild);
            }
            grid.style.transform = "translateX(-" + (slideWidth * absSteps) + "px)";
            void grid.offsetWidth; 

            grid.style.transition = TRANSITION_STYLE;
            grid.style.transform = "translateX(0)";

            grid.addEventListener("transitionend", function handler(e) {
                if (e.target !== grid || e.propertyName !== 'transform') return;
                grid.removeEventListener("transitionend", handler);
                updateActiveDot();
                isAnimatingCarousel = false;
            });
        }
    }

    function dotClicked(targetIndex) {
        if (!isCarouselActive) return;
        var currentLeftmost = parseInt(grid.firstElementChild.dataset.index, 10);
        if (currentLeftmost === targetIndex) return;

        var children = grid.children;
        var targetDomIndex = -1;
        for (var i = 0; i < children.length; i++) {
            if (parseInt(children[i].dataset.index, 10) === targetIndex) {
                targetDomIndex = i;
                break;
            }
        }
        if (targetDomIndex === -1) return;

        var totalSlides = children.length;
        var stepsForward = targetDomIndex;
        var stepsBackward = totalSlides - targetDomIndex;

        if (stepsForward <= stepsBackward) {
            moveCarousel(stepsForward);
        } else {
            moveCarousel(-stepsBackward);
        }
    }

    function initCarousel() {
        if (isCarouselActive) return;
        isCarouselActive = true;
        carouselWrapper.classList.add("is-carousel");
        if (pagination) {
            pagination.classList.add("is-active");
            pagination.setAttribute("aria-hidden", "false");
        }
        updateActiveDot();
        startAutoplay();
    }

    function destroyCarousel() {
        if (!isCarouselActive) return;
        isCarouselActive = false;
        stopAutoplay();
        carouselWrapper.classList.remove("is-carousel");
        if (pagination) {
            pagination.classList.remove("is-active");
            pagination.setAttribute("aria-hidden", "true");
        }
        grid.style.transition = "none";
        grid.style.transform = "translateX(0)";
        
        for (var i = 0; i < originalNodes.length; i++) {
            grid.appendChild(originalNodes[i]);
        }
    }

    function checkResponsive() {
        if (total <= 1) return; 
        var cols = getVisibleColumns();
        
        if (total > cols) {
            initCarousel();
        } else {
            destroyCarousel();
        }
    }

    dots.forEach(function(dot) {
        dot.addEventListener("click", function() {
            var targetIdx = parseInt(dot.dataset.index, 10);
            dotClicked(targetIdx);
            startAutoplay();
        });
    });

    carouselWrapper.addEventListener('mouseenter', stopAutoplay);
    carouselWrapper.addEventListener('mouseleave', startAutoplay);
    carouselWrapper.addEventListener('focusin', stopAutoplay);
    carouselWrapper.addEventListener('focusout', startAutoplay);

    var touchStartXOuter = 0;
    var touchEndXOuter = 0;

    viewport.addEventListener('touchstart', function (e) {
        if (!isCarouselActive) return;
        touchStartXOuter = e.changedTouches[0].screenX;
    }, { passive: true });

    viewport.addEventListener('touchend', function (e) {
        if (!isCarouselActive) return;
        touchEndXOuter = e.changedTouches[0].screenX;
        var diff = touchStartXOuter - touchEndXOuter;

        if (Math.abs(diff) > 40) {
            if (diff > 0) moveCarousel(1);
            else moveCarousel(-1);
            startAutoplay();
        }
    }, { passive: true });

    var resizeTimer;
    window.addEventListener("resize", function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(checkResponsive, 150);
    });

    checkResponsive();
})();