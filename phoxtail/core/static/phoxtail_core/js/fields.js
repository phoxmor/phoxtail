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

/* Date stepper: the box sends its request on "step". An arrow or a picked day
   sends at once; a date typed key by key waits for Enter or for the box to be
   left, since the browser reports every finished part (the "1" of "15") as a
   change, and the redraw would swallow the next key. */
(function () {
    var STEPPER = '.phx-date-stepper__input';

    function step(input) {
        delete input.dataset.typed;
        input.dispatchEvent(new Event('step'));
    }

    document.addEventListener('click', function (event) {
        var button = event.target.closest('[data-date-step]');
        if (!button) {
            return;
        }
        var input = button.closest('.phx-date-stepper').querySelector(STEPPER);
        input.value = button.dataset.dateStep;
        step(input);
    }, true);

    // A change during a key press was typed; any other came from the picker.
    document.addEventListener('keydown', function (event) {
        if (!event.target.matches(STEPPER)) {
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
        if (event.target.matches(STEPPER)) {
            delete event.target.dataset.keyDown;
        }
    }, true);

    document.addEventListener('change', function (event) {
        var input = event.target;
        if (!input.matches(STEPPER)) {
            return;
        }
        if (input.dataset.keyDown !== undefined) {
            input.dataset.typed = '';
        } else {
            // A pick lets go of the focus before it sends, or htmx gives it
            // back to the redrawn box, which shows the date over the text.
            // Digits typed before the pick go with it, not in a request of
            // their own as the box is left.
            delete input.dataset.typed;
            input.blur();
            step(input);
        }
    }, true);

    // Tab moves focus away before the key comes back up, so leaving the box
    // (or pressing on the pill) forgets the key, or the next pick would be
    // taken for typing and never sent.
    document.addEventListener('focusout', function (event) {
        if (!event.target.matches(STEPPER)) {
            return;
        }
        delete event.target.dataset.keyDown;
        if (event.target.dataset.typed !== undefined) {
            step(event.target);
        }
    }, true);

    document.addEventListener('pointerdown', function (event) {
        var stepper = event.target.closest('.phx-date-stepper');
        if (stepper) {
            delete stepper.querySelector(STEPPER).dataset.keyDown;
        }
    }, true);
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
