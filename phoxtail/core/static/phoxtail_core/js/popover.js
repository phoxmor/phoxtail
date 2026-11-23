/**
 * Placement for a popover beside its button: a .phx-popover with the popover
 * attribute and data-popover-placement, opened by the button that names it
 * (popovertarget), whether by a click or by a script (showPopover()).
 *
 * data-popover-placement is "<side>-<align>": the side of the button it
 * opens on (top, bottom, left or right) and the button edge it lines up
 * with, as CSS names them: above or below it, start is the edge its text
 * starts from (the left one, the right one in a right-to-left page), end
 * the other; beside it, start is the top edge, end the bottom one.
 * "bottom-end" opens under the button, end edges level. Where the side has
 * no room and the opposite one has more, it opens there instead; along the
 * button it shifts as little as it must to stay inside the window. The gap
 * from the button is --phx-popover-offset (surfaces.css).
 *
 * It is placed as it opens, and again on a resize (a phone's address bar
 * or keyboard showing or hiding resizes the window). It closes rather than
 * drift when a scroll moves its button (a scroll inside it, or one that
 * moves something else, leaves it; so does a scroll the browser reports
 * late, after it opened), when a resize hides its button, and on a choice
 * (a click on a link or a button inside it). The browser closes it on
 * Escape and on a click outside it, and tells assistive technology its
 * button is expanded while it is open.
 *
 * One listener each on the document, so popovers drawn later (htmx) need
 * nothing of their own.
 */
(function () {
    var PLACED = '.phx-popover[popover][data-popover-placement]';
    // How close to the window's edge it may come.
    var EDGE = 12;
    var SIDES = {top: 'bottom', bottom: 'top', left: 'right', right: 'left'};
    // Where each open popover's button was when it was placed.
    var placedAt = new WeakMap();

    function invoker(popover) {
        return popover.id ? document.querySelector('[popovertarget="' + CSS.escape(popover.id) + '"]') : null;
    }

    // Where along one axis something of *size* starts, kept inside the window
    // (*room* long) where it fits, else at its start edge.
    function inside(start, size, room) {
        return Math.max(EDGE, Math.min(start, room - size - EDGE));
    }

    function place(popover) {
        var button = invoker(popover);
        if (!button) {
            return;
        }
        // A button no longer shown (hidden at this window's width, or swapped
        // out) has nowhere to be beside: it closes.
        if (!button.isConnected || !button.getClientRects().length) {
            if (popover.matches(':popover-open')) {
                popover.hidePopover();
            }
            return;
        }
        var parts = popover.dataset.popoverPlacement.split('-');
        var side = SIDES[parts[0]] ? parts[0] : 'bottom';
        var start = parts[1] === 'start';
        var anchor = button.getBoundingClientRect();
        placedAt.set(popover, {button: button, top: anchor.top, left: anchor.left});
        // Measured at the window's corner, at the size it takes with room: where
        // it was last (against an edge) would squeeze it narrower.
        popover.style.left = '0px';
        popover.style.top = '0px';
        var width = popover.offsetWidth;
        var height = popover.offsetHeight;
        var gap = parseFloat(getComputedStyle(popover).getPropertyValue('--phx-popover-offset')) || 0;
        var vertical = side === 'top' || side === 'bottom';
        var size = vertical ? height : width;
        var room = {
            top: anchor.top - gap - EDGE,
            bottom: window.innerHeight - anchor.bottom - gap - EDGE,
            left: anchor.left - gap - EDGE,
            right: window.innerWidth - anchor.right - gap - EDGE
        };
        if (room[side] < size && room[SIDES[side]] > room[side]) {
            side = SIDES[side];
        }
        var left;
        var top;
        if (vertical) {
            top = side === 'bottom' ? anchor.bottom + gap : anchor.top - gap - height;
            // Its text starts from the right in a right-to-left page.
            var leftEdge = start !== (getComputedStyle(button).direction === 'rtl');
            left = leftEdge ? anchor.left : anchor.right - width;
        } else {
            left = side === 'right' ? anchor.right + gap : anchor.left - gap - width;
            top = start ? anchor.top : anchor.bottom - height;
        }
        popover.style.left = inside(left, width, window.innerWidth) + 'px';
        popover.style.top = inside(top, height, window.innerHeight) + 'px';
        popover.dataset.popoverSide = side;
    }

    // Placed as it opens, before its size is known, and again before its
    // first paint, once it is.
    document.addEventListener('beforetoggle', function (event) {
        var popover = event.target;
        if (event.newState !== 'open' || !(popover instanceof Element) || !popover.matches(PLACED)) {
            return;
        }
        place(popover);
        requestAnimationFrame(function () {
            place(popover);
        });
    }, true);

    function moved(popover) {
        var at = placedAt.get(popover);
        if (!at) {
            return true;
        }
        var now = at.button.getBoundingClientRect();
        return Math.abs(now.top - at.top) > 1 || Math.abs(now.left - at.left) > 1;
    }

    // A scroll does not bubble: it is caught on its way down.
    document.addEventListener('scroll', function () {
        document.querySelectorAll(PLACED + ':popover-open').forEach(function (popover) {
            if (moved(popover)) {
                popover.hidePopover();
            }
        });
    }, true);
    window.addEventListener('resize', function () {
        document.querySelectorAll(PLACED + ':popover-open').forEach(place);
    });

    // A choice closes it once the click has done its work (its own
    // listeners, htmx's among them, and a link followed or a form sent).
    // Heard in the capture phase, so a choice inside something that keeps
    // its clicks from bubbling up still closes it.
    document.addEventListener('click', function (event) {
        var choice = event.target instanceof Element ? event.target.closest('a[href], button') : null;
        var popover = choice && choice.closest(PLACED);
        if (popover) {
            setTimeout(function () {
                if (popover.matches(':popover-open')) {
                    popover.hidePopover();
                }
            });
        }
    }, true);
})();
