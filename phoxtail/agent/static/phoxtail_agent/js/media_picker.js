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

    function bindResults(container) {
        container.querySelectorAll('.phoxtail-media-picker-add-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var item = btn.closest('[data-media-type]');
                var payload = item ? payloadFromEl(item) : null;
                if (payload && window.phoxtailChat) {
                    window.phoxtailChat.addContext(payload);
                    btn.classList.add('phoxtail-media-picker-add-btn--added');
                    setTimeout(function () { btn.classList.remove('phoxtail-media-picker-add-btn--added'); }, 800);
                }
            });
        });

        container.querySelectorAll('[data-media-type][draggable="true"]').forEach(function (el) {
            el.addEventListener('dragstart', function (e) {
                var payload = payloadFromEl(el);
                if (!payload || !window.phoxtailChat) { e.preventDefault(); return; }
                window.phoxtailChat.beginDrag(payload, e);
            });
            el.addEventListener('dragend', function () {
                if (window.phoxtailChat) window.phoxtailChat.endDrag();
            });
        });
    }

    function tryInit(target) {
        var results = target && target.id === 'phoxtail-media-picker-results'
            ? target
            : target && target.querySelector('#phoxtail-media-picker-results');
        if (results) bindResults(results);
    }

    /* Bind after HTMX swaps the modal or the results partial */
    document.addEventListener('htmx:afterSwap', function (e) {
        tryInit(e.detail && e.detail.target);
    });
    document.addEventListener('htmx:afterSettle', function (e) {
        tryInit(e.detail && e.detail.target);
    });

    window.phoxtailMediaPicker = { payloadFromEl: payloadFromEl };
})();
