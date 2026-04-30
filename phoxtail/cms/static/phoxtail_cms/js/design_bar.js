(function () {
    var manifestEl = document.getElementById('phoxtail-design-bar-manifest');
    if (!manifestEl) return;

    var manifest = JSON.parse(manifestEl.textContent);
    var bar = document.getElementById('phoxtail-design-bar');
    var blocksBtn = document.getElementById('phoxtail-design-bar-blocks-btn');
    var panel = document.getElementById('phoxtail-design-bar-blocks-panel');
    var closeBtn = document.getElementById('phoxtail-design-bar-panel-close');

    // ── Panel open / close ──────────────────────────────────────────────────

    function isOpen() {
        return panel && panel.classList.contains('phoxtail-design-bar-panel--open');
    }
    function openPanel() {
        panel.classList.add('phoxtail-design-bar-panel--open');
        blocksBtn.classList.add('phoxtail-design-bar-btn--active');
        blocksBtn.setAttribute('aria-expanded', 'true');
    }
    function closePanel() {
        panel.classList.remove('phoxtail-design-bar-panel--open');
        blocksBtn.classList.remove('phoxtail-design-bar-btn--active');
        blocksBtn.setAttribute('aria-expanded', 'false');
    }

    if (blocksBtn && panel) {
        blocksBtn.addEventListener('click', function () {
            isOpen() ? closePanel() : openPanel();
        });
        closeBtn.addEventListener('click', closePanel);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                if (_hlTarget) { dismissHighlight(); return; }
                if (isOpen()) { closePanel(); return; }
                return;
            }
            if ((e.key === 'b' || e.key === 'B') && blocksBtn) {
                if (e.altKey || e.ctrlKey || e.metaKey) return;
                var tag = document.activeElement && document.activeElement.tagName;
                if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
                if (document.activeElement && document.activeElement.isContentEditable) return;
                isOpen() ? closePanel() : openPanel();
            }
        });
        document.addEventListener('click', function (e) {
            if (isOpen() && !bar.contains(e.target)) closePanel();
        });
    }

    // ── Copy to clipboard ───────────────────────────────────────────────────

    function copyText(text, btn) {
        navigator.clipboard.writeText(text).then(function () {
            btn.classList.add('phoxtail-design-bar-copy-btn--copied');
            setTimeout(function () { btn.classList.remove('phoxtail-design-bar-copy-btn--copied'); }, 1400);
        });
    }

    bar.addEventListener('click', function (e) {
        var copyBtn = e.target.closest('.phoxtail-design-bar-copy-btn');
        if (!copyBtn) return;
        e.stopPropagation();

        var row = copyBtn.closest('[data-phoxtail-design-bar-copy]');
        if (!row) return;

        var payload;
        if (row.dataset.phoxtailDesignBarCopy === 'page') {
            payload = {
                page_id: manifest.id,
                page_type: manifest.type,
                slug: manifest.slug,
                locale: manifest.locale,
                live: manifest.live
            };
        } else if (row.dataset.phoxtailDesignBarCopy === 'block') {
            payload = {
                page_id: manifest.id,
                block_uuid: row.dataset.phoxtailDesignBarUuid,
                block_type: row.dataset.phoxtailDesignBarType
            };
            if (row.dataset.phoxtailDesignBarVariantId) {
                payload.variant_id = parseInt(row.dataset.phoxtailDesignBarVariantId, 10);
                payload.variant_identifier = row.dataset.phoxtailDesignBarVariantIdentifier;
            }
        }

        if (payload) copyText(JSON.stringify(payload, null, 2), copyBtn);
    });

    // ── Block highlight — fixed-position body overlay, immune to block CSS ──

    var _hlEl = null;
    var _hlTarget = null;
    var _hlRaf = null;

    function getHighlightEl() {
        if (!_hlEl) {
            _hlEl = document.createElement('div');
            _hlEl.id = 'phoxtail-design-bar-highlight';
            _hlEl.innerHTML =
                '<div class="phoxtail-design-bar-highlight-corner phoxtail-design-bar-highlight-corner--tl"></div>' +
                '<div class="phoxtail-design-bar-highlight-corner phoxtail-design-bar-highlight-corner--tr"></div>' +
                '<div class="phoxtail-design-bar-highlight-corner phoxtail-design-bar-highlight-corner--bl"></div>' +
                '<div class="phoxtail-design-bar-highlight-corner phoxtail-design-bar-highlight-corner--br"></div>';
            document.body.appendChild(_hlEl);
        }
        return _hlEl;
    }

    function cancelHighlight() {
        if (_hlRaf) { cancelAnimationFrame(_hlRaf); _hlRaf = null; }
        _hlTarget = null;
    }

    function dismissHighlight() {
        cancelHighlight();
        getHighlightEl().classList.remove('phoxtail-design-bar-highlight--visible');
    }

    function highlightBlock(target) {
        cancelHighlight();
        _hlTarget = target;

        var hl = getHighlightEl();
        function updatePos() {
            if (!_hlTarget) return;
            if (!_hlTarget.isConnected) { dismissHighlight(); return; }
            var r = _hlTarget.getBoundingClientRect();
            hl.style.top = r.top + 'px';
            hl.style.left = r.left + 'px';
            hl.style.width = r.width + 'px';
            hl.style.height = r.height + 'px';
            _hlRaf = requestAnimationFrame(updatePos);
        }

        updatePos();
        hl.classList.add('phoxtail-design-bar-highlight--visible');
    }

    document.addEventListener('click', function (e) {
        if (!_hlTarget) return;
        if (bar.contains(e.target)) return;
        if (_hlTarget.contains(e.target)) return;
        dismissHighlight();
    });

    // ── Scroll-to-block + highlight ─────────────────────────────────────────

    if (panel) {
        panel.addEventListener('click', function (e) {
            // Ignore copy button clicks — those are handled above
            if (e.target.closest('.phoxtail-design-bar-copy-btn')) return;

            var row = e.target.closest('.phoxtail-design-bar-block-row');
            if (!row || !row.dataset.phoxtailDesignBarUuid) return;

            var target = document.getElementById('phoxtail-block-' + row.dataset.phoxtailDesignBarUuid);
            if (!target) return;

            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            highlightBlock(target);
        });
    }
})();
