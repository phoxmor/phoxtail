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
        if (!btn) return;
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

    window.phoxtailMediaPicker = { payloadFromEl: payloadFromEl };
})();
