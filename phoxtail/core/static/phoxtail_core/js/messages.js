/**
 * Toast message system
 *
 * Handles dismiss, auto-hide, and HTMX-driven toast messages.
 * Requires a <template id="toast-template"> element on the page.
 */

function dismissMessage(button) {
    var messageElement = button.closest('[id^="message-"]');
    if (messageElement) {
        messageElement.classList.add('auth-toast--hidden');
        setTimeout(function() {
            if (messageElement.parentNode) {
                messageElement.remove();
            }
        }, 500);
    }
}

function initializeMessages(container) {
    var messages = container.querySelectorAll('[id^="message-"]');

    messages.forEach(function(message, index) {
        setTimeout(function() {
            message.classList.remove('auth-toast--hidden');
        }, index * 150 + 100);

        setTimeout(function() {
            if (message && message.parentNode) {
                message.classList.add('auth-toast--hidden');
                setTimeout(function() {
                    if (message.parentNode) {
                        message.remove();
                    }
                }, 500);
            }
        }, 10000 + (index * 150));
    });
}

document.addEventListener('DOMContentLoaded', function() {
    var messagesContainer = document.getElementById('messages-container');
    if (messagesContainer) {
        initializeMessages(messagesContainer);
    }
});

document.body.addEventListener('htmx:afterSwap', function(event) {
    var messagesContainer = event.detail.target.querySelector('#messages-container');
    if (messagesContainer) {
        initializeMessages(messagesContainer);
    }
});

document.body.addEventListener('htmx:oobAfterSwap', function(event) {
    var messagesContainer = event.detail.target.querySelector('#messages-container');
    if (messagesContainer) {
        initializeMessages(messagesContainer);
    }
});

document.body.addEventListener('showToast', function(event) {
    var detail = event.detail || {};
    var message = detail.message || '';
    var type = detail.type || 'error';

    if (typeof closeModal === 'function') closeModal();

    var wrapper = document.getElementById('messages-container-wrapper');
    if (!wrapper) return;

    var template = document.getElementById('toast-template');
    if (!template) return;

    var clone = template.content.cloneNode(true);
    var toast = clone.querySelector('.auth-toast');
    toast.id = 'message-toast-' + Date.now();
    toast.classList.add('auth-toast--' + type);

    var labelKey = 'label' + type.charAt(0).toUpperCase() + type.slice(1);
    clone.querySelector('[data-toast-label]').textContent = template.dataset[labelKey] || type;
    clone.querySelector('[data-toast-text]').textContent = message;

    wrapper.innerHTML = '';
    var container = document.createElement('div');
    container.id = 'messages-container';
    container.className = 'auth-toast-container';
    var list = document.createElement('div');
    list.className = 'auth-toast-list';
    list.appendChild(clone);
    container.appendChild(list);
    wrapper.appendChild(container);

    initializeMessages(container);
});
