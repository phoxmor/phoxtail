(function () {
    var root = document.getElementById("hl-{{ block.id }}");
    if (!root) return;

    /* ── Ember Particles Generation ── */
    var embersEl = root.querySelector("[data-hl-embers]");
    var EMBER_COUNT = 30;
    
    // Updated to strictly use permitted color roles (primary, secondary, accent)
    var colors = [
        "rgb(var(--color-secondary-400))",
        "rgb(var(--color-primary-500))",
        "rgb(var(--color-accent-500))"
    ];

    for (var i = 0; i < EMBER_COUNT; i++) {
        var ember = document.createElement("span");
        ember.className = "hl-ember";
        var size = 2 + Math.random() * 5;
        var left = 20 + Math.random() * 60;
        var dur = 6 + Math.random() * 10;
        var delay = Math.random() * dur;

        ember.style.width = size + "px";
        ember.style.height = size + "px";
        ember.style.left = left + "%";
        ember.style.bottom = "-20px";
        ember.style.color = colors[Math.floor(Math.random() * colors.length)];
        ember.style.backgroundColor = "currentColor";
        ember.style.animationDuration = dur + "s";
        ember.style.animationDelay = "-" + delay + "s";
        
        embersEl.appendChild(ember);
    }

    /* ── Advanced Eye Tracking (Bounded) ── */
    var phoenixWrap = root.querySelector("[data-hl-phoenix]");
    var pupils = root.querySelectorAll("[data-hl-pupil]");
    
    if (!phoenixWrap || !pupils.length) return;

    var MAX_OFFSET = 3.5;
    var targetX = 0, targetY = 0;
    var currentX = 0, currentY = 0;
    var EASE = 0.15;
    var ticking = false;

    function onMove(e) {
        var rect = phoenixWrap.getBoundingClientRect();
        var cx = rect.left + rect.width / 2;
        var cy = rect.top + rect.height * 0.40;
        
        var dx = e.clientX - cx;
        var dy = e.clientY - cy;

        var angle = Math.atan2(dy, dx);
        var dist = Math.min(Math.sqrt(dx * dx + dy * dy) / 40, MAX_OFFSET);

        targetX = Math.cos(angle) * dist;
        targetY = Math.sin(angle) * dist;

        if (!ticking) {
            ticking = true;
            requestAnimationFrame(animate);
        }
    }

    function animate() {
        currentX += (targetX - currentX) * EASE;
        currentY += (targetY - currentY) * EASE;
        
        for (var i = 0; i < pupils.length; i++) {
            pupils[i].setAttribute("transform", "translate(" + currentX.toFixed(2) + " " + currentY.toFixed(2) + ")");
        }

        if (Math.abs(targetX - currentX) > 0.01 || Math.abs(targetY - currentY) > 0.01) {
            requestAnimationFrame(animate);
        } else {
            ticking = false;
        }
    }

    document.addEventListener("mousemove", onMove);

    /* ── Hardware Accelerated Blinking ── */
    var eyesWrap = root.querySelector("[data-hl-eyes-wrap]");
    if (!eyesWrap) return;

    function triggerBlink() {
        eyesWrap.classList.add("is-blinking");
        setTimeout(function () {
            eyesWrap.classList.remove("is-blinking");
        }, 150);
        setTimeout(triggerBlink, 2500 + Math.random() * 4000);
    }

    setTimeout(triggerBlink, 2000);
})();