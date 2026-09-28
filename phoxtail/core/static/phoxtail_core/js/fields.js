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
    var input = button.closest('.fw-md3-outlined').querySelector('.fw-md3-control');
    var isVisible = input.type === 'text';
    input.type = isVisible ? 'password' : 'text';
    button.setAttribute('aria-pressed', isVisible ? 'false' : 'true');
    button.querySelector('.fw-password-eye--show').style.display = isVisible ? '' : 'none';
    button.querySelector('.fw-password-eye--hide').style.display = isVisible ? 'none' : '';
}, true);
