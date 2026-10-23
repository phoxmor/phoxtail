/**
 * The language menu (phoxtail_core/language_menu.html): its button opens and
 * closes the list; a click outside the menu or Escape closes it.
 *
 * One listener on the document, so it needs no element when it loads and
 * works for every menu on the page.
 */
(function () {
    var MENU = '[data-language-menu]';
    var OPEN = 'phx-language-menu--open';

    function setOpen(menu, open) {
        menu.classList.toggle(OPEN, open);
        menu.querySelector('.phx-language-menu__button').setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    document.addEventListener('click', function (event) {
        var menu = event.target.closest(MENU);
        document.querySelectorAll(MENU + '.' + OPEN).forEach(function (open) {
            if (open !== menu) {
                setOpen(open, false);
            }
        });
        if (menu && event.target.closest('.phx-language-menu__button')) {
            setOpen(menu, !menu.classList.contains(OPEN));
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') {
            return;
        }
        document.querySelectorAll(MENU + '.' + OPEN).forEach(function (menu) {
            setOpen(menu, false);
            menu.querySelector('.phx-language-menu__button').focus();
        });
    });
})();
