/**
 * Generic modal close handler
 * @param {string} modalId - The ID of the modal to close
 */
function _closeModalGeneric(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('closing');
        // animationend bubbles: a shorter animation ending anywhere inside
        // the content would remove the modal early and truncate the exit.
        // Only the modal's own closing animation (fadeOut on the shell)
        // may trigger removal.
        const onEnd = (e) => {
            if (e.target !== modal) return;
            modal.removeEventListener('animationend', onEnd);
            modal.remove();
        };
        modal.addEventListener('animationend', onEnd);
    }
}

/**
 * Close a modal. Given an element inside one (a drawer's close button, say),
 * the modal it is in, at whichever level; given nothing, the base modal
 * (level 0).
 * @param {Element} [el] - An element inside the modal to close
 */
window.closeModal = function(el) {
    const modal = el instanceof Element ? el.closest('#base-modal, #base-modal-level-1') : null;
    _closeModalGeneric(modal ? modal.id : 'base-modal');
};

/**
 * Dismiss a modal the way a click outside it or Escape does: close it,
 * unless its content asks to be closed only by its own buttons
 * (data-modal-dismiss="button", modal_drawer.html's dismiss block).
 * @param {Element} [el] - An element inside the modal to dismiss
 */
window.dismissModal = function(el) {
    const modal = el instanceof Element ? el.closest('#base-modal, #base-modal-level-1') : null;
    const target = modal || document.getElementById('base-modal');
    if (!target || target.querySelector('[data-modal-dismiss="button"]')) return;
    _closeModalGeneric(target.id);
};

/**
 * Close level 1 modal
 */
function closeModalLevel1() {
    _closeModalGeneric('base-modal-level-1');
}

/**
 * Configure modal content animation based on loaded content
 * @param {string} modalId - The ID of the modal container
 * @param {string} placeholderId - The ID of the content placeholder
 */
function _configureModalAnimation(modalId, placeholderId) {
    const modal = document.getElementById(modalId);
    const content = document.getElementById(placeholderId);

    if (!modal || !content) return;

    const firstChild = content.firstElementChild;
    // A drawer states its side (modal_drawer.html); the side decides how it
    // moves. Other content may still name its animation.
    const sideAnimation = {right: 'slide-right', left: 'slide-left', center: 'fade'};
    const animationType = firstChild
        ? sideAnimation[firstChild.getAttribute('data-modal-side')] ||
          firstChild.getAttribute('data-modal-animation') || 'fade'
        : 'fade';

    // Set the animation type — since the placeholder starts with no
    // animation attribute, this assignment triggers the CSS animation
    // on the first browser paint after swap.
    content.setAttribute('data-animation-type', animationType);
}

/**
 * Name a modal's dialog by its content's title (its first heading), for
 * assistive technology. A title without an id takes one from its modal's,
 * so stacked modals never share one.
 * @param {string} modalId - The ID of the modal container
 * @param {string} placeholderId - The ID of the content placeholder
 */
function _labelModal(modalId, placeholderId) {
    const modal = document.getElementById(modalId);
    const content = document.getElementById(placeholderId);

    if (!modal || !content) return;

    const title = content.querySelector('h1, h2, h3');
    if (!title) return;
    if (!title.id) title.id = modalId + '-title';
    modal.setAttribute('aria-labelledby', title.id);
}

/**
 * Initialize modal system
 * Sets up event listeners for escape key and HTMX events
 */
(function() {
    // Escape dismisses the topmost modal (dismissModal: not one that is
    // closed only by its own buttons).
    document.addEventListener('keyup', function(e) {
        if (e.key === 'Escape') {
            const top = document.getElementById('base-modal-level-1') || document.getElementById('base-modal');
            if (top) window.dismissModal(top);
        }
    });

    // The closeModal client event (an HX-Trigger from the server) closes the
    // modal holding the element that sent the request, at whichever level;
    // sent from outside any modal, the base one. A toast (showToast,
    // messages.js) closes nothing: an action that should close its modal
    // sends this event beside it.
    document.addEventListener('closeModal', function(event) {
        window.closeModal(event.target);
    });

    // Listen for HTMX content loaded event to configure animations.
    // The modal shell + content arrive in a single swap into the
    // wrapper element, so we listen on both wrapper and placeholder IDs.
    document.addEventListener('htmx:afterSwap', function(event) {
        var targetId = event.target.id;

        if (targetId === 'core-modal-placeholder-wrapper' ||
            targetId === 'core-modal-placeholder') {
            _configureModalAnimation('base-modal', 'core-modal-placeholder');
            _labelModal('base-modal', 'core-modal-placeholder');
        } else if (targetId === 'core-modal-level-1-placeholder-wrapper' ||
                   targetId === 'core-modal-level-1-placeholder') {
            _configureModalAnimation('base-modal-level-1', 'core-modal-level-1-placeholder');
            _labelModal('base-modal-level-1', 'core-modal-level-1-placeholder');
        }
    });
})();
