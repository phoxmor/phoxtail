(function () {
    function payloadFromEl(el) {
        var t = el.dataset.mediaType;
        if (!t) return null;
        var p = {
            media_type: t,
            media_id: parseInt(el.dataset.mediaId, 10),
            title: el.dataset.mediaTitle || '',
            file_url: el.dataset.mediaFileUrl || ''
        };
        if (t === 'image') {
            if (el.dataset.mediaWidth)  p.width  = parseInt(el.dataset.mediaWidth, 10);
            if (el.dataset.mediaHeight) p.height = parseInt(el.dataset.mediaHeight, 10);
        } else if (t === 'video') {
            if (el.dataset.mediaThumbnailUrl) p.thumbnail_url = el.dataset.mediaThumbnailUrl;
            if (el.dataset.mediaDuration)     p.duration      = parseFloat(el.dataset.mediaDuration);
            if (el.dataset.mediaWidth)        p.width         = parseInt(el.dataset.mediaWidth, 10);
            if (el.dataset.mediaHeight)       p.height        = parseInt(el.dataset.mediaHeight, 10);
        } else if (t === 'audio') {
            if (el.dataset.mediaDuration)      p.duration       = parseFloat(el.dataset.mediaDuration);
            if (el.dataset.mediaFileExtension) p.file_extension = el.dataset.mediaFileExtension;
        } else if (t === 'document') {
            if (el.dataset.mediaFileExtension) p.file_extension = el.dataset.mediaFileExtension;
            if (el.dataset.mediaFileSize)      p.file_size      = parseInt(el.dataset.mediaFileSize, 10);
        }
        return p;
    }

    /* Delegated off document: HTMX's "Load more" swaps `hx-target="this"`
       (the button itself), not the results container, so per-element
       listeners bound after a container-level swap never reach appended
       items. Delegation sidesteps that regardless of what HTMX swaps. */
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.phoxtail-media-picker-add-btn');
        if (!btn || btn.classList.contains('phoxtail-media-picker-menu-add-btn')) return;
        e.stopPropagation();
        var item = btn.closest('[data-media-type]');
        var payload = item ? payloadFromEl(item) : null;
        if (payload && window.phoxtailChat) {
            window.phoxtailChat.addContext(payload);
            btn.classList.add('phoxtail-media-picker-add-btn--added');
            setTimeout(function () { btn.classList.remove('phoxtail-media-picker-add-btn--added'); }, 800);
        }
    });

    document.addEventListener('dragstart', function (e) {
        var el = e.target.closest('[data-media-type][draggable="true"]');
        if (!el) return;
        var payload = payloadFromEl(el);
        if (!payload || !window.phoxtailChat) { e.preventDefault(); return; }
        window.phoxtailChat.beginDrag(payload, e);
    });
    document.addEventListener('dragend', function (e) {
        var el = e.target.closest('[data-media-type][draggable="true"]');
        if (!el) return;
        if (window.phoxtailChat) window.phoxtailChat.endDrag();
    });

    /* ── Menu tab (page tree) ──
       Pages use the same context-chip payload shape as the "add current
       page" action in phoxtail_bar.js — no media_type field, so the chip
       system's existing page:<id> dedupe key keeps working unchanged. */
    function pagePayloadFromEl(el) {
        if (!el || !el.dataset.pageId) return null;
        return {
            page_id: parseInt(el.dataset.pageId, 10),
            page_title: el.dataset.pageTitle || '',
            page_type: el.dataset.pageType || '',
            slug: el.dataset.pageSlug || '',
            locale: el.dataset.pageLocale || '',
            live: el.dataset.pageLive === 'true'
        };
    }

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.phoxtail-media-picker-menu-add-btn');
        if (!btn) return;
        e.stopPropagation();
        var payload = pagePayloadFromEl(btn.closest('[data-page-id]'));
        if (payload && window.phoxtailChat) {
            window.phoxtailChat.addContext(payload);
            btn.classList.add('phoxtail-media-picker-add-btn--added');
            setTimeout(function () { btn.classList.remove('phoxtail-media-picker-add-btn--added'); }, 800);
        }
    });

    /* Expand/collapse. The children fetch is driven from here rather than an
       hx-trigger="click once" on the button: "once" is spent by the first
       click even if the request fails, stranding the node open, empty and
       un-retryable. Fetching only while the branch is unloaded makes every
       failure recoverable by simply expanding again. */
    document.addEventListener('click', function (e) {
        var toggle = e.target.closest('.phoxtail-media-picker-menu-toggle');
        if (!toggle || toggle.classList.contains('phoxtail-media-picker-menu-toggle--spacer')) return;
        var node = toggle.closest('.phoxtail-media-picker-menu-node');
        var children = node && node.querySelector(':scope > .phoxtail-media-picker-menu-children');
        if (!children) return;
        var expanded = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        children.hidden = expanded;
        if (expanded || children.dataset.loaded || !toggle.dataset.childrenUrl) return;
        var row = toggle.closest('[data-page-id]');
        if (!row || typeof htmx === 'undefined') return;
        htmx.ajax('GET', toggle.dataset.childrenUrl, {
            target: children,
            swap: 'innerHTML',
            values: { parent_id: row.dataset.pageId }
        }).then(function () {
            if (children.childElementCount > 0) children.dataset.loaded = '1';
        });
    });

    /* Buttons live inside draggable="true" rows, and a few pixels of pointer
       drift between press and release starts an HTML5 drag on the row instead
       of delivering the click (draggable="false" on the buttons alone can't
       stop the ancestor's drag). Suspend the row's draggability for the
       duration of any press that begins on a control. */
    document.addEventListener('pointerdown', function (e) {
        var ctl = e.target.closest(
            '.phoxtail-media-picker-menu-toggle:not(.phoxtail-media-picker-menu-toggle--spacer), ' +
            '.phoxtail-media-picker-add-btn'
        );
        if (!ctl) return;
        var row = ctl.closest('[draggable="true"]');
        if (!row) return;
        row.setAttribute('draggable', 'false');
        function restore() {
            row.setAttribute('draggable', 'true');
            document.removeEventListener('pointerup', restore);
            document.removeEventListener('pointercancel', restore);
        }
        document.addEventListener('pointerup', restore);
        document.addEventListener('pointercancel', restore);
    });

    document.addEventListener('dragstart', function (e) {
        var el = e.target.closest('[data-page-id][draggable="true"]');
        if (!el) return;
        var payload = pagePayloadFromEl(el);
        if (!payload || !window.phoxtailChat) { e.preventDefault(); return; }
        window.phoxtailChat.beginDrag(payload, e);
    });
    document.addEventListener('dragend', function (e) {
        var el = e.target.closest('[data-page-id][draggable="true"]');
        if (!el) return;
        if (window.phoxtailChat) window.phoxtailChat.endDrag();
    });

    window.phoxtailMediaPicker = { payloadFromEl: payloadFromEl, pagePayloadFromEl: pagePayloadFromEl };
})();
