(function () { 
    var root = document.getElementById("testimonials-{{ block.id }}"); 
    if (!root) return; 

    var items = root.querySelectorAll(".tm-item"); 
    var modal = root.querySelector(".tm-modal"); 
    var modalContent = root.querySelector(".tm-modal-content"); 
    var modalAvatar = root.querySelector(".tm-modal-avatar"); 
    var modalReview = root.querySelector(".tm-modal-review-text"); 
    var modalRating = root.querySelector(".tm-modal-rating"); 
    var modalAuthorName = root.querySelector(".tm-modal-author-name"); 
    var modalAuthorTitle = root.querySelector(".tm-modal-author-title"); 
    var prevBtn = root.querySelector(".tm-nav--prev"); 
    var nextBtn = root.querySelector(".tm-nav--next"); 
    var closeBtn = root.querySelector(".tm-close"); 
    var counter = root.querySelector(".tm-counter"); 
    var total = items.length; 
    var current = 0; 
    var isAnimating = false; 

    // --- 1. RESPONSIVE CAROUSEL & PAGINATION LOGIC ---
    var carouselWrapper = root.querySelector(".tm-carousel-wrapper");
    var viewport = root.querySelector(".tm-carousel-viewport");
    var grid = root.querySelector(".tm-grid");
    var pagination = root.querySelector(".tm-pagination");
    var dots = root.querySelectorAll(".tm-dot");

    var autoplayInterval = null;
    var isCarouselActive = false;
    var isAnimatingCarousel = false;
    var TRANSITION_STYLE = "transform 500ms cubic-bezier(0.25, 1, 0.5, 1)";

    // Store original DOM nodes in order to cleanly rebuild the standard grid later
    var originalNodes = [];
    for (var i = 0; i < total; i++) {
        originalNodes.push(items[i]);
    }

    // Calculates how many cards naturally fit side-by-side based on the CSS media queries
    function getVisibleColumns() {
        if (window.innerWidth >= 1024) return 3;
        if (window.innerWidth >= 768) return 2;
        return 1;
    }

    function startAutoplay() {
        if (autoplayInterval) clearInterval(autoplayInterval);
        if (isCarouselActive) {
            autoplayInterval = setInterval(function() { moveCarousel(1); }, 5000);
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
            dot.classList.remove("tm-dot--active");
            dot.removeAttribute("aria-current");
        });
        if (dots[currentLeftmost]) {
            dots[currentLeftmost].classList.add("tm-dot--active");
            dots[currentLeftmost].setAttribute("aria-current", "step");
        }
    }

    // Carousel Core Mechanics
    function getSlideWidth() {
        var gap = parseFloat(window.getComputedStyle(grid).gap) || 24;
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

    // Lifecycle methods for dynamically checking screen width
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
        
        // Restore DOM nodes strictly back to their original sequential order
        for (var i = 0; i < originalNodes.length; i++) {
            grid.appendChild(originalNodes[i]);
        }
    }

    function checkResponsive() {
        if (total <= 1) return; // Prevent carousel for 1 or fewer cards inherently
        var cols = getVisibleColumns();
        // If there are more cards than can fit evenly in a row, make it a carousel
        if (total > cols) {
            initCarousel();
        } else {
            destroyCarousel();
        }
    }

    // Event Bindings
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

    // Initial check & resize observer
    var resizeTimer;
    window.addEventListener("resize", function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(checkResponsive, 150);
    });
    checkResponsive();


    // --- 2. PRESERVED MODAL LOGIC ---
    function updateCounter() { counter.textContent = (current + 1) + " / " + total; } 
    
    function getStarHtml(rating) { 
        var html = ""; 
        var r = parseInt(rating, 10) || 5; 
        for (var i = 1; i <= 5; i++) { 
            var activeClass = i <= r ? "tm-star--active" : ""; 
            html += '<div class="tm-star ' + activeClass + '" aria-hidden="true"><svg class="tm-star-svg" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg></div>'; 
        } 
        return html; 
    } 
    
    function populateModal(index) { 
        var item = originalNodes[index]; // Reference original array directly in case DOM shifted
        var avatarUrl = item.dataset.avatar; 
        if (avatarUrl) { 
            modalAvatar.innerHTML = '<img src="' + avatarUrl + '" alt="' + item.dataset.name + '\'s avatar">'; 
            modalAvatar.style.display = 'block'; 
        } else { 
            modalAvatar.innerHTML = ''; 
            modalAvatar.style.display = 'none'; 
        } 
        modalReview.textContent = '"' + item.dataset.review + '"'; 
        modalRating.innerHTML = getStarHtml(item.dataset.rating); 
        modalAuthorName.textContent = item.dataset.name; 
        modalAuthorTitle.textContent = item.dataset.title; 
        current = index; 
        updateCounter(); 
    } 
    
    function showContent(index, direction) { 
        if (isAnimating) return; 
        if (direction) { 
            isAnimating = true; 
            var outClass = direction === "next" ? "tm-slide-left" : "tm-slide-right"; 
            var inClass = direction === "next" ? "tm-slide-in-left" : "tm-slide-in-right"; 
            modalContent.classList.add(outClass); 
            modalContent.addEventListener("animationend", function handler() { 
                modalContent.removeEventListener("animationend", handler); 
                modalContent.classList.remove(outClass); 
                populateModal(index); 
                modalContent.classList.add(inClass); 
                modalContent.addEventListener("animationend", function handler2() { 
                    modalContent.removeEventListener("animationend", handler2); 
                    modalContent.classList.remove(inClass); 
                    isAnimating = false; 
                }); 
            }); 
        } else { 
            populateModal(index); 
        } 
    } 
    
    function openModal(index) { 
        stopAutoplay(); 
        showContent(index); 
        modal.setAttribute("aria-hidden", "false"); 
        document.body.style.overflow = "hidden"; 
    } 
    
    function closeModal() { 
        modal.setAttribute("aria-hidden", "true"); 
        document.body.style.overflow = ""; 
        if (isCarouselActive) startAutoplay(); 
    } 
    
    function goNext() { 
        var next = (current + 1) % total; 
        showContent(next, "next"); 
    } 
    
    function goPrev() { 
        var prev = (current - 1 + total) % total; 
        showContent(prev, "prev"); 
    } 
    
    /* Grid click */ 
    originalNodes.forEach(function (item) { 
        item.addEventListener("click", function () { 
            var idx = parseInt(item.dataset.index, 10); 
            openModal(idx); 
        }); 
        item.addEventListener("keydown", function(e) { 
            if (e.key === "Enter" || e.key === " ") { 
                e.preventDefault(); 
                var idx = parseInt(item.dataset.index, 10); 
                openModal(idx); 
            } 
        }); 
    }); 
    
    /* Close on clicking anywhere in the modal except interactive elements */ 
    modal.addEventListener("click", function (e) { 
        var target = e.target; 
        if (target.closest(".tm-nav") || target.closest(".tm-close") || target.closest(".tm-modal-content")) { 
            return; 
        } 
        closeModal(); 
    }); 
    
    closeBtn.addEventListener("click", function (e) { 
        e.stopPropagation(); 
        closeModal(); 
    }); 
    
    prevBtn.addEventListener("click", function (e) { 
        e.stopPropagation(); 
        goPrev(); 
    }); 
    nextBtn.addEventListener("click", function (e) { 
        e.stopPropagation(); 
        goNext(); 
    }); 
    
    document.addEventListener("keydown", function (e) { 
        if (modal.getAttribute("aria-hidden") !== "false") return; 
        if (e.key === "Escape") closeModal(); 
        else if (e.key === "ArrowLeft") goPrev(); 
        else if (e.key === "ArrowRight") goNext(); 
    }); 
    
    /* Touch swipe mapped to modal */ 
    var touchStartX = 0; 
    var touchStartY = 0; 
    var touchDeltaX = 0; 
    var swiping = false; 
    var SWIPE_THRESHOLD = 40; 
    
    modal.addEventListener("touchstart", function (e) { 
        if (isAnimating) return; 
        if (e.target.closest(".tm-nav") || e.target.closest(".tm-close")) return; 
        touchStartX = e.changedTouches[0].clientX; 
        touchStartY = e.changedTouches[0].clientY; 
        touchDeltaX = 0; 
        swiping = false; 
    }, { passive: true }); 
    
    modal.addEventListener("touchmove", function (e) { 
        if (isAnimating) return; 
        var dx = e.changedTouches[0].clientX - touchStartX; 
        var dy = e.changedTouches[0].clientY - touchStartY; 
        if (Math.abs(dx) > Math.abs(dy)) { 
            touchDeltaX = dx; 
            swiping = true; 
            modalContent.style.transition = "none"; 
            modalContent.style.transform = "translateX(" + (dx * 0.4) + "px) scale(1)"; 
        } 
    }, { passive: true }); 
    
    modal.addEventListener("touchend", function (e) { 
        if (isAnimating) return; 
        modalContent.style.transition = ""; 
        modalContent.style.transform = ""; 
        if (swiping && Math.abs(touchDeltaX) > SWIPE_THRESHOLD) { 
            if (touchDeltaX < 0) goNext(); 
            else goPrev(); 
        } 
        touchDeltaX = 0; 
        swiping = false; 
    }, { passive: true }); 
})();