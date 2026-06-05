(function () {
    var blockEl = document.getElementById('ss-{{ block.id }}');
    if (!blockEl) return;

    var svgEl = document.getElementById('ss-svg-{{ block.id }}');
    var trackEl = document.getElementById('ss-track-{{ block.id }}');
    var fillEl = document.getElementById('ss-fill-{{ block.id }}');
    var anchors = blockEl.querySelectorAll('[data-num-anchor]');

    if (!svgEl || !trackEl || !fillEl || anchors.length < 2) return;

    function isDesktop() {
        return window.innerWidth >= 1024;
    }

    function getCentre(el) {
        var er = el.getBoundingClientRect();
        var br = blockEl.getBoundingClientRect();
        return {
            x: er.left - br.left + er.width / 2,
            y: er.top - br.top + er.height / 2
        };
    }

    function buildPathD() {
        var pts = Array.from(anchors).map(getCentre);
        var desktop = isDesktop();
        var pull = desktop ? Math.min(blockEl.offsetWidth * 0.18, 160) : 0;

        var d = 'M ' + pts[0].x.toFixed(1) + ' ' + pts[0].y.toFixed(1);

        for (var i = 0; i < pts.length - 1; i++) {
            var p0 = pts[i];
            var p1 = pts[i + 1];

            if (pull === 0) {
                d += ' L ' + p1.x.toFixed(1) + ' ' + p1.y.toFixed(1);
            } else {
                var midY = ((p0.y + p1.y) / 2).toFixed(1);
                var dir = (i % 2 === 0) ? 1 : -1;
                var cpx = (p0.x + dir * pull).toFixed(1);
                var cpx2 = (p1.x + dir * pull).toFixed(1);
                d += ' C ' + cpx + ' ' + midY + ', '
                    + cpx2 + ' ' + midY + ', '
                    + p1.x.toFixed(1) + ' ' + p1.y.toFixed(1);
            }
        }

        return d;
    }

    function getScrollProgress() {
        var first = anchors[0].getBoundingClientRect();
        var last = anchors[anchors.length - 1].getBoundingClientRect();
        var vh = window.innerHeight;
        var firstCy = first.top + first.height / 2;
        var lastCy = last.top + last.height / 2;
        var mid = vh / 2;
        var total = lastCy - firstCy;
        var elapsed = mid - firstCy;
        if (total === 0) return 1;
        return Math.max(0, Math.min(1, elapsed / total));
    }

    var pathLength = 0;
    var rafId = null;
    var lastOffset = -1;

    function applyFill() {
        rafId = null;
        if (!pathLength) return;
        var progress = getScrollProgress();
        var offset = (pathLength * (1 - progress)).toFixed(2);
        if (offset === lastOffset) return;
        lastOffset = offset;
        fillEl.style.strokeDashoffset = offset;
    }

    function onScroll() {
        if (rafId) return;
        rafId = requestAnimationFrame(applyFill);
    }

    function updatePath() {
        var d = buildPathD();
        trackEl.setAttribute('d', d);
        fillEl.setAttribute('d', d);
        svgEl.setAttribute('viewBox',
            '0 0 ' + blockEl.offsetWidth + ' ' + blockEl.offsetHeight);

        // On mobile use a solid accent stroke instead of the gradient
        // reference which fails with strokeDashoffset on WebKit mobile
        if (!isDesktop()) {
            var styles = getComputedStyle(blockEl);
            var accent = styles.getPropertyValue('--ss-accent').trim();
            if (accent) {
                fillEl.setAttribute('stroke', 'rgb(' + accent + ')');
            } else {
                fillEl.setAttribute('stroke', 'currentColor');
            }
        } else {
            fillEl.setAttribute('stroke',
                'url(#ss-path-grad-{{ block.id }})');
        }

        requestAnimationFrame(function () {
            pathLength = 0;

            try {
                pathLength = fillEl.getTotalLength();
            } catch (e) {
                pathLength = 0;
            }

            // Fallback: manually sum segment lengths if native fails
            if (!pathLength || isNaN(pathLength) || pathLength < 1) {
                var pts = Array.from(anchors).map(getCentre);
                pathLength = 0;
                for (var i = 0; i < pts.length - 1; i++) {
                    var dx = pts[i + 1].x - pts[i].x;
                    var dy = pts[i + 1].y - pts[i].y;
                    pathLength += Math.sqrt(dx * dx + dy * dy);
                }
            }

            if (pathLength > 0) {
                fillEl.style.strokeDasharray = pathLength;
                fillEl.style.strokeDashoffset = pathLength;
            }

            applyFill();
        });
    }

    function init() {
        updatePath();
        window.addEventListener('scroll', onScroll, { passive: true });

        // Catch late layout shifts from images/fonts on mobile
        setTimeout(updatePath, 600);

        var resizeTimer;
        window.addEventListener('resize', function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(updatePath, 100);
        });
    }

    if (document.readyState === 'complete') {
        init();
    } else {
        window.addEventListener('load', init);
    }
})();