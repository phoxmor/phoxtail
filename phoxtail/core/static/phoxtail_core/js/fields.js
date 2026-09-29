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

/* Search field: its button opens and closes the panel it controls; a click
   outside the field or Escape closes it. */
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
        document.querySelectorAll('[data-search-trigger][aria-expanded="true"]').forEach(function (trigger) {
            if (!trigger.parentElement.contains(event.target)) {
                setSearchPanel(trigger, false);
            }
        });
        // The clear button inside the trigger makes its own request.
        var trigger = event.target.closest('button, [data-search-trigger]');
        if (trigger && trigger.matches('[data-search-trigger]')) {
            setSearchPanel(trigger, trigger.getAttribute('aria-expanded') !== 'true');
        }
    }, true);

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            document.querySelectorAll('[data-search-trigger][aria-expanded="true"]').forEach(function (trigger) {
                setSearchPanel(trigger, false);
            });
        } else if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-search-trigger]')) {
            event.preventDefault();
            setSearchPanel(event.target, event.target.getAttribute('aria-expanded') !== 'true');
        }
    });
})();

/* A new pick clears the search field's error: the line under the field sits
   outside the part htmx redraws. */
document.addEventListener('htmx:afterSwap', function (event) {
    var field = event.detail.target.closest('[data-search-field]');
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
