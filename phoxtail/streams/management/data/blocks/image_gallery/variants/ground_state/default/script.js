(function () {
  var root = document.getElementById("image-gallery-{{ block.id }}");
  if (!root) return;

  var items = root.querySelectorAll(".ig-item");
  var modal = root.querySelector(".ig-modal");
  var modalImg = root.querySelector(".ig-modal-image");
  var prevBtn = root.querySelector(".ig-nav--prev");
  var nextBtn = root.querySelector(".ig-nav--next");
  var closeBtn = root.querySelector(".ig-close");
  var counter = root.querySelector(".ig-counter");
  var total = items.length;
  var current = 0;
  var isAnimating = false;

  function updateCounter() {
    counter.textContent = (current + 1) + " / " + total;
  }

  function showImage(index, direction) {
    if (isAnimating) return;
    var item = items[index];
    var src = item.dataset.fullSrc;
    var alt = item.dataset.alt;

    if (direction) {
      isAnimating = true;
      var outClass = direction === "next" ? "ig-slide-left" : "ig-slide-right";
      var inClass = direction === "next" ? "ig-slide-in-left" : "ig-slide-in-right";

      modalImg.classList.add(outClass);
      modalImg.addEventListener("animationend", function handler() {
        modalImg.removeEventListener("animationend", handler);
        modalImg.classList.remove(outClass);
        modalImg.src = src;
        modalImg.alt = alt;
        current = index;
        updateCounter();
        modalImg.classList.add(inClass);
        modalImg.addEventListener("animationend", function handler2() {
          modalImg.removeEventListener("animationend", handler2);
          modalImg.classList.remove(inClass);
          isAnimating = false;
        });
      });
    } else {
      modalImg.src = src;
      modalImg.alt = alt;
      current = index;
      updateCounter();
    }
  }

  function openModal(index) {
    showImage(index);
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    modal.addEventListener("transitionend", function handler() {
      modalImg.src = "";
      modal.removeEventListener("transitionend", handler);
    });
  }

  function goNext() {
    var next = (current + 1) % total;
    showImage(next, "next");
  }

  function goPrev() {
    var prev = (current - 1 + total) % total;
    showImage(prev, "prev");
  }

  /* Grid click */
  items.forEach(function (item) {
    item.addEventListener("click", function () {
      var idx = parseInt(item.dataset.index, 10);
      openModal(idx);
    });
  });

  /* Close on clicking anywhere in the modal except interactive elements */
  modal.addEventListener("click", function (e) {
    var target = e.target;
    /* Don't close if clicking nav arrows, close button, or the image itself */
    if (target.closest(".ig-nav") || target.closest(".ig-close") || target.closest(".ig-modal-image")) {
      return;
    }
    closeModal();
  });

  /* Close button */
  closeBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    closeModal();
  });

  /* Arrow nav */
  prevBtn.addEventListener("click", function (e) { e.stopPropagation(); goPrev(); });
  nextBtn.addEventListener("click", function (e) { e.stopPropagation(); goNext(); });

  /* Keyboard */
  document.addEventListener("keydown", function (e) {
    if (modal.getAttribute("aria-hidden") !== "false") return;
    if (e.key === "Escape") closeModal();
    else if (e.key === "ArrowLeft") goPrev();
    else if (e.key === "ArrowRight") goNext();
  });

  /* Touch swipe on modal */
  var touchStartX = 0;
  var touchStartY = 0;
  var touchDeltaX = 0;
  var swiping = false;
  var SWIPE_THRESHOLD = 40;

  modal.addEventListener("touchstart", function (e) {
    if (isAnimating) return;
    if (e.target.closest(".ig-nav") || e.target.closest(".ig-close")) return;
    touchStartX = e.changedTouches[0].clientX;
    touchStartY = e.changedTouches[0].clientY;
    touchDeltaX = 0;
    swiping = false;
  }, { passive: true });

  modal.addEventListener("touchmove", function (e) {
    if (isAnimating) return;
    var dx = e.changedTouches[0].clientX - touchStartX;
    var dy = e.changedTouches[0].clientY - touchStartY;
    /* Only track horizontal if dominant axis */
    if (Math.abs(dx) > Math.abs(dy)) {
      touchDeltaX = dx;
      swiping = true;
      modalImg.style.transition = "none";
      modalImg.style.transform = "translateX(" + (dx * 0.4) + "px) scale(1)";
    }
  }, { passive: true });

  modal.addEventListener("touchend", function (e) {
    if (isAnimating) return;
    modalImg.style.transition = "";
    modalImg.style.transform = "";

    if (swiping && Math.abs(touchDeltaX) > SWIPE_THRESHOLD) {
      if (touchDeltaX < 0) goNext();
      else goPrev();
    }
    touchDeltaX = 0;
    swiping = false;
  }, { passive: true });
})();