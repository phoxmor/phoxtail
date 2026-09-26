/**
 * Rising embers behind the auth pages
 *
 * The particles the hatchling homepage shows: they drift upward, sway, and
 * are pushed aside by the mouse. Requires a [data-auth-embers] element fixed
 * to the viewport.
 *
 * Every distance is measured in hundredths of the viewport's shorter side
 * and every speed per second, so a phone sees the same scene as a desktop,
 * only smaller, at any refresh rate.
 */

(function () {
    var embersEl = document.querySelector("[data-auth-embers]");
    if (!embersEl) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    var DENSITY = 45 / (1440 * 900); // embers per square pixel of a laptop screen
    var RISE = [2, 5]; // upward speed
    var DRIFT = 1.5; // largest sideways speed
    var SWAY = 1; // speed of the side-to-side sway
    var SWAY_RATE = 1.2; // radians per second
    var REACH = 12; // how close the mouse must come to push an ember
    var PUSH = 90; // strongest push, as an acceleration
    var SETTLE = 2; // how quickly a pushed ember returns to its own course
    var colors = [
        "rgb(var(--color-secondary-400))",
        "rgb(var(--color-primary-500))",
        "rgb(var(--color-accent-500))"
    ];
    var particles = [];

    var unit, width, height;

    function measure() {
        width = window.innerWidth;
        height = window.innerHeight;
        unit = Math.min(width, height) / 100;
    }

    var mouseX = -1000;
    var mouseY = -1000;

    /* Only a real mouse pushes: a tap on a phone would kick every ember near it */
    window.addEventListener("pointermove", function (e) {
        if (e.pointerType !== "mouse") return;
        mouseX = e.clientX;
        mouseY = e.clientY;
    });

    document.documentElement.addEventListener("mouseleave", function () {
        mouseX = -1000;
        mouseY = -1000;
    });

    function between(range) {
        return range[0] + Math.random() * (range[1] - range[0]);
    }

    function createParticle() {
        var el = document.createElement("span");
        el.className = "auth-bg-ember";
        var size = 2 + Math.random() * 5;
        el.style.width = size + "px";
        el.style.height = size + "px";
        el.style.color = colors[Math.floor(Math.random() * colors.length)];
        el.style.backgroundColor = "currentColor";
        embersEl.appendChild(el);
        return resetParticle({ el: el, size: size }, true);
    }

    function resetParticle(p, isInitial) {
        p.x = Math.random() * width;
        p.y = isInitial ? Math.random() * height : height + 20;

        p.baseVx = (Math.random() - 0.5) * 2 * DRIFT;
        p.baseVy = -between(RISE);

        p.vx = p.baseVx;
        p.vy = p.baseVy;
        p.life = Math.random() * Math.PI * 2;
        p.el.style.opacity = Math.random() * 0.5 + 0.3;
        return p;
    }

    measure();
    var count = Math.max(12, Math.min(45, Math.round(width * height * DENSITY)));
    for (var i = 0; i < count; i++) {
        particles.push(createParticle());
    }

    window.addEventListener("resize", measure);

    var last = performance.now();

    function render(now) {
        /* A long gap (a hidden tab) resumes calmly instead of leaping */
        var dt = Math.min((now - last) / 1000, 0.05);
        last = now;
        var settle = 1 - Math.exp(-SETTLE * dt);
        var reach = REACH * unit;

        for (var i = 0; i < particles.length; i++) {
            var p = particles[i];

            p.vx += (p.baseVx - p.vx) * settle;
            p.vy += (p.baseVy - p.vy) * settle;

            var dx = p.x - mouseX;
            var dy = p.y - mouseY;
            var dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < reach && dist > 0) {
                /* Eases in from the edge of the reach, so there is no sudden kick */
                var t = (reach - dist) / reach;
                var force = t * t * (3 - 2 * t) * PUSH * dt;
                p.vx += (dx / dist) * force;
                p.vy += (dy / dist) * force;
            }

            p.life += SWAY_RATE * dt;
            p.x += (p.vx + Math.sin(p.life) * SWAY) * unit * dt;
            p.y += p.vy * unit * dt;

            p.el.style.transform = "translate3d(" + p.x.toFixed(2) + "px, " + p.y.toFixed(2) + "px, 0)";

            if (p.y < -50 || p.x < -50 || p.x > width + 50) {
                resetParticle(p, false);
            }
        }
        requestAnimationFrame(render);
    }

    requestAnimationFrame(render);
})();
