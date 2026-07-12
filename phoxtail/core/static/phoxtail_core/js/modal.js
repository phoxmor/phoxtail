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
 * Close base modal (level 0)
 */
window.closeModal = function() {
    _closeModalGeneric('base-modal');
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
    const animationType = firstChild
        ? firstChild.getAttribute('data-modal-animation') || 'fade'
        : 'fade';

    // Set the animation type — since the placeholder starts with no
    // animation attribute, this assignment triggers the CSS animation
    // on the first browser paint after swap.
    content.setAttribute('data-animation-type', animationType);
}

/**
 * Initialize modal system
 * Sets up event listeners for escape key and HTMX events
 */
(function() {
    // Handle escape key to close modals (closes topmost modal first)
    document.addEventListener('keyup', function(e) {
        if (e.key === 'Escape') {
            // Try to close level 1 first, then base modal
            if (document.getElementById('base-modal-level-1')) {
                closeModalLevel1();
            } else if (document.getElementById('base-modal')) {
                window.closeModal();
            }
        }
    });

    // Listen for HTMX content loaded event to configure animations.
    // The modal shell + content arrive in a single swap into the
    // wrapper element, so we listen on both wrapper and placeholder IDs.
    document.addEventListener('htmx:afterSwap', function(event) {
        var targetId = event.target.id;

        if (targetId === 'core-modal-placeholder-wrapper' ||
            targetId === 'core-modal-placeholder') {
            _configureModalAnimation('base-modal', 'core-modal-placeholder');
        } else if (targetId === 'core-modal-level-1-placeholder-wrapper' ||
                   targetId === 'core-modal-level-1-placeholder') {
            _configureModalAnimation('base-modal-level-1', 'core-modal-level-1-placeholder');
        }
    });
})();
