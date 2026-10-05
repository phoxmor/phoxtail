/**
 * Field behaviour shared by core's field templates.
 *
 * One listener on the document, so fields swapped in by htmx work without
 * running any script of their own. It listens in the capture phase: modal
 * drawers stopPropagation() on clicks inside them, which would hide the
 * click from a listener waiting for it to bubble up.
 */

document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-password-toggle]');
    if (!button) {
        return;
    }
    var input = button.closest('.phx-field__box').querySelector('.phx-field__control');
    var isVisible = input.type === 'text';
    input.type = isVisible ? 'password' : 'text';
    button.setAttribute('aria-pressed', isVisible ? 'false' : 'true');
    button.querySelector('.phx-input__password-eye--show').style.display = isVisible ? '' : 'none';
    button.querySelector('.phx-input__password-eye--hide').style.display = isVisible ? 'none' : '';
}, true);

document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-picker-open]');
    if (!button) {
        return;
    }
    var input = button.closest('.phx-field__box').querySelector('.phx-field__control');
    try {
        input.showPicker();
    } catch (error) {
        // Browsers without showPicker(), or a picker the user has not
        // activated yet: focusing still lets them type or use the keyboard.
        input.focus();
    }
}, true);

/* Date boxes that send on "step" (hx_trigger="step": the date and week
   steppers', and any date field that redraws itself as it is filled in). A
   button that carries a day (an arrow, a week's day) puts it in the box of
   its stepper (data-date-steps) and sends at once, as a picked day does; a
   date typed key by key waits for Enter or for the box to be left, since the
   browser reports every finished part (the "1" of "15") as a change, and the
   redraw would swallow the next key. */
(function () {
    var STEP_BOX = 'input[type="date"][hx-trigger~="step"]';

    function step(input) {
        delete input.dataset.typed;
        input.dispatchEvent(new Event('step'));
    }

    document.addEventListener('click', function (event) {
        var button = event.target.closest('[data-date-step]');
        if (!button) {
            return;
        }
        var input = button.closest('[data-date-steps]').querySelector('input');
        input.value = button.dataset.dateStep;
        step(input);
    }, true);

    // A change during a key press was typed; any other came from the picker.
    document.addEventListener('keydown', function (event) {
        if (!event.target.matches(STEP_BOX)) {
            return;
        }
        if (event.key === 'Enter') {
            event.preventDefault();
            if (event.target.dataset.typed !== undefined) {
                step(event.target);
            }
            return;
        }
        event.target.dataset.keyDown = '';
    }, true);

    document.addEventListener('keyup', function (event) {
        if (event.target.matches(STEP_BOX)) {
            delete event.target.dataset.keyDown;
        }
    }, true);

    document.addEventListener('change', function (event) {
        var input = event.target;
        if (!input.matches(STEP_BOX)) {
            return;
        }
        if (input.dataset.keyDown !== undefined) {
            input.dataset.typed = '';
        } else {
            // A pick lets go of the focus before it sends, or htmx gives it
            // back to the redrawn box. Digits typed before the pick go with
            // it, not in a request of their own as the box is left.
            delete input.dataset.typed;
            input.blur();
            step(input);
        }
    }, true);

    // Tab moves focus away before the key comes back up, so leaving the box
    // (or pressing on the pill) forgets the key, or the next pick would be
    // taken for typing and never sent.
    document.addEventListener('focusout', function (event) {
        if (!event.target.matches(STEP_BOX)) {
            return;
        }
        delete event.target.dataset.keyDown;
        if (event.target.dataset.typed !== undefined) {
            step(event.target);
        }
    }, true);

    document.addEventListener('pointerdown', function (event) {
        var stepper = event.target.closest('[data-date-steps]');
        var box = event.target.matches(STEP_BOX) ? event.target : stepper && stepper.querySelector(STEP_BOX);
        if (box) {
            delete box.dataset.keyDown;
        }
    }, true);
})();

/* Week stepper: its three groups (the calendar and Today, the arrows, the
   days) on one row where all seven circles fit there whole; else the two
   others above the days, side by side where they fit, one under the other
   where not. Each layout is tried afresh, since the stepper's width follows
   its layout. The days take as many columns as fit without shrinking a
   circle, the rows as even as they can be (4 and 3 rather than 6 and 1).
   Layout and count go on the stepper, not its days: htmx gives the days their
   new attributes on a redraw, which would drop them. A resize is watched per
   stepper. Each one is met wherever it comes from (the page, an htmx swap,
   an out-of-band one, any script): the browser reports every node added to
   the page, before it paints them, so a new week never shows unlaid. htmx's
   own events would not do: an out-of-band swap's fires on the element that
   asked, which the same answer may have replaced. A stepper taken off the
   page is no longer watched. A click on the calendar's date box opens the
   browser's picker for a mouse; a tap opens it by itself. */
(function () {
    var DAYS = '.phx-week-stepper__days';

    function room(days) {
        var style = getComputedStyle(days);
        // Half a pixel spare, for a box exactly seven circles wide that
        // rounding could leave a hair short.
        return days.getBoundingClientRect().width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) + 0.5;
    }

    function circle(days) {
        return parseFloat(getComputedStyle(days.querySelector('.phx-week-stepper__day')).minWidth);
    }

    function layout(days) {
        if (!days.querySelector('.phx-week-stepper__day')) {
            return;
        }
        var stepper = days.closest('.phx-week-stepper');
        var classes = stepper.classList;
        classes.remove('phx-week-stepper--stacked');
        classes.add('phx-week-stepper--wide');
        if (room(days) < 7 * circle(days)) {
            classes.remove('phx-week-stepper--wide');
            var jump = stepper.querySelector('.phx-week-stepper__jump').getBoundingClientRect();
            if (stepper.querySelector('.phx-week-stepper__nav').getBoundingClientRect().top >= jump.bottom) {
                classes.add('phx-week-stepper--stacked');
            }
        }
        var fit = Math.max(1, Math.min(7, Math.floor(room(days) / circle(days))));
        stepper.style.setProperty('--phx-week-stepper-columns', Math.ceil(7 / Math.ceil(7 / fit)));
    }

    document.addEventListener('click', function (event) {
        if (event.target.matches('.phx-week-stepper__box')) {
            try {
                event.target.showPicker();
            } catch (error) {
                // Already open from the tap itself, or no showPicker().
            }
        }
    }, true);

    var resized = new ResizeObserver(function (entries) {
        entries.forEach(function (entry) {
            layout(entry.target);
        });
    });

    function meet(days) {
        layout(days);
        resized.observe(days);
    }

    // A week added, or a day added to one (a page still being read adds a
    // week before its days).
    function arrived(node) {
        if (node.nodeType !== Node.ELEMENT_NODE || !node.isConnected) {
            return;
        }
        var days = node.closest(DAYS);
        if (days) {
            meet(days);
        } else {
            node.querySelectorAll(DAYS).forEach(meet);
        }
    }

    function left(node) {
        if (node.nodeType !== Node.ELEMENT_NODE) {
            return;
        }
        if (node.matches(DAYS)) {
            resized.unobserve(node);
        }
        node.querySelectorAll(DAYS).forEach(function (days) {
            resized.unobserve(days);
        });
    }

    new MutationObserver(function (records) {
        records.forEach(function (record) {
            record.removedNodes.forEach(left);
            record.addedNodes.forEach(arrived);
        });
    }).observe(document.documentElement, {childList: true, subtree: true});

    document.querySelectorAll(DAYS).forEach(meet);
})();

/* Single select search: its button opens and closes the panel it controls; a
   click outside the field or Escape closes it. */
(function () {
    function setSearchPanel(trigger, open) {
        var panel = document.getElementById(trigger.getAttribute('aria-controls'));
        if (!panel) {
            return;
        }
        panel.classList.toggle('phx-hidden', !open);
        trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
        var input = open && panel.querySelector('input');
        if (input) {
            setTimeout(function () { input.focus(); }, 0);
        }
    }

    document.addEventListener('click', function (event) {
        document.querySelectorAll('[data-single-select-search-trigger][aria-expanded="true"]').forEach(function (trigger) {
            if (!trigger.parentElement.contains(event.target)) {
                setSearchPanel(trigger, false);
            }
        });
        // The clear button inside the trigger makes its own request.
        var trigger = event.target.closest('button, [data-single-select-search-trigger]');
        if (trigger && trigger.matches('[data-single-select-search-trigger]')) {
            setSearchPanel(trigger, trigger.getAttribute('aria-expanded') !== 'true');
        }
    }, true);

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            document.querySelectorAll('[data-single-select-search-trigger][aria-expanded="true"]').forEach(function (trigger) {
                setSearchPanel(trigger, false);
            });
        } else if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-single-select-search-trigger]')) {
            event.preventDefault();
            setSearchPanel(event.target, event.target.getAttribute('aria-expanded') !== 'true');
        }
    });
})();

/* Search bar: the magnifier gives way to the clear button once there is
   text. Enter and the clear button send the request at once (the box's
   "search" trigger); Enter would otherwise submit the page's form and reload
   the page. A box that makes no request (no hx-trigger) keeps the browser's
   own Enter. The clear button leaves the cursor in the box. */
(function () {
    function showClear(bar, show) {
        bar.querySelector('[data-search-icon]').classList.toggle('phx-hidden', show);
        bar.querySelector('[data-search-clear]').classList.toggle('phx-hidden', !show);
    }

    document.addEventListener('input', function (event) {
        var bar = event.target.closest('.phx-search');
        if (bar && event.target.matches('.phx-search__input')) {
            showClear(bar, event.target.value.trim().length > 0);
        }
    }, true);

    document.addEventListener('click', function (event) {
        var button = event.target.closest('[data-search-clear]');
        if (!button) {
            return;
        }
        var bar = button.closest('.phx-search');
        var input = bar.querySelector('.phx-search__input');
        input.value = '';
        showClear(bar, false);
        input.focus();
        if (input.hasAttribute('hx-trigger')) {
            input.dispatchEvent(new Event('search'));
        }
    }, true);

    document.addEventListener('keydown', function (event) {
        var box = event.target;
        if (event.key === 'Enter' && !event.isComposing && box.matches('.phx-search__input[hx-trigger]')) {
            event.preventDefault();
            box.dispatchEvent(new Event('search'));
        }
    }, true);
})();

/* A new pick clears the single select search's error: the line under the
   field sits outside the part htmx redraws. */
document.addEventListener('htmx:afterSwap', function (event) {
    var field = event.detail.target.closest('[data-single-select-search]');
    if (!field || !event.detail.target.matches('.phx-single-select-search__container')) {
        return;
    }
    if (field.classList.contains('phx-field--error')) {
        field.classList.remove('phx-field--error');
        var errors = field.querySelector(':scope > .phx-field__supporting');
        if (errors) {
            errors.remove();
        }
    }
});
