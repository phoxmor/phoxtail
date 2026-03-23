document.addEventListener("DOMContentLoaded", function () {
    const banner = document.querySelector('#image-banner-{{ block.id }}');
    if (!banner) return;

    const slides = banner.querySelectorAll('.ib-slide');
    const dots = banner.querySelectorAll('.ib-dot');
    const slideCount = slides.length;

    if (slideCount <= 1) return;

    let current = 0;
    let autoplayTimer = null;
    const AUTOPLAY_DELAY = 5000;

    function goTo(index) {
        slides[current].classList.remove('ib-slide--active');
        dots[current].classList.remove('ib-dot--active');
        dots[current].removeAttribute('aria-current');

        current = (index + slideCount) % slideCount;

        slides[current].classList.add('ib-slide--active');
        dots[current].classList.add('ib-dot--active');
        dots[current].setAttribute('aria-current', 'step');
    }

    function startAutoplay() {
        stopAutoplay();
        autoplayTimer = setInterval(function () {
            goTo(current + 1);
        }, AUTOPLAY_DELAY);
    }

    function stopAutoplay() {
        if (autoplayTimer) {
            clearInterval(autoplayTimer);
            autoplayTimer = null;
        }
    }

    dots.forEach(function (dot) {
        dot.addEventListener('click', function () {
            var index = parseInt(this.getAttribute('data-index'), 10);
            goTo(index);
            startAutoplay();
        });
    });

    banner.addEventListener('mouseenter', stopAutoplay);
    banner.addEventListener('mouseleave', startAutoplay);
    banner.addEventListener('focusin', stopAutoplay);
    banner.addEventListener('focusout', startAutoplay);

    banner.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowLeft') {
            goTo(current - 1);
            startAutoplay();
        } else if (e.key === 'ArrowRight') {
            goTo(current + 1);
            startAutoplay();
        }
    });

    var touchStartX = 0;
    var touchEndX = 0;
    var SWIPE_THRESHOLD = 50;

    banner.addEventListener('touchstart', function (e) {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    banner.addEventListener('touchend', function (e) {
        touchEndX = e.changedTouches[0].screenX;
        var diff = touchStartX - touchEndX;

        if (Math.abs(diff) > SWIPE_THRESHOLD) {
            if (diff > 0) {
                goTo(current + 1);
            } else {
                goTo(current - 1);
            }
            startAutoplay();
        }
    }, { passive: true });

    if (dots.length > 0) {
        dots[0].setAttribute('aria-current', 'step');
    }

    startAutoplay();
});