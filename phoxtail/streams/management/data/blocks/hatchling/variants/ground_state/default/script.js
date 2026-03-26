(function () {
    var root = document.getElementById("m3-hatch-{{ block.id }}");
    if (!root) return;

    /* ── Advanced Eye Tracking (Bounded) ── */
    var phoenixWrap = root.querySelector("[data-m3-phoenix]");
    var pupils = root.querySelectorAll("[data-m3-pupil]");
    
    if (phoenixWrap && pupils.length) {
        var MAX_OFFSET = 3.5;
        var targetX = 0, targetY = 0;
        var currentX = 0, currentY = 0;
        var EASE = 0.15;
        var tickingEyes = false;

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

            if (!tickingEyes) {
                tickingEyes = true;
                requestAnimationFrame(animateEyes);
            }
        }

        function animateEyes() {
            currentX += (targetX - currentX) * EASE;
            currentY += (targetY - currentY) * EASE;
            
            for (var i = 0; i < pupils.length; i++) {
                pupils[i].setAttribute("transform", "translate(" + currentX.toFixed(2) + " " + currentY.toFixed(2) + ")");
            }

            if (Math.abs(targetX - currentX) > 0.01 || Math.abs(targetY - currentY) > 0.01) {
                requestAnimationFrame(animateEyes);
            } else {
                tickingEyes = false;
            }
        }

        document.addEventListener("mousemove", onMove);
    }

    /* ── Hardware Accelerated Blinking ── */
    var eyesWrap = root.querySelector("[data-m3-eyes-wrap]");
    if (eyesWrap) {
        function triggerBlink() {
            eyesWrap.classList.add("is-blinking");
            setTimeout(function () {
                eyesWrap.classList.remove("is-blinking");
            }, 150);
            setTimeout(triggerBlink, 2500 + Math.random() * 4000);
        }
        setTimeout(triggerBlink, 2000);
    }

    /* ── Free-Floating Embers ── */
    var embersEl = root.querySelector("[data-m3-embers]");
    if (embersEl) {
        var EMBER_COUNT = 45;
        var colors = [
            "rgb(var(--color-secondary-400))",
            "rgb(var(--color-primary-500))",
            "rgb(var(--color-accent-500))"
        ];
        var particles = [];

        function createParticle() {
            var el = document.createElement("span");
            el.className = "m3-ember";
            var size = 2 + Math.random() * 5;
            el.style.width = size + "px";
            el.style.height = size + "px";
            el.style.color = colors[Math.floor(Math.random() * colors.length)];
            el.style.backgroundColor = "currentColor";
            embersEl.appendChild(el);
            return resetParticle({ el: el, size: size }, true);
        }

        function resetParticle(p, isInitial) {
            var rootRect = root.getBoundingClientRect();
            var w = rootRect.width || window.innerWidth;
            var h = rootRect.height || window.innerHeight;
            p.x = Math.random() * w;
            p.y = isInitial ? Math.random() * h : h + 20;
            p.vx = (Math.random() - 0.5) * 1.5;
            p.vy = -(1 + Math.random() * 1.5);
            p.life = Math.random() * Math.PI * 2;
            p.el.style.opacity = Math.random() * 0.5 + 0.3;
            return p;
        }

        for (var i = 0; i < EMBER_COUNT; i++) {
            particles.push(createParticle());
        }

        function renderEmbers() {
            var rootRect = root.getBoundingClientRect();
            var w = rootRect.width || window.innerWidth;
            
            for (var i = 0; i < particles.length; i++) {
                var p = particles[i];
                p.life += 0.03;
                p.x += p.vx + Math.sin(p.life) * 0.5;
                p.y += p.vy;
                p.el.style.transform = "translate3d(" + p.x.toFixed(2) + "px, " + p.y.toFixed(2) + "px, 0)";
                
                if (p.y < -50 || p.x < -50 || p.x > w + 50) {
                    resetParticle(p, false);
                }
            }
            requestAnimationFrame(renderEmbers);
        }
        
        requestAnimationFrame(renderEmbers);
    }
})();