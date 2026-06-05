(function () {
    var root = document.getElementById("team-section-{{ block.id }}");
    if (!root) return;

    var items = root.querySelectorAll(".ts-item");
    var modal = root.querySelector(".ts-modal");
    var modalContent = root.querySelector(".ts-modal-content");
    var modalAvatar = root.querySelector(".ts-modal-avatar");
    var modalName = root.querySelector(".ts-modal-name");
    var modalRole = root.querySelector(".ts-modal-role");
    var modalBio = root.querySelector(".ts-modal-bio");
    var modalSocial = root.querySelector(".ts-modal-social");
    var modalButtons = root.querySelector(".ts-modal-buttons");
    var prevBtn = root.querySelector(".ts-nav--prev");
    var nextBtn = root.querySelector(".ts-nav--next");
    var closeBtn = root.querySelector(".ts-close");
    var counter = root.querySelector(".ts-counter");

    var total = items.length;
    var current = 0;
    var isAnimating = false;

    // --- 1. RESPONSIVE CAROUSEL & PAGINATION LOGIC ---
    var carouselWrapper = root.querySelector(".ts-carousel-wrapper");
    var viewport = root.querySelector(".ts-carousel-viewport");
    var grid = root.querySelector(".ts-grid");
    var pagination = root.querySelector(".ts-pagination");
    var dots = root.querySelectorAll(".ts-dot");
    var autoplayInterval = null;
    var isCarouselActive = false;
    var isAnimatingCarousel = false;

    var TRANSITION_STYLE = "transform 500ms cubic-bezier(0.25, 1, 0.5, 1)";
    var originalNodes = [];

    for (var i = 0; i < total; i++) {
        originalNodes.push(items[i]);
    }

    // Changed logic to render max 3 columns for desktop (was 4)
    function getVisibleColumns() {
        if (window.innerWidth >= 1024) return 3;
        if (window.innerWidth >= 768) return 2;
        return 1;
    }

    function startAutoplay() {
        if (autoplayInterval) clearInterval(autoplayInterval);
        if (isCarouselActive) {
            autoplayInterval = setInterval(function () {
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
        dots.forEach(function (dot) {
            dot.classList.remove("ts-dot--active");
            dot.removeAttribute("aria-current");
        });
        if (dots[currentLeftmost]) {
            dots[currentLeftmost].classList.add("ts-dot--active");
            dots[currentLeftmost].setAttribute("aria-current", "step");
        }
    }

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
                if (e.target !== grid || e.propertyName !== "transform") return;
                grid.removeEventListener("transitionend", handler);
                
                grid.style.transition = "none";
                for (var k = 0; k < steps; k++) {
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
            for (var k = 0; k < absSteps; k++) {
                grid.prepend(grid.lastElementChild);
            }
            grid.style.transform = "translateX(-" + (slideWidth * absSteps) + "px)";
            
            void grid.offsetWidth; 
            
            grid.style.transition = TRANSITION_STYLE;
            grid.style.transform = "translateX(0)";

            grid.addEventListener("transitionend", function handler(e) {
                if (e.target !== grid || e.propertyName !== "transform") return;
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

    dots.forEach(function (dot) {
        dot.addEventListener("click", function () {
            var targetIdx = parseInt(dot.dataset.index, 10);
            dotClicked(targetIdx);
            startAutoplay(); 
        });
    });

    carouselWrapper.addEventListener("mouseenter", stopAutoplay);
    carouselWrapper.addEventListener("mouseleave", startAutoplay);
    carouselWrapper.addEventListener("focusin", stopAutoplay);
    carouselWrapper.addEventListener("focusout", startAutoplay);

    var touchStartXOuter = 0;
    var touchEndXOuter = 0;

    viewport.addEventListener("touchstart", function (e) {
        if (!isCarouselActive) return;
        touchStartXOuter = e.changedTouches[0].screenX;
    }, { passive: true });

    viewport.addEventListener("touchend", function (e) {
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
    window.addEventListener("resize", function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(checkResponsive, 150);
    });

    checkResponsive();

    // --- 2. MODAL LOGIC ---
    function updateCounter() {
        counter.textContent = (current + 1) + " / " + total;
    }

    function populateModal(index) {
        var item = originalNodes[index];
        
        var avatarUrl = item.dataset.avatar;
        if (avatarUrl) {
            modalAvatar.innerHTML = '<img src="' + avatarUrl + '" alt="' + item.dataset.name + '">';
            modalAvatar.style.display = "block";
        } else {
            modalAvatar.innerHTML = "";
            modalAvatar.style.display = "none";
        }
        
        modalName.textContent = item.dataset.name;
        modalRole.textContent = item.dataset.role || "";
        modalRole.style.display = item.dataset.role ? "block" : "none";

        // Populate bio from the card layout, discarding clamp wrapper styling
        var bioEl = item.querySelector(".ts-card-bio");
        modalBio.innerHTML = bioEl ? bioEl.innerHTML : "";
        modalBio.style.display = bioEl && bioEl.innerHTML.trim() ? "block" : "none";

        // Populate social data from the card layout
        var socialEl = item.querySelector(".ts-card-social");
        modalSocial.innerHTML = socialEl ? socialEl.innerHTML : "";
        modalSocial.style.display = socialEl && socialEl.innerHTML.trim() ? "flex" : "none";

        // Populate buttons from the card layout
        var buttonsEl = item.querySelector(".ts-card-button-wrap");
        modalButtons.innerHTML = buttonsEl ? buttonsEl.innerHTML : "";
        modalButtons.style.display = buttonsEl && buttonsEl.innerHTML.trim() ? "flex" : "none";

        current = index;
        updateCounter();
    }

    function showContent(index, direction) {
        if (isAnimating) return;
        if (direction) {
            isAnimating = true;
            var outClass = direction === "next" ? "ts-slide-left" : "ts-slide-right";
            var inClass = direction === "next" ? "ts-slide-in-left" : "ts-slide-in-right";
            
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

    originalNodes.forEach(function (item) {
        item.addEventListener("click", function (e) {
            // Prevent opening the modal if a social link or button is clicked directly on the card
            if (e.target.closest('.ts-social-link') || e.target.closest('.ts-btn')) return;
            openModal(parseInt(item.dataset.index, 10));
        });
        
        item.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") {
                if (e.target.closest('.ts-social-link') || e.target.closest('.ts-btn')) return;
                e.preventDefault();
                openModal(parseInt(item.dataset.index, 10));
            }
        });
    });

    modal.addEventListener("click", function (e) {
        var target = e.target;
        if (target.closest(".ts-nav") || target.closest(".ts-close") || target.closest(".ts-modal-content")) {
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

    var touchStartX = 0;
    var touchStartY = 0;
    var touchDeltaX = 0;
    var swiping = false;
    var SWIPE_THRESHOLD = 40;

    modal.addEventListener("touchstart", function (e) {
        if (isAnimating) return;
        if (e.target.closest(".ts-nav") || e.target.closest(".ts-close")) return;
        
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