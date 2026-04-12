(function () {
    'use strict';

    function initBlogPostList(wrapper) {
        var id = wrapper.dataset.bplId;
        var searchInput = document.getElementById('bpl-input-' + id);
        var clearBtn = document.getElementById('bpl-clear-' + id);
        var searchIcon = document.getElementById('bpl-icon-' + id);

        if (!searchInput || !clearBtn || !searchIcon) return;

        function showClear() {
            searchIcon.classList.add('bpl-hidden');
            clearBtn.classList.remove('bpl-hidden');
        }

        function showSearch() {
            clearBtn.classList.add('bpl-hidden');
            searchIcon.classList.remove('bpl-hidden');
        }

        clearBtn.addEventListener('click', function () {
            searchInput.value = '';
            showSearch();
            searchInput.dispatchEvent(new Event('keyup', { bubbles: true }));
        });

        searchInput.addEventListener('input', function () {
            if (this.value.trim().length > 0) {
                showClear();
            } else {
                showSearch();
            }
        });
    }

    function initAll() {
        document.querySelectorAll('[data-bpl-id]').forEach(initBlogPostList);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
})();