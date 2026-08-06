(function () {
    if (!document.getElementById('phoxtail-bar-manifest')) return;

    // Re-queried on every read: page-swapping UIs (e.g. the slides
    // player) replace the manifest node out-of-band, so holding the
    // element would go stale along with its contents.
    function _readManifest() {
        var el = document.getElementById('phoxtail-bar-manifest');
        try {
            return el ? JSON.parse(el.textContent) : { id: null };
        } catch (err) {
            return { id: null };
        }
    }

    var manifest = _readManifest();
    var bar = document.getElementById('phoxtail-bar');

    // Mark html + body so CSS can reserve space; ResizeObserver keeps the
    // custom property in sync with the dock's live height.
    document.documentElement.classList.add('phoxtail-bar-active');
    document.body.classList.add('phoxtail-bar-active');
    var _dock = bar && bar.querySelector('.phoxtail-bar-dock');
    if (_dock) {
        new ResizeObserver(function (entries) {
            document.documentElement.style.setProperty(
                '--phoxtail-bar-offset', entries[0].contentRect.height + 'px'
            );
        }).observe(_dock);
    }

    var blocksBtn = document.getElementById('phoxtail-bar-blocks-btn');
    var blocksPanel = document.getElementById('phoxtail-bar-blocks-panel');
    var blocksPanelClose = document.getElementById('phoxtail-bar-panel-close');
    var modelPickerBtn = document.getElementById('phoxtail-model-picker-btn');
    var modelPickerPanel = document.getElementById('phoxtail-model-picker-panel');
    var modelPickerClose = document.getElementById('phoxtail-model-picker-close');
    var modelPickerLabel = document.getElementById('phoxtail-model-picker-label');
    var modelSearchInput = document.getElementById('phoxtail-model-search');
    var modelSearchClear = document.getElementById('phoxtail-model-search-clear');
    var modelSearchIcon  = document.getElementById('phoxtail-model-search-icon');
    var chatbotBtn = document.getElementById('phoxtail-bar-chatbot-btn');
    var chatbotDrawer = document.getElementById('phoxtail-chatbot-drawer');
    var chatbotHistoryBtn = document.getElementById('phoxtail-chatbot-history-btn');
    var chatbotForm = document.getElementById('phoxtail-chatbot-form');
    var chatbotInput = document.getElementById('phoxtail-chatbot-input');
    var chatbotSendBtn = chatbotForm && chatbotForm.querySelector('.phoxtail-chatbot-send-btn');
    var chatbotStopBtn = chatbotForm && chatbotForm.querySelector('.phoxtail-chatbot-stop-btn');
    var chatbotMessages = document.getElementById('phoxtail-chatbot-messages');
    var _emptyStateHTML = chatbotMessages ? chatbotMessages.innerHTML : '';
    var menuBtn = document.getElementById('phoxtail-bar-actions-btn');
    var menuPanel = document.getElementById('phoxtail-bar-actions-panel');
    var menuClose = document.getElementById('phoxtail-bar-actions-close');
    var publishBtn = document.getElementById('phoxtail-bar-publish-btn');
    var unpublishBtn = document.getElementById('phoxtail-bar-unpublish-btn');
    var editBtn = document.getElementById('phoxtail-bar-edit-btn');
    var adminBtn = document.getElementById('phoxtail-bar-admin-btn');

    // ── Generic panel toggle factory ────────────────────────────────────────

    function makeToggle(panel, button) {
        if (!panel || !button) return null;
        return {
            isOpen: function () { return panel.classList.contains('phoxtail-bar-panel--open'); },
            open:   function () {
                panel.classList.add('phoxtail-bar-panel--open');
                button.classList.add('phoxtail-bar-btn--active');
                button.setAttribute('aria-expanded', 'true');
            },
            close:  function () {
                panel.classList.remove('phoxtail-bar-panel--open');
                button.classList.remove('phoxtail-bar-btn--active');
                button.setAttribute('aria-expanded', 'false');
                if (panel === blocksPanel) {
                    // _activeBlockIdx preserved so next open resumes from the last-visited row
                    getBlockRows().forEach(function (r) { r.classList.remove('phoxtail-bar-block-row--active'); });
                }
                if (panel === modelPickerPanel) {
                    _activeModelIdx = -1;
                    getModelRows().forEach(function (r) { r.classList.remove('phoxtail-bar-block-row--active'); });
                    _resetModelSearch();
                }
                if (panel === menuPanel) {
                    _activeMenuIdx = -1;
                    getMenuItems().forEach(function (r) { r.classList.remove('phoxtail-bar-actions-item--active'); });
                }
            }
        };
    }

    var blocks = makeToggle(blocksPanel, blocksBtn);
    var menu = makeToggle(menuPanel, menuBtn);
    var modelPicker = makeToggle(modelPickerPanel, modelPickerBtn);

    // Chatbot uses a drawer class, not a panel class — handled manually but same shape
    function _setPageBlocksDraggable(enabled) {
        document.querySelectorAll('.phoxtail-page-body .phoxtail-block').forEach(function (el) {
            if (enabled) { el.setAttribute('draggable', 'true'); }
            else { el.removeAttribute('draggable'); }
        });
        if (enabled) { document.body.classList.add('phoxtail-chat-open'); }
        else { document.body.classList.remove('phoxtail-chat-open'); }
    }

    var chat = {
        isOpen: function () { return chatbotDrawer && chatbotDrawer.classList.contains('phoxtail-chatbot-drawer--open'); },
        open:   function () {
            if (!chatbotDrawer || !chatbotBtn) return;
            chatbotDrawer.classList.add('phoxtail-chatbot-drawer--open');
            chatbotBtn.classList.add('phoxtail-bar-btn--active');
            chatbotBtn.setAttribute('aria-expanded', 'true');
            _setPageBlocksDraggable(true);
            _loadModelPickerContent();
        },
        close:  function () {
            if (!chatbotDrawer || !chatbotBtn) return;
            chatbotDrawer.classList.remove('phoxtail-chatbot-drawer--open');
            chatbotBtn.classList.remove('phoxtail-bar-btn--active');
            chatbotBtn.setAttribute('aria-expanded', 'false');
            _setPageBlocksDraggable(false);
        }
    };

    // Close all panels except the given one
    function closeOthers(keep) {
        [blocks, menu, modelPicker].forEach(function (t) { if (t && t !== keep && t.isOpen()) t.close(); });
    }

    // ── Wire up toggles ─────────────────────────────────────────────────────

    if (blocks) {
        blocksBtn.addEventListener('click', function () {
            if (blocks.isOpen()) { blocks.close(); } else {
                if (modelPicker && modelPicker.isOpen()) modelPicker.close();
                blocks.open();
                var brows = getBlockRows();
                if (_activeBlockIdx !== -1 && _activeBlockIdx < brows.length) activateBlockAtIndex(_activeBlockIdx);
            }
        });
        blocksPanelClose.addEventListener('click', function () { blocks.close(); });
    }

    // ── Model picker state ───────────────────────────────────────────────────

    var _modelPickerUrl = chatbotDrawer ? chatbotDrawer.dataset.modelPickerUrl : null;
    var _modelPickerLoaded = false;
    var _LS_ARTIFACT_ID = 'phoxtail.chatbot.artifact_id';
    var _LS_ARTIFACT_NAME = 'phoxtail.chatbot.artifact_name';
    var _selectedArtifactId = null;
    var _selectedArtifactName = null;
    var _siteDefaultArtifactId = null;
    var _siteDefaultArtifactName = null;
    var _activeModelIdx = -1;

    function _abbreviateModelName(name) {
        // "Gemini 2.5 Flash" → "2.5 Flash", "Claude Sonnet 4.6" → "Sonnet 4.6"
        var parts = name.split(' ');
        return parts.length > 1 ? parts.slice(1).join(' ') : name;
    }

    function _setSelectedArtifact(id, name, persist) {
        _selectedArtifactId = id;
        _selectedArtifactName = name;
        if (persist !== false) {
            if (id !== null) {
                try { localStorage.setItem(_LS_ARTIFACT_ID, String(id)); } catch (_) {}
                try { localStorage.setItem(_LS_ARTIFACT_NAME, name); } catch (_) {}
            } else {
                try { localStorage.removeItem(_LS_ARTIFACT_ID); } catch (_) {}
                try { localStorage.removeItem(_LS_ARTIFACT_NAME); } catch (_) {}
            }
        }
        _syncModelPickerUI();
    }

    function _restorePersistedArtifact() {
        try {
            var storedId = localStorage.getItem(_LS_ARTIFACT_ID);
            var storedName = localStorage.getItem(_LS_ARTIFACT_NAME);
            if (storedId) {
                _setSelectedArtifact(parseInt(storedId, 10), storedName || '', false);
                return;
            }
        } catch (_) {}
        _setSelectedArtifact(null, null, false);
    }

    function _syncModelPickerUI() {
        if (!modelPickerBtn) return;
        var effectiveId = _selectedArtifactId !== null ? _selectedArtifactId : _siteDefaultArtifactId;
        var effectiveName = _selectedArtifactId !== null ? _selectedArtifactName : _siteDefaultArtifactName;
        var isExplicit = _selectedArtifactId !== null;

        if (effectiveId !== null) {
            modelPickerBtn.classList.add('phoxtail-chatbot-model-btn--labeled');
            if (modelPickerLabel) {
                modelPickerLabel.textContent = _abbreviateModelName(effectiveName || '');
            }
        } else {
            modelPickerBtn.classList.remove('phoxtail-chatbot-model-btn--labeled');
            if (modelPickerLabel) modelPickerLabel.textContent = '';
        }
        // Sync selected row highlight inside panel
        if (modelPickerPanel) {
            modelPickerPanel.querySelectorAll('.phoxtail-model-row').forEach(function (row) {
                var rid = parseInt(row.dataset.artifactId, 10);
                row.classList.toggle('phoxtail-model-row--selected', rid === _selectedArtifactId);
                row.classList.toggle('phoxtail-model-row--site-default-active',
                    _selectedArtifactId === null && rid === _siteDefaultArtifactId);
            });
        }
    }

    // Restore from localStorage on load
    (function () {
        try {
            var storedId = localStorage.getItem(_LS_ARTIFACT_ID);
            var storedName = localStorage.getItem(_LS_ARTIFACT_NAME);
            if (storedId) {
                _selectedArtifactId = parseInt(storedId, 10);
                _selectedArtifactName = storedName || '';
                _syncModelPickerUI();
            }
        } catch (_) {}
    })();

    function getModelRows() {
        if (!modelPickerPanel) return [];
        return Array.prototype.slice.call(modelPickerPanel.querySelectorAll('.phoxtail-model-row'));
    }

    function activateModelAtIndex(idx) {
        var rows = getModelRows();
        if (!rows.length) return;
        var n = rows.length;
        idx = ((idx % n) + n) % n;
        _activeModelIdx = idx;
        rows.forEach(function (r) { r.classList.remove('phoxtail-bar-block-row--active'); });
        rows[idx].classList.add('phoxtail-bar-block-row--active');
        rows[idx].scrollIntoView({ block: 'nearest' });
    }

    // Returns the full-list index of the next/prev visible model row (dir: 1=down, -1=up), wrapping around.
    // Returns -1 if no visible rows exist.
    function _stepModelIdx(dir) {
        var rows = getModelRows();
        var n = rows.length;
        if (!n) return -1;
        if (_activeModelIdx === -1) {
            var start = dir === 1 ? 0 : n - 1;
            for (var i = 0; i < n; i++) {
                var ci = ((start + dir * i) % n + n) % n;
                if (rows[ci].style.display !== 'none') return ci;
            }
            return -1;
        }
        for (var i = 1; i <= n; i++) {
            var ci = ((_activeModelIdx + dir * i) % n + n) % n;
            if (rows[ci].style.display !== 'none') return ci;
        }
        return -1;
    }

    function _initModelActiveRow() {
        var rows = getModelRows();
        if (!rows.length) { _activeModelIdx = -1; return; }
        var targetId = _selectedArtifactId !== null ? _selectedArtifactId : _siteDefaultArtifactId;
        if (targetId === null) { _activeModelIdx = -1; return; }
        for (var i = 0; i < rows.length; i++) {
            if (parseInt(rows[i].dataset.artifactId, 10) === targetId && rows[i].style.display !== 'none') {
                activateModelAtIndex(i);
                return;
            }
        }
        _activeModelIdx = -1;
    }

    function _resetModelSearch() {
        if (!modelSearchInput) return;
        var hadQuery = modelSearchInput.value.trim().length > 0;
        modelSearchInput.value = '';
        if (modelSearchIcon)  modelSearchIcon.classList.remove('phoxtail-bar-hidden');
        if (modelSearchClear) modelSearchClear.classList.add('phoxtail-bar-hidden');
        if (hadQuery && _modelPickerUrl && typeof htmx !== 'undefined') {
            htmx.ajax('GET', _modelPickerUrl, { target: '#phoxtail-model-picker-body', swap: 'innerHTML' });
        } else {
            _initModelActiveRow();
        }
    }

    if (modelSearchInput) {
        modelSearchInput.addEventListener('input', function () {
            var hasVal = modelSearchInput.value.length > 0;
            if (modelSearchIcon)  modelSearchIcon.classList.toggle('phoxtail-bar-hidden', hasVal);
            if (modelSearchClear) modelSearchClear.classList.toggle('phoxtail-bar-hidden', !hasVal);
        });
        modelSearchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') e.preventDefault();
        });
    }
    if (modelSearchClear) {
        modelSearchClear.addEventListener('click', function () {
            _resetModelSearch();
            if (modelSearchInput) modelSearchInput.focus();
        });
    }

    function _loadModelPickerContent() {
        if (_modelPickerLoaded || !_modelPickerUrl || typeof htmx === 'undefined') return;
        _modelPickerLoaded = true;
        var bodyEl = document.getElementById('phoxtail-model-picker-body');
        if (!bodyEl) return;
        bodyEl.addEventListener('htmx:afterSettle', function () {
            _activeModelIdx = -1;
            // Read site default from the server-marked row
            var defaultRow = modelPickerPanel.querySelector('.phoxtail-model-row[data-is-site-default="true"]');
            if (defaultRow) {
                _siteDefaultArtifactId = parseInt(defaultRow.dataset.artifactId, 10);
                _siteDefaultArtifactName = defaultRow.dataset.artifactName || '';
            }
            // Clear stale explicit selection if the artifact was deactivated/removed.
            // Only do this when not searching — a query may simply filter out the selected row.
            var hasActiveSearch = modelSearchInput && modelSearchInput.value.trim().length > 0;
            if (!hasActiveSearch && _selectedArtifactId !== null) {
                var found = getModelRows().some(function (r) {
                    return parseInt(r.dataset.artifactId, 10) === _selectedArtifactId;
                });
                if (!found) _setSelectedArtifact(null, null);
            }
            _syncModelPickerUI();
            if (modelPicker.isOpen()) _initModelActiveRow();
        }, { once: false });
        htmx.ajax('GET', _modelPickerUrl, { target: '#phoxtail-model-picker-body', swap: 'innerHTML' });
    }

    if (modelPicker) {
        modelPickerBtn.addEventListener('click', function () {
            if (modelPicker.isOpen()) { modelPicker.close(); } else {
                if (blocks && blocks.isOpen()) blocks.close();
                _loadModelPickerContent();
                modelPicker.open();
                if (getModelRows().length) _initModelActiveRow();
            }
        });
        modelPickerClose.addEventListener('click', function () { modelPicker.close(); });
        modelPickerPanel.addEventListener('click', function (e) {
            var row = e.target.closest('.phoxtail-model-row');
            if (!row) return;
            var id = parseInt(row.dataset.artifactId, 10);
            var name = row.dataset.artifactName || '';
            // Clicking the already-selected model clears back to system default
            if (id === _selectedArtifactId) {
                _setSelectedArtifact(null, null);
            } else {
                _setSelectedArtifact(id, name);
            }
            modelPicker.close();
        });
    }

    if (menu) {
        menuBtn.addEventListener('click', function () {
            if (menu.isOpen()) { menu.close(); } else { closeOthers(menu); menu.open(); }
        });
        menuClose.addEventListener('click', function () { menu.close(); });
        // Close menu when a menu item link is activated (target=_blank stays open in new tab, UX still clean)
        menuPanel.addEventListener('click', function (e) {
            if (e.target.closest('.phoxtail-bar-actions-item')) menu.close();
        });
    }

    function _pageAction(action) {
        var pageId = manifest.id;
        fetch('/api/content/v1/pages/' + pageId + '/', {
            headers: { 'Accept': 'application/json' },
        }).then(function (res) {
            if (!res.ok) { return Promise.reject('GET failed: ' + res.status); }
            var etag = res.headers.get('ETag');
            return fetch('/api/content/v1/pages/' + pageId + '/' + action + '/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': _getCsrfToken(),
                    'If-Match': etag || '',
                },
            });
        }).then(function (res) {
            if (!res.ok) {
                return res.json().then(function (data) {
                    alert((data && data.detail) ? data.detail : action + ' failed (' + res.status + ').');
                }).catch(function () {
                    alert(action + ' failed (' + res.status + ').');
                });
            }
            if (action === 'unpublish' && manifest.view_draft_url) {
                window.location.href = manifest.view_draft_url;
            } else {
                window.location.reload();
            }
        }).catch(function (err) {
            alert('Error: ' + err);
        });
    }

    if (publishBtn) {
        publishBtn.addEventListener('click', function () { _pageAction('publish'); });
    }
    if (unpublishBtn) {
        unpublishBtn.addEventListener('click', function () { _pageAction('unpublish'); });
    }

    if (chatbotBtn && chatbotDrawer) {
        chatbotBtn.addEventListener('click', function () {
            chat.isOpen() ? chat.close() : chat.open();
        });
        // Delegated: these buttons sit inside the messages container,
        // which is recreated from the empty-state snapshot on new/load chat.
        chatbotDrawer.addEventListener('click', function (e) {
            if (e.target.closest('#phoxtail-chatbot-drawer-close')) chat.close();
            else if (e.target.closest('#phoxtail-chatbot-expand-btn')) _toggleChatExpand();
        });
    }

    var barMediaBtn = document.getElementById('phoxtail-bar-media-btn');
    if (barMediaBtn) {
        barMediaBtn.addEventListener('click', function () {
            if (window.phoxtailChat) window.phoxtailChat.toggleMedia();
        });
    }

    if (chatbotStopBtn) {
        chatbotStopBtn.addEventListener('click', function () {
            if (_abortController) _abortController.abort();
        });
    }

    // ── Resizable drawer width ───────────────────────────────────────────────
    // The drag sets --phoxtail-chatbot-width (the user's DESIRED width); the
    // CSS clamp computes the effective width, including the max-width lane
    // reserved while a left-edge drawer (media picker / history) is open. The
    // JS clamp below only keeps the handle under the cursor during the drag.

    var _LS_WIDTH = 'phoxtail.chatbot.width';

    // Expand toggle: "expanded" simply means a desired width of 9999px — the
    // CSS clamp caps it at the CURRENT max, so an expanded drawer narrows by
    // itself while a left picker is open and re-stretches when it closes.
    var _chatExpanded = false;
    var _preExpandWidth = null;

    function _applyExpandState() {
        var btn = document.getElementById('phoxtail-chatbot-expand-btn');
        if (btn) btn.classList.toggle('phoxtail-bar-btn--active', _chatExpanded);
    }

    function _toggleChatExpand() {
        if (!chatbotDrawer) return;
        if (_chatExpanded) {
            _chatExpanded = false;
            if (_preExpandWidth > 0) {
                chatbotDrawer.style.setProperty('--phoxtail-chatbot-width', _preExpandWidth + 'px');
                try { localStorage.setItem(_LS_WIDTH, String(_preExpandWidth)); } catch (_) {}
            } else {
                chatbotDrawer.style.removeProperty('--phoxtail-chatbot-width');
                try { localStorage.removeItem(_LS_WIDTH); } catch (_) {}
            }
        } else {
            _chatExpanded = true;
            _preExpandWidth = Math.round(chatbotDrawer.getBoundingClientRect().width);
            chatbotDrawer.style.setProperty('--phoxtail-chatbot-width', '9999px');
            try { localStorage.setItem(_LS_WIDTH, 'max'); } catch (_) {}
        }
        _applyExpandState();
    }

    (function () {
        var handle = document.getElementById('phoxtail-chatbot-resize-handle');
        if (!handle || !chatbotDrawer) return;

        try {
            var stored = localStorage.getItem(_LS_WIDTH);
            if (stored === 'max') {
                _chatExpanded = true;
                chatbotDrawer.style.setProperty('--phoxtail-chatbot-width', '9999px');
                _applyExpandState();
            } else if (parseFloat(stored) > 0) {
                chatbotDrawer.style.setProperty('--phoxtail-chatbot-width', parseFloat(stored) + 'px');
            }
        } catch (_) {}

        function remPx() {
            return parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
        }

        function maxWidth() {
            var leftDrawerOpen =
                document.body.classList.contains('phoxtail-media-picker-open') ||
                document.body.classList.contains('phoxtail-chat-history-open');
            // clientWidth, not innerWidth: the fixed drawers are laid out
            // against the viewport excluding the page scrollbar. With no
            // picker open the drawer may stretch to the far screen edge.
            return document.documentElement.clientWidth - (leftDrawerOpen ? 27.5 : 0) * remPx();
        }

        var startX = 0;
        var startWidth = 0;

        function onMove(e) {
            var w = Math.min(Math.max(startWidth + (startX - e.clientX), 27.5 * remPx()), maxWidth());
            chatbotDrawer.style.setProperty('--phoxtail-chatbot-width', Math.round(w) + 'px');
        }

        handle.addEventListener('pointerdown', function (e) {
            e.preventDefault();
            // A manual drag leaves the expanded state; its width wins.
            _chatExpanded = false;
            _applyExpandState();
            startX = e.clientX;
            startWidth = chatbotDrawer.getBoundingClientRect().width;
            try { handle.setPointerCapture(e.pointerId); } catch (_) {}
            document.body.classList.add('phoxtail-chatbot-resizing');
            handle.addEventListener('pointermove', onMove);
            var onUp = function () {
                handle.removeEventListener('pointermove', onMove);
                handle.removeEventListener('pointerup', onUp);
                handle.removeEventListener('pointercancel', onUp);
                document.body.classList.remove('phoxtail-chatbot-resizing');
                try {
                    localStorage.setItem(_LS_WIDTH, String(Math.round(chatbotDrawer.getBoundingClientRect().width)));
                } catch (_) {}
            };
            handle.addEventListener('pointerup', onUp);
            handle.addEventListener('pointercancel', onUp);
        });

        handle.addEventListener('dblclick', function () {
            _chatExpanded = false;
            _preExpandWidth = null;
            _applyExpandState();
            chatbotDrawer.style.removeProperty('--phoxtail-chatbot-width');
            try { localStorage.removeItem(_LS_WIDTH); } catch (_) {}
        });
    })();

    // ── Click-outside: close any open panel ─────────────────────────────────

    document.addEventListener('click', function (e) {
        if (document.getElementById('base-modal') || document.getElementById('base-modal-level-1')) return;
        if (bar.contains(e.target)) return;
        if (chatbotDrawer && chatbotDrawer.contains(e.target)) return;
        if (menu && menu.isOpen()) menu.close();
        if (chat.isOpen()) chat.close();
    });

    // ── Keyboard shortcuts ───────────────────────────────────────────────────

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            if (_hlTarget) { dismissHighlight(); return; }
            if (document.getElementById('base-modal') || document.getElementById('base-modal-level-1')) return;
            if (chat.isOpen()) { chat.close(); return; }
            if (menu && menu.isOpen()) { menu.close(); return; }
            if (blocks && blocks.isOpen()) { blocks.close(); return; }
            return;
        }
        if (e.altKey || e.ctrlKey || e.metaKey) return;

        // Enter to activate the focused actions menu item
        if (e.key === 'Enter' && menu && menu.isOpen() && _activeMenuIdx !== -1) {
            e.preventDefault();
            var mitems = getMenuItems();
            var mitem = mitems[_activeMenuIdx];
            if (mitem) mitem.click();
            return;
        }
        // Enter to add active block — check before textarea guard since block rows have focus
        if (e.key === 'Enter' && blocks && blocks.isOpen() && _activeBlockIdx !== -1) {
            e.preventDefault();
            var rows = getBlockRows();
            var row = rows[_activeBlockIdx];
            if (row) {
                var payload = _payloadFromRow(row);
                if (payload) _addContextBlock(payload);
            }
            return;
        }
        // Enter to select active model row
        if (e.key === 'Enter' && modelPicker && modelPicker.isOpen() && _activeModelIdx !== -1) {
            e.preventDefault();
            var mrows = getModelRows();
            var mrow = mrows[_activeModelIdx];
            if (mrow) {
                var mid = parseInt(mrow.dataset.artifactId, 10);
                var mname = mrow.dataset.artifactName || '';
                if (mid === _selectedArtifactId) {
                    _setSelectedArtifact(null, null);
                } else {
                    _setSelectedArtifact(mid, mname);
                }
                modelPicker.close();
            }
            return;
        }

        // Backspace/Delete on an active chip — remove it (state-based, mirrors Enter/_activeBlockIdx)
        if ((e.key === 'Backspace' || e.key === 'Delete') && _activeChipIdx !== -1) {
            var aTag = document.activeElement && document.activeElement.tagName;
            if (aTag !== 'INPUT' && aTag !== 'TEXTAREA') {
                e.preventDefault();
                _removeContextBlockAt(_activeChipIdx);
                return;
            }
        }

        var tag = document.activeElement && document.activeElement.tagName;
        var isEditable = document.activeElement && document.activeElement.isContentEditable;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || isEditable) return;
        if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && menu && menu.isOpen()) {
            e.preventDefault();
            if (!getMenuItems().length) return;
            var dir = e.key === 'ArrowDown' ? 1 : -1;
            activateMenuItemAtIndex(_activeMenuIdx === -1 ? (dir === 1 ? 0 : getMenuItems().length - 1) : _activeMenuIdx + dir);
            return;
        }
        if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && blocks && blocks.isOpen()) {
            e.preventDefault();
            if (!getBlockRows().length) return;
            var dir = e.key === 'ArrowDown' ? 1 : -1;
            activateBlockAtIndex(_activeBlockIdx === -1 ? (dir === 1 ? 0 : -1) : _activeBlockIdx + dir);
            return;
        }
        if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && modelPicker && modelPicker.isOpen()) {
            e.preventDefault();
            var dir = e.key === 'ArrowDown' ? 1 : -1;
            var next = _stepModelIdx(dir);
            if (next !== -1) activateModelAtIndex(next);
            return;
        }
        if ((e.key === 'b' || e.key === 'B') && blocks) {
            var chatWasOpen = chat.isOpen();
            var _openBlocks = function () {
                closeOthers(blocks); blocks.open();
                var brows = getBlockRows();
                if (_activeBlockIdx !== -1 && _activeBlockIdx < brows.length) activateBlockAtIndex(_activeBlockIdx);
            };
            if (!chatWasOpen) {
                chat.open();
                if (!blocks.isOpen()) _openBlocks();
            } else {
                blocks.isOpen() ? blocks.close() : _openBlocks();
            }
        }
        if ((e.key === 'c' || e.key === 'C') && chatbotBtn) {
            chat.isOpen() ? chat.close() : chat.open();
        }
        if ((e.key === 'f' || e.key === 'F') && chatbotInput && chat.isOpen()) {
            e.preventDefault();
            chatbotInput.focus();
        }
        // Only when the chat drawer is open — otherwise 'e' is the page-actions
        // edit shortcut below (guarded on the actions menu being open).
        if ((e.key === 'e' || e.key === 'E') && chat.isOpen() && !(menu && menu.isOpen())) {
            _toggleChatExpand();
        }
        if ((e.key === 'a' || e.key === 'A') && menu) {
            menu.isOpen() ? menu.close() : (closeOthers(menu), menu.open());
        }
        if ((e.key === 'd' || e.key === 'D') && menu && menu.isOpen() && adminBtn) {
            menu.close();
            window.open(adminBtn.href, adminBtn.target || '_self');
        }
        if ((e.key === 'i' || e.key === 'I') && modelPicker) {
            var iChatWasOpen = chat.isOpen();
            var _openModelPicker = function () {
                closeOthers(modelPicker); modelPicker.open();
                if (getModelRows().length) _initModelActiveRow();
            };
            if (!iChatWasOpen) {
                chat.open();
                if (!modelPicker.isOpen()) _openModelPicker();
            } else {
                modelPicker.isOpen() ? modelPicker.close() : _openModelPicker();
            }
        }
        if ((e.key === 'm' || e.key === 'M') && window.phoxtailChat) {
            window.phoxtailChat.toggleMedia();
        }
        if ((e.key === 'h' || e.key === 'H') && window.phoxtailChat) {
            window.phoxtailChat.toggleHistory();
        }
        if ((e.key === 'n' || e.key === 'N') && chatbotBtn) {
            if (!chat.isOpen()) chat.open();
            _newConversation();
        }
        if ((e.key === 'e' || e.key === 'E') && menu && menu.isOpen() && editBtn) {
            menu.close();
            window.open(editBtn.href, editBtn.target || '_self');
        }
        if ((e.key === 'p' || e.key === 'P') && menu && menu.isOpen() && publishBtn) {
            menu.close();
            _pageAction('publish');
        }
        if ((e.key === 'u' || e.key === 'U') && menu && menu.isOpen() && unpublishBtn) {
            menu.close();
            _pageAction('unpublish');
        }
    });

    // ── Context chips ────────────────────────────────────────────────────────

    var _contextBlocks = [];
    var _activeChipIdx = -1;
    var _chipsEl = document.getElementById('phoxtail-chatbot-chips');
    var _chipIconsEl = document.getElementById('phoxtail-chip-icons');

    function _chipIconEl(payload) {
        if (!_chipIconsEl) return null;
        var key = payload.media_type || (payload.block_uuid ? 'block' : 'page');
        var container = _chipIconsEl.querySelector('[data-chip-icon="' + key + '"]');
        if (!container) container = _chipIconsEl.querySelector('[data-chip-icon="block"]');
        var svg = container ? container.querySelector('svg') : null;
        return svg ? svg.cloneNode(true) : null;
    }

    function _chipLabel(payload) {
        if (payload.media_type) {
            return payload.title || String(payload.media_id);
        }
        if (payload.block_type) {
            return payload.variant_identifier
                ? payload.block_type + ' · ' + payload.variant_identifier
                : payload.block_type;
        }
        return payload.page_title || payload.page_type || 'page';
    }

    function _chipAriaLabel(payload) {
        if (payload.media_type) return payload.media_type + ' ' + _chipLabel(payload);
        return _chipLabel(payload);
    }

    function _chipKey(payload) {
        if (payload.media_type) return payload.media_type + ':' + payload.media_id;
        return payload.block_uuid ? 'block:' + payload.block_uuid : 'page:' + payload.page_id;
    }

    function _syncChipsUI() {
        if (!_chipsEl) return;
        _chipsEl.innerHTML = '';
        if (!_contextBlocks.length) {
            _chipsEl.style.display = 'none';
            _activeChipIdx = -1;
            _syncAddButtons();
            return;
        }
        // Clamp active index after a removal
        if (_activeChipIdx >= _contextBlocks.length) {
            _activeChipIdx = _contextBlocks.length - 1;
        }
        _chipsEl.style.display = '';
        _contextBlocks.forEach(function (payload, i) {
            var chip = document.createElement('span');
            chip.className = 'phoxtail-chatbot-chip';
            if (i === _activeChipIdx) chip.classList.add('phoxtail-chatbot-chip--active');
            chip.setAttribute('tabindex', '0');
            chip.setAttribute('data-chip-index', i);

            var icon = _chipIconEl(payload);
            if (icon) chip.appendChild(icon);

            var label = document.createElement('span');
            label.className = 'phoxtail-chatbot-chip-label';
            label.textContent = _chipLabel(payload);

            var dismiss = document.createElement('button');
            dismiss.type = 'button';
            dismiss.className = 'phoxtail-chatbot-chip-dismiss';
            dismiss.title = 'Remove';
            dismiss.setAttribute('aria-label', 'Remove ' + _chipAriaLabel(payload));
            dismiss.textContent = '×';
            dismiss.setAttribute('data-chip-index', i);

            chip.appendChild(label);
            chip.appendChild(dismiss);
            chip.addEventListener('click', function (e) {
                if (e.target.closest('.phoxtail-chatbot-chip-dismiss')) return;
                _activeChipIdx = i;
                _chipsEl.querySelectorAll('.phoxtail-chatbot-chip').forEach(function (c, ci) {
                    c.classList.toggle('phoxtail-chatbot-chip--active', ci === i);
                });
            });
            _chipsEl.appendChild(chip);
        });
        _syncAddButtons();
    }

    function _syncAddButtons() {
        if (!blocksPanel) return;
        var rows = blocksPanel.querySelectorAll('[data-phoxtail-bar-copy]');
        rows.forEach(function (row) {
            var payload = _payloadFromRow(row);
            if (!payload) return;
            var key = _chipKey(payload);
            var isAdded = false;
            for (var i = 0; i < _contextBlocks.length; i++) {
                if (_chipKey(_contextBlocks[i]) === key) { isAdded = true; break; }
            }
            var addBtn = row.querySelector('.phoxtail-bar-add-btn');
            if (!addBtn) return;
            if (isAdded) {
                addBtn.classList.add('phoxtail-bar-add-btn--active');
                addBtn.title = 'Remove from chat';
            } else {
                addBtn.classList.remove('phoxtail-bar-add-btn--active');
                addBtn.title = 'Add to chat';
            }
        });
    }

    function _addContextBlock(payload) {
        var key = _chipKey(payload);
        for (var i = 0; i < _contextBlocks.length; i++) {
            if (_chipKey(_contextBlocks[i]) === key) return; // dedupe
        }
        _contextBlocks.push(payload);
        _activeChipIdx = _contextBlocks.length - 1; // auto-activate the new chip
        _syncChipsUI();
    }

    function _removeContextBlockAt(idx) {
        _contextBlocks.splice(idx, 1);
        _syncChipsUI();
    }

    function _clearContextBlocks() {
        _contextBlocks = [];
        _syncChipsUI();
    }

    if (_chipsEl) {
        _chipsEl.addEventListener('click', function (e) {
            var btn = e.target.closest('.phoxtail-chatbot-chip-dismiss');
            if (!btn) return;
            e.stopPropagation();
            var idx = parseInt(btn.getAttribute('data-chip-index'), 10);
            if (!isNaN(idx)) _removeContextBlockAt(idx);
        });

    }

    // ── Context sentinel encoding / decoding ─────────────────────────────────

    var _CONTEXT_RE = /^<phoxtail-context>\n([\s\S]*?)\n<\/phoxtail-context>\n\n/;

    function _parseContextPrefix(text) {
        var m = _CONTEXT_RE.exec(text);
        if (!m) return { blocks: [], text: text };
        var parsed;
        try { parsed = JSON.parse(m[1]); } catch (_) { parsed = []; }
        return { blocks: Array.isArray(parsed) ? parsed : [], text: text.slice(m[0].length) };
    }

    function _buildMessageText(rawText) {
        if (!_contextBlocks.length) return rawText;
        return '<phoxtail-context>\n' + JSON.stringify(_contextBlocks) + '\n</phoxtail-context>\n\n' + rawText;
    }

    // ── Drag-to-attach ───────────────────────────────────────────────────────

    var _draggingPayload = null;
    var _dragGhost = null;

    function _payloadFromRow(row) {
        if (!row) return null;
        if (row.dataset.phoxtailBarCopy === 'page') {
            return {
                page_id: manifest.id,
                page_title: manifest.title,
                page_type: manifest.type,
                slug: manifest.slug,
                locale: manifest.locale,
                live: manifest.live
            };
        }
        if (row.dataset.phoxtailBarCopy === 'block') {
            var p = {
                page_id: manifest.id,
                block_uuid: row.dataset.phoxtailBarUuid,
                block_type: row.dataset.phoxtailBarType
            };
            if (row.dataset.phoxtailBarVariantId) {
                p.variant_id = parseInt(row.dataset.phoxtailBarVariantId, 10);
                p.variant_identifier = row.dataset.phoxtailBarVariantIdentifier;
            }
            return p;
        }
        return null;
    }

    if (blocksPanel) {
        blocksPanel.addEventListener('dragstart', function (e) {
            var row = e.target.closest('[data-phoxtail-bar-copy]');
            var payload = _payloadFromRow(row);
            if (!payload) { e.preventDefault(); return; }

            _draggingPayload = payload;
            e.dataTransfer.effectAllowed = 'copy';
            e.dataTransfer.setData('text/plain', JSON.stringify(payload));

            _dragGhost = document.createElement('div');
            _dragGhost.className = 'phoxtail-chatbot-drag-ghost';
            var _ghostIcon = _chipIconEl(payload);
            if (_ghostIcon) _dragGhost.appendChild(_ghostIcon);
            var _ghostLabel = document.createElement('span');
            _ghostLabel.textContent = _chipLabel(payload);
            _dragGhost.appendChild(_ghostLabel);
            document.body.appendChild(_dragGhost);
            e.dataTransfer.setDragImage(_dragGhost, 12, 12);

            document.body.setAttribute('data-phoxtail-dragging', '1');
        });

        blocksPanel.addEventListener('dragend', function () {
            _draggingPayload = null;
            document.body.removeAttribute('data-phoxtail-dragging');
            if (_dragGhost) {
                if (_dragGhost.parentNode) _dragGhost.parentNode.removeChild(_dragGhost);
                _dragGhost = null;
            }
        });
    }

    // Auto-open chatbot drawer when dragging over its toggle button
    if (chatbotBtn) {
        chatbotBtn.addEventListener('dragenter', function () {
            if (document.body.hasAttribute('data-phoxtail-dragging') && !chat.isOpen()) {
                chat.open();
            }
        });
    }

    // Drop target: document-level coordinate check so drags from a modal overlay still land
    document.addEventListener('dragover', function (e) {
        if (!document.body.hasAttribute('data-phoxtail-dragging') || !chatbotDrawer) return;
        var r = chatbotDrawer.getBoundingClientRect();
        if (e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            if (chatbotForm) chatbotForm.classList.add('phoxtail-chatbot-compose--drop-target');
        } else {
            if (chatbotForm) chatbotForm.classList.remove('phoxtail-chatbot-compose--drop-target');
        }
    });

    document.addEventListener('drop', function (e) {
        if (!document.body.hasAttribute('data-phoxtail-dragging') || !chatbotDrawer) return;
        var r = chatbotDrawer.getBoundingClientRect();
        if (e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom) {
            e.preventDefault();
            if (chatbotForm) chatbotForm.classList.remove('phoxtail-chatbot-compose--drop-target');
            if (_draggingPayload) _addContextBlock(_draggingPayload);
        }
    });

    // ── Chatbot compose ──────────────────────────────────────────────────────

    if (chatbotInput) {
        chatbotInput.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 232) + 'px';
            _syncSendBtnState();
        });
        chatbotInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (chatbotForm) chatbotForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                return;
            }
            if (e.key === 'Backspace' && !e.shiftKey && this.value === '' && this.selectionStart === 0 && _contextBlocks.length) {
                e.preventDefault();
                _removeContextBlockAt(_contextBlocks.length - 1);
            }
        });
    }

    // ── Chatbot state ────────────────────────────────────────────────────────

    var _LS_KEY = 'phoxtail.chatbot.chat_uuid';
    var _conversationUuid = null;
    var _busy = false;
    var _abortController = null;

    function _getCsrfToken() {
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    function _renderChipsRow(blocks) {
        var row = document.createElement('div');
        row.className = 'phoxtail-chatbot-message-chips';
        blocks.forEach(function (payload) {
            var chip = document.createElement('span');
            chip.className = 'phoxtail-chatbot-chip phoxtail-chatbot-chip--inert';
            var icon = _chipIconEl(payload);
            if (icon) chip.appendChild(icon);
            var label = document.createElement('span');
            label.className = 'phoxtail-chatbot-chip-label';
            label.textContent = _chipLabel(payload);
            chip.appendChild(label);
            row.appendChild(chip);
        });
        return row;
    }

    function _appendMessage(cls, text) {
        var emptyState = document.getElementById('phoxtail-chatbot-empty');
        if (emptyState) emptyState.style.display = 'none';
        var el = document.createElement('div');
        el.className = 'phoxtail-chatbot-message ' + cls;

        if (cls === 'phoxtail-chatbot-message--user') {
            var parsed = _parseContextPrefix(text);
            if (parsed.blocks.length) {
                el.appendChild(_renderChipsRow(parsed.blocks));
            }
            var textSpan = document.createElement('span');
            textSpan.textContent = parsed.text;
            el.appendChild(textSpan);
        } else {
            el.textContent = text;
        }

        chatbotMessages.appendChild(el);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        return el;
    }

    function _blockShell(streamId) {
        var el = null;
        if (streamId) {
            try {
                el = chatbotMessages.querySelector('[data-stream-id="' + CSS.escape(streamId) + '"]');
            } catch (_) {}
        }
        if (!el) {
            var emptyState = document.getElementById('phoxtail-chatbot-empty');
            if (emptyState) emptyState.style.display = 'none';
            el = document.createElement('div');
            el.className = 'phoxtail-chatbot-message phoxtail-chatbot-message--assistant phoxtail-chatbot-message--block';
            if (streamId) el.setAttribute('data-stream-id', streamId);
            chatbotMessages.appendChild(el);
        }
        return el;
    }

    // Assistant prose arrives as server-rendered markdown HTML (message_html
    // events): throttled partial renders and the final render upsert the
    // same bubble via stream_id, exactly like block partials. The frontend
    // never parses markdown itself.
    function _upsertAssistantHtml(data) {
        var el = null;
        if (data.stream_id) {
            try {
                el = chatbotMessages.querySelector('[data-stream-id="' + CSS.escape(data.stream_id) + '"]');
            } catch (_) {}
        }
        if (!el) {
            el = _appendMessage('phoxtail-chatbot-message--assistant', '');
            if (data.stream_id) el.setAttribute('data-stream-id', data.stream_id);
        }
        el.innerHTML = data.html || '';
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        return el;
    }

    // Variants carry page-section spacing on their root (padding + margins
    // for page rhythm) — wasted space in the chat pane, where the messages
    // container already provides the gutter and gap. Strip it so the block
    // itself (which brings its own card padding) gets the full width.
    function _stripBlockRootSpacing(container) {
        Array.prototype.forEach.call(container.children, function (root) {
            if (root.tagName === 'STYLE' || root.tagName === 'SCRIPT') return;
            root.style.setProperty('padding', '0', 'important');
            root.style.setProperty('margin', '0', 'important');
        });
    }

    // Lane A: server-rendered block HTML from the site's own DB-authored
    // variant templates — it renders in the light DOM at natural height,
    // like on a page. The shell is a container-query context, so variants
    // adapt via @container rules.
    // Partial payloads stream in and replace the same shell; the final
    // payload re-runs the variant's scripts, inert when set via innerHTML.
    function _upsertBlockHtml(data) {
        var el = _blockShell(data.stream_id);
        el.innerHTML = data.html;
        if (!data.partial) {
            Array.prototype.forEach.call(el.querySelectorAll('script'), function (inert) {
                var script = document.createElement('script');
                if (inert.src) script.src = inert.src;
                script.textContent = inert.textContent;
                inert.parentNode.replaceChild(script, inert);
            });
        }
        _stripBlockRootSpacing(el);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        return el;
    }

    // Agent-designed one-off components render in the light DOM like any
    // block: natural height, native scrolling, page design tokens inherited.
    // The agent is instructed to self-scope its CSS under a unique root
    // class, the same convention DB-authored variants follow.
    function _appendCustomBlock(data) {
        var el = _blockShell(data.stream_id);
        el.innerHTML = '';
        if (data.css) {
            var style = document.createElement('style');
            style.textContent = data.css;
            el.appendChild(style);
        }
        var body = document.createElement('div');
        body.innerHTML = data.html || '';
        el.appendChild(body);
        if (data.javascript) {
            var script = document.createElement('script');
            script.textContent = data.javascript;
            el.appendChild(script);
        }
        _stripBlockRootSpacing(body);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        return el;
    }

    // ── Waiting-for-response indicator ───────────────────────────────────────
    // Three bouncing dots shown while nothing else signals progress: from
    // submit until the first token/block/tool event, and again between a
    // tool finishing and the next event. appendChild moves it to the bottom
    // when it already exists.

    var _thinkingEl = null;

    function _showThinking() {
        var emptyState = document.getElementById('phoxtail-chatbot-empty');
        if (emptyState) emptyState.style.display = 'none';
        if (!_thinkingEl || !_thinkingEl.isConnected) {
            _thinkingEl = document.createElement('div');
            _thinkingEl.className = 'phoxtail-chatbot-thinking';
            _thinkingEl.innerHTML = '<span></span><span></span><span></span>';
        }
        chatbotMessages.appendChild(_thinkingEl);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    }

    function _hideThinking() {
        if (_thinkingEl && _thinkingEl.parentNode) _thinkingEl.parentNode.removeChild(_thinkingEl);
    }

    // ── Tool-call activity group ─────────────────────────────────────────────
    // Consecutive tool calls share one compact row: a ticker label animates
    // each new tool name in (replacing the previous), a badge counts them,
    // and clicking expands the full list. When prose resumes (or the turn
    // ends) the group collapses to a "N tool calls" summary. The same
    // machinery renders the persisted trail on conversation reload.

    var _toolGroup = null;

    function _openToolGroup() {
        var emptyState = document.getElementById('phoxtail-chatbot-empty');
        if (emptyState) emptyState.style.display = 'none';
        var el = document.createElement('div');
        el.className = 'phoxtail-chatbot-toolgroup phoxtail-chatbot-toolgroup--running';
        var head = document.createElement('button');
        head.type = 'button';
        head.className = 'phoxtail-chatbot-toolgroup-head';
        head.innerHTML =
            '<span class="phoxtail-chatbot-toolgroup-spinner"></span>' +
            '<span class="phoxtail-chatbot-toolgroup-label"></span>' +
            '<span class="phoxtail-chatbot-toolgroup-count"></span>' +
            '<span class="phoxtail-chatbot-toolgroup-chevron"></span>';
        var list = document.createElement('div');
        list.className = 'phoxtail-chatbot-toolgroup-list';
        list.hidden = true;
        head.addEventListener('click', function () {
            list.hidden = !list.hidden;
            el.classList.toggle('phoxtail-chatbot-toolgroup--open', !list.hidden);
        });
        el.appendChild(head);
        el.appendChild(list);
        chatbotMessages.appendChild(el);
        return {
            el: el,
            label: head.querySelector('.phoxtail-chatbot-toolgroup-label'),
            count: head.querySelector('.phoxtail-chatbot-toolgroup-count'),
            list: list,
            names: [],
        };
    }

    function _toolGroupStart(name) {
        if (!_toolGroup || !_toolGroup.el.isConnected) _toolGroup = _openToolGroup();
        _toolGroup.names.push(name);
        _toolGroup.label.textContent = name;
        // Restart the slide-in animation for each new name.
        _toolGroup.label.classList.remove('phoxtail-chatbot-toolgroup-label--tick');
        void _toolGroup.label.offsetWidth;
        _toolGroup.label.classList.add('phoxtail-chatbot-toolgroup-label--tick');
        _toolGroup.count.textContent = _toolGroup.names.length > 1 ? String(_toolGroup.names.length) : '';
        var row = document.createElement('div');
        row.className = 'phoxtail-chatbot-toolgroup-item phoxtail-chatbot-toolgroup-item--running';
        row.textContent = name;
        _toolGroup.list.appendChild(row);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    }

    function _toolGroupEnd() {
        if (!_toolGroup) return;
        var running = _toolGroup.list.querySelector('.phoxtail-chatbot-toolgroup-item--running');
        if (running) running.classList.remove('phoxtail-chatbot-toolgroup-item--running');
    }

    function _finalizeToolGroup() {
        if (!_toolGroup) return;
        _toolGroupEnd();
        _toolGroup.el.classList.remove('phoxtail-chatbot-toolgroup--running');
        var n = _toolGroup.names.length;
        _toolGroup.label.classList.remove('phoxtail-chatbot-toolgroup-label--tick');
        _toolGroup.label.textContent = n === 1 ? _toolGroup.names[0] : n + ' tool calls';
        _toolGroup.count.textContent = '';
        _toolGroup = null;
    }

    function _syncSendBtnState() {
        if (!chatbotSendBtn || !chatbotInput) return;
        chatbotSendBtn.classList.toggle('phoxtail-chatbot-send-btn--active', chatbotInput.value.trim().length > 0);
    }

    function _setSending(active) {
        _busy = active;
        if (chatbotSendBtn) chatbotSendBtn.disabled = active;
        if (chatbotInput) chatbotInput.disabled = active;
        if (chatbotForm) chatbotForm.classList.toggle('phoxtail-chatbot-compose--busy', active);
        if (!active) _abortController = null;
    }

    function _newConversation() {
        if (_busy) return;
        _conversationUuid = null;
        _clearContextBlocks();
        try { localStorage.removeItem(_LS_KEY); } catch (_) {}
        _restorePersistedArtifact();
        _toolGroup = null;
        if (chatbotMessages) {
            chatbotMessages.innerHTML = _emptyStateHTML;
            _applyExpandState(); // expand button was recreated from the snapshot
        }
    }

    function _rehydrate(uuid) {
        fetch('/api/agent/v1/conversations/' + uuid + '/', {
            method: 'GET',
            headers: { 'X-CSRFToken': _getCsrfToken() },
        }).then(function (res) {
            if (!res.ok) {
                try { localStorage.removeItem(_LS_KEY); } catch (_) {}
                return;
            }
            return res.json();
        }).then(function (data) {
            if (!data || !data.messages || !data.messages.length) return;
            _conversationUuid = data.uuid;
            // Restore the model used in this conversation without touching localStorage
            if (data.last_artifact_used) {
                _setSelectedArtifact(data.last_artifact_used.id, data.last_artifact_used.name, false);
            } else {
                _restorePersistedArtifact();
            }
            var emptyState = document.getElementById('phoxtail-chatbot-empty');
            if (emptyState) emptyState.style.display = 'none';
            data.messages.forEach(function (msg) {
                // Consecutive tool items share one activity group, exactly
                // like they did while streaming.
                if (msg.role === 'tool') {
                    _toolGroupStart(msg.name);
                    _toolGroupEnd();
                    return;
                }
                _finalizeToolGroup();
                if (msg.role === 'user') {
                    _appendMessage('phoxtail-chatbot-message--user', msg.content);
                } else if (msg.role === 'assistant') {
                    if (msg.type === 'block_html') {
                        _upsertBlockHtml({ html: msg.html });
                    } else if (msg.type === 'block_custom') {
                        _appendCustomBlock(msg);
                    } else if (msg.type === 'message_html') {
                        _upsertAssistantHtml({ html: msg.html });
                    } else {
                        _appendMessage('phoxtail-chatbot-message--assistant', msg.content);
                    }
                }
            });
            _finalizeToolGroup();
        }).catch(function () {});
    }

    function _loadChat(uuid) {
        if (_busy) return;
        _conversationUuid = uuid;
        _contextBlocks = [];
        _syncChipsUI();
        try { localStorage.setItem(_LS_KEY, uuid); } catch (_) {}
        _toolGroup = null;
        if (chatbotMessages) {
            chatbotMessages.innerHTML = _emptyStateHTML;
            _applyExpandState(); // expand button was recreated from the snapshot
        }
        _rehydrate(uuid);
    }

    var _mediaPickerUrl = bar ? bar.dataset.mediaPickerUrl : null;
    var _mediaPickerModalUrl = bar ? bar.dataset.mediaPickerModalUrl : null;
    var _mediaPickerTab = null;
    var _mediaPickerObserver = null;
    var _mediaBtns = null;

    // Shared with the tab-click handler in media_picker.html — keep the key and
    // the valid-tabs list in sync with that file.
    var _MEDIA_TAB_LS_KEY = 'phoxtail.media_picker.tab';
    var _MEDIA_TABS = ['menu', 'images', 'videos', 'audio', 'documents'];

    function _getRememberedMediaTab() {
        var stored = null;
        try { stored = localStorage.getItem(_MEDIA_TAB_LS_KEY); } catch (_) {}
        return _MEDIA_TABS.indexOf(stored) !== -1 ? stored : 'menu';
    }

    function _getMediaBtns() {
        if (!_mediaBtns) _mediaBtns = Array.prototype.slice.call(document.querySelectorAll('.phoxtail-bar-media-btn'));
        return _mediaBtns;
    }

    function _setMediaBtnActive(active) {
        _getMediaBtns().forEach(function (btn) { btn.classList.toggle('phoxtail-bar-btn--active', active); });
    }

    function _onMediaPickerClosed() {
        _mediaPickerTab = null;
        _setMediaBtnActive(false);
        document.body.classList.remove('phoxtail-media-picker-open');
    }

    function _watchModalForClose() {
        if (_mediaPickerObserver) _mediaPickerObserver.disconnect();
        // #base-modal-level-1 is a direct child of #core-modal-level-1-placeholder-wrapper,
        // not document.body — observe the wrapper so childList mutations fire correctly.
        var wrapper = document.getElementById('core-modal-level-1-placeholder-wrapper');
        if (!wrapper) return;
        _mediaPickerObserver = new MutationObserver(function (mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var removed = mutations[i].removedNodes;
                for (var j = 0; j < removed.length; j++) {
                    if (removed[j].id === 'base-modal-level-1') {
                        // Only clean up if the removed modal actually held the media picker
                        // (not the case when _openMediaPicker replaces a history modal)
                        if (removed[j].querySelector && !removed[j].querySelector('.phoxtail-media-picker-drawer')) return;
                        _mediaPickerObserver.disconnect();
                        _mediaPickerObserver = null;
                        _onMediaPickerClosed();
                        return;
                    }
                }
            }
        });
        _mediaPickerObserver.observe(wrapper, { childList: true });
    }

    function _openMediaPicker(tab) {
        if (!_mediaPickerUrl || !_mediaPickerModalUrl) return;
        if (_chatHistoryOpen) _onHistoryClosed();
        _mediaPickerTab = tab;
        _setMediaBtnActive(true);
        document.body.classList.add('phoxtail-media-picker-open');
        _watchModalForClose();
        var pickerUrl = _mediaPickerUrl + '?tab=' + tab;
        if (manifest.id) pickerUrl += '&page_id=' + manifest.id;
        htmx.ajax('GET', _mediaPickerModalUrl, {
            target: '#core-modal-level-1-placeholder-wrapper',
            swap: 'innerHTML',
            values: { content_url: pickerUrl }
        });
    }

    var _chatHistoryUrl = chatbotDrawer ? chatbotDrawer.dataset.chatHistoryUrl : null;
    var _chatHistoryOpen = false;
    var _historyObserver = null;

    function _setHistoryBtnActive(active) {
        var btn = document.getElementById('phoxtail-chatbot-history-btn');
        if (!btn) return;
        btn.classList.toggle('phoxtail-bar-btn--active', active);
    }

    function _onHistoryClosed() {
        _chatHistoryOpen = false;
        _setHistoryBtnActive(false);
        document.body.classList.remove('phoxtail-chat-history-open');
    }

    function _watchHistoryForClose() {
        if (_historyObserver) _historyObserver.disconnect();
        var wrapper = document.getElementById('core-modal-level-1-placeholder-wrapper');
        if (!wrapper) return;
        _historyObserver = new MutationObserver(function (mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var removed = mutations[i].removedNodes;
                for (var j = 0; j < removed.length; j++) {
                    if (removed[j].id === 'base-modal-level-1') {
                        if (removed[j].querySelector && !removed[j].querySelector('.phoxtail-chat-history-drawer')) return;
                        _historyObserver.disconnect();
                        _historyObserver = null;
                        _onHistoryClosed();
                        return;
                    }
                }
            }
        });
        _historyObserver.observe(wrapper, { childList: true });
    }

    function _openHistory() {
        if (!_chatHistoryUrl || !_mediaPickerModalUrl) return;
        if (_mediaPickerTab !== null) _onMediaPickerClosed();
        _chatHistoryOpen = true;
        _setHistoryBtnActive(true);
        document.body.classList.add('phoxtail-chat-history-open');
        _watchHistoryForClose();
        htmx.ajax('GET', _mediaPickerModalUrl, {
            target: '#core-modal-level-1-placeholder-wrapper',
            swap: 'innerHTML',
            values: { content_url: _chatHistoryUrl }
        });
    }

    window.phoxtailChat = {
        close: function () { chat.close(); },
        load: function (uuid) {
            _loadChat(uuid);
            if (typeof window.closeModalLevel1 === 'function') window.closeModalLevel1();
            if (!chat.isOpen()) chat.open();
        },
        newChat: function () {
            _newConversation();
            if (!chat.isOpen()) chat.open();
        },
        addContext: function (payload) {
            _addContextBlock(payload);
            if (!chat.isOpen()) chat.open();
        },
        toggleHistory: function () {
            if (_chatHistoryOpen) {
                if (typeof window.closeModalLevel1 === 'function') window.closeModalLevel1();
            } else {
                _openHistory();
            }
        },
        toggleMedia: function () {
            if (_mediaPickerTab !== null) {
                if (typeof window.closeModalLevel1 === 'function') window.closeModalLevel1();
            } else {
                _openMediaPicker(_getRememberedMediaTab());
            }
        },
        beginDrag: function (payload, event) {
            _draggingPayload = payload;
            event.dataTransfer.effectAllowed = 'copy';
            event.dataTransfer.setData('text/plain', JSON.stringify(payload));
            _dragGhost = document.createElement('div');
            _dragGhost.className = 'phoxtail-chatbot-drag-ghost';
            var _ghostIcon = _chipIconEl(payload);
            if (_ghostIcon) _dragGhost.appendChild(_ghostIcon);
            var _ghostLabel = document.createElement('span');
            _ghostLabel.textContent = _chipLabel(payload);
            _dragGhost.appendChild(_ghostLabel);
            document.body.appendChild(_dragGhost);
            event.dataTransfer.setDragImage(_dragGhost, 12, 12);
            document.body.setAttribute('data-phoxtail-dragging', '1');
        },
        endDrag: function () {
            _draggingPayload = null;
            document.body.removeAttribute('data-phoxtail-dragging');
            if (_dragGhost) {
                if (_dragGhost.parentNode) _dragGhost.parentNode.removeChild(_dragGhost);
                _dragGhost = null;
            }
        }
    };

    // Keep messages bottom padding in sync with the compose form's live height so
    // the compose never overlaps the last message, even when the textarea is tall.
    if (chatbotForm && chatbotMessages) {
        function _syncComposePadding() {
            chatbotMessages.style.paddingBottom = (chatbotForm.offsetHeight + 20) + 'px';
        }
        new ResizeObserver(_syncComposePadding).observe(chatbotForm);
        _syncComposePadding();
    }

    // Rehydrate on load if we have a stored UUID
    (function () {
        try {
            var storedUuid = localStorage.getItem(_LS_KEY);
            if (storedUuid) _rehydrate(storedUuid);
        } catch (_) {}
    })();

    // ── Block refresh (HTMX-powered per-block updates) ────────────────────────

    // Queried fresh: the page body can be swapped wholesale (htmx page
    // navigation in the slides player), so a captured reference would
    // point at a detached element.
    function _pageBody() { return document.querySelector('.phoxtail-page-body'); }

    // ── Page-body block drag-to-chip ─────────────────────────────────────────
    // Document-delegated so it survives the page body being replaced.
    // Only blocks inside .phoxtail-page-body ever get draggable="true",
    // so the closest() check below already scopes this correctly.

    {
        document.addEventListener('dragstart', function (e) {
            // Let native link/image drags pass through untouched
            if (e.target.tagName === 'A' || e.target.tagName === 'IMG') return;
            var block = e.target.closest && e.target.closest('.phoxtail-block[draggable="true"]');
            if (!block) return;
            var payload = _payloadFromRow(block);
            if (!payload) { e.preventDefault(); return; }

            _draggingPayload = payload;
            e.dataTransfer.effectAllowed = 'copy';
            e.dataTransfer.setData('text/plain', JSON.stringify(payload));

            _dragGhost = document.createElement('div');
            _dragGhost.className = 'phoxtail-chatbot-drag-ghost';
            var _ghostIcon = _chipIconEl(payload);
            if (_ghostIcon) _dragGhost.appendChild(_ghostIcon);
            var _ghostLabel = document.createElement('span');
            _ghostLabel.textContent = _chipLabel(payload);
            _dragGhost.appendChild(_ghostLabel);
            document.body.appendChild(_dragGhost);
            e.dataTransfer.setDragImage(_dragGhost, 12, 12);

            document.body.setAttribute('data-phoxtail-dragging', '1');
        });

        document.addEventListener('dragend', function () {
            _draggingPayload = null;
            document.body.removeAttribute('data-phoxtail-dragging');
            if (_dragGhost) {
                if (_dragGhost.parentNode) _dragGhost.parentNode.removeChild(_dragGhost);
                _dragGhost = null;
            }
        });
    }

    // Re-apply draggable after HTMX swaps a block (outerHTML swap creates a fresh element)
    document.body.addEventListener('htmx:afterSettle', function () {
        if (chat.isOpen()) { _setPageBlocksDraggable(true); }
    });

    function _refreshBlock(uuid) {
        var el = document.getElementById('phoxtail-block-' + uuid);
        if (el && typeof htmx !== 'undefined') {
            htmx.trigger(el, 'phoxtail:block-refresh');
        }
    }

    function _refreshPageBody() {
        var pageBodyEl = _pageBody();
        if (pageBodyEl && typeof htmx !== 'undefined') {
            htmx.trigger(pageBodyEl, 'phoxtail:page-body-refresh');
        }
    }

    function _handleBlocksChanged(data) {
        var kind = data.kind;
        var uuids = data.uuids || [];
        if (kind === 'update') {
            uuids.forEach(function (uuid) { _refreshBlock(uuid); });
        } else {
            _refreshPageBody();
        }
    }

    if (chatbotForm) {
        chatbotForm.addEventListener('submit', function (e) {
            e.preventDefault();
            if (_busy) return;
            var rawText = chatbotInput ? chatbotInput.value.trim() : '';
            if (!rawText) return;

            var fullMessage = _buildMessageText(rawText);
            _appendMessage('phoxtail-chatbot-message--user', fullMessage);
            chatbotInput.value = '';
            chatbotInput.style.height = 'auto';
            _syncSendBtnState();
            _clearContextBlocks();
            _setSending(true);
            _showThinking();

            var body = { message: fullMessage };
            if (_conversationUuid) body.conversation_uuid = _conversationUuid;
            if (_selectedArtifactId !== null) body.artifact_id = _selectedArtifactId;

            _abortController = new AbortController();
            fetch('/api/agent/v1/chat/stream/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': _getCsrfToken(),
                },
                body: JSON.stringify(body),
                signal: _abortController.signal,
            }).then(function (res) {
                if (!res.ok) {
                    _hideThinking();
                    var status = res.status;
                    res.json().then(function (data) {
                        var msg = (data && data.detail) ? data.detail : 'Error ' + status + '. Please try again.';
                        _appendMessage('phoxtail-chatbot-message--assistant', msg);
                    }).catch(function () {
                        _appendMessage('phoxtail-chatbot-message--assistant', 'Error ' + status + '. Please try again.');
                    }).then(function () {
                        _setSending(false);
                    });
                    return;
                }
                var reader = res.body.getReader();
                var decoder = new TextDecoder();
                var buffer = '';

                function processChunk() {
                    reader.read().then(function (chunk) {
                        if (chunk.done) { _hideThinking(); _finalizeToolGroup(); _setSending(false); return; }
                        buffer += decoder.decode(chunk.value, { stream: true });
                        var parts = buffer.split('\n\n');
                        buffer = parts.pop();
                        parts.forEach(function (block) {
                            if (!block.trim()) return;
                            var eventMatch = block.match(/^event:\s*(.+)$/m);
                            var dataMatch = block.match(/^data:\s*(.+)$/m);
                            if (!eventMatch || !dataMatch) return;
                            var evt = eventMatch[1].trim();
                            var data;
                            try { data = JSON.parse(dataMatch[1]); } catch (_) { return; }

                            if (evt === 'tool_start') {
                                _hideThinking();
                                _toolGroupStart(data.name);
                            } else if (evt === 'tool_end') {
                                _toolGroupEnd();
                                // Nothing visibly streams between a tool
                                // finishing and the next event — show the
                                // dots again until it arrives.
                                if (_busy) _showThinking();
                            } else if (evt === 'blocks_changed') {
                                _handleBlocksChanged(data);
                            } else if (evt === 'block_html') {
                                _hideThinking();
                                _finalizeToolGroup();
                                _upsertBlockHtml(data);
                            } else if (evt === 'block_gone') {
                                // The block tool errored after a speculative
                                // preview streamed in — drop the stale shell.
                                if (data.stream_id) {
                                    try {
                                        var stale = chatbotMessages.querySelector('[data-stream-id="' + CSS.escape(data.stream_id) + '"]');
                                        if (stale) stale.parentNode.removeChild(stale);
                                    } catch (_) {}
                                }
                            } else if (evt === 'block_custom') {
                                _hideThinking();
                                _finalizeToolGroup();
                                _appendCustomBlock(data);
                            } else if (evt === 'message_html') {
                                _hideThinking();
                                _finalizeToolGroup();
                                _upsertAssistantHtml(data);
                            } else if (evt === 'done') {
                                _hideThinking();
                                _finalizeToolGroup();
                                _conversationUuid = data.conversation_uuid;
                                try { localStorage.setItem(_LS_KEY, _conversationUuid); } catch (_) {}
                                _setSending(false);
                            } else if (evt === 'error') {
                                _hideThinking();
                                _finalizeToolGroup();
                                var errMsg = (data && data.message) ? data.message : 'An error occurred. Please try again.';
                                _appendMessage('phoxtail-chatbot-message--assistant', errMsg);
                                _setSending(false);
                            }
                        });
                        processChunk();
                    }).catch(function (err) {
                        _hideThinking();
                        _finalizeToolGroup();
                        // AbortError is user-initiated — suppress the error message
                        if (err && err.name === 'AbortError') { _setSending(false); return; }
                        _setSending(false);
                    });
                }
                processChunk();
            }).catch(function (err) {
                _hideThinking();
                _finalizeToolGroup();
                if (err && err.name === 'AbortError') { _setSending(false); return; }
                _appendMessage('phoxtail-chatbot-message--assistant', 'Network error. Please try again.');
                _setSending(false);
            });
        });
    }

    // ── Copy to clipboard ────────────────────────────────────────────────────

    function copyText(text, btn) {
        navigator.clipboard.writeText(text).then(function () {
            btn.classList.add('phoxtail-bar-copy-btn--copied');
            setTimeout(function () { btn.classList.remove('phoxtail-bar-copy-btn--copied'); }, 1400);
        });
    }

    // Copy handler on design bar (menu panel copy buttons, if any)
    bar.addEventListener('click', function (e) {
        var copyBtn = e.target.closest('.phoxtail-bar-copy-btn');
        if (!copyBtn) return;
        e.stopPropagation();

        var row = copyBtn.closest('[data-phoxtail-bar-copy]');
        var payload = _payloadFromRow(row);
        if (payload) copyText(JSON.stringify(payload, null, 2), copyBtn);
    });

    // ── Block highlight — fixed-position body overlay, immune to block CSS ───

    var _hlEl = null;
    var _hlTarget = null;
    var _hlRaf = null;

    function getHighlightEl() {
        if (!_hlEl) {
            _hlEl = document.createElement('div');
            _hlEl.id = 'phoxtail-bar-highlight';
            _hlEl.innerHTML =
                '<div class="phoxtail-bar-highlight-corner phoxtail-bar-highlight-corner--tl"></div>' +
                '<div class="phoxtail-bar-highlight-corner phoxtail-bar-highlight-corner--tr"></div>' +
                '<div class="phoxtail-bar-highlight-corner phoxtail-bar-highlight-corner--bl"></div>' +
                '<div class="phoxtail-bar-highlight-corner phoxtail-bar-highlight-corner--br"></div>';
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
        getHighlightEl().classList.remove('phoxtail-bar-highlight--visible');
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
        hl.classList.add('phoxtail-bar-highlight--visible');
    }

    document.addEventListener('click', function (e) {
        if (!_hlTarget) return;
        if (bar.contains(e.target)) return;
        if (chatbotDrawer && chatbotDrawer.contains(e.target)) return;
        if (_hlTarget.contains(e.target)) return;
        dismissHighlight();
    });

    // ── Scroll-to-block + highlight ──────────────────────────────────────────

    var _activeBlockIdx = -1;
    var _activeMenuIdx = -1;

    function getMenuItems() {
        if (!menuPanel) return [];
        return Array.prototype.slice.call(menuPanel.querySelectorAll('.phoxtail-bar-actions-item'));
    }

    function activateMenuItemAtIndex(idx) {
        var items = getMenuItems();
        if (!items.length) return;
        var n = items.length;
        idx = ((idx % n) + n) % n;
        _activeMenuIdx = idx;
        items.forEach(function (r) { r.classList.remove('phoxtail-bar-actions-item--active'); });
        items[idx].classList.add('phoxtail-bar-actions-item--active');
        items[idx].scrollIntoView({ block: 'nearest' });
    }

    function getBlockRows() {
        if (!blocksPanel) return [];
        var page = Array.prototype.slice.call(blocksPanel.querySelectorAll('.phoxtail-bar-page-row[data-phoxtail-bar-copy]'));
        var blocks = Array.prototype.slice.call(blocksPanel.querySelectorAll('.phoxtail-bar-block-row[data-phoxtail-bar-uuid]'));
        return page.concat(blocks);
    }

    function activateBlockAtIndex(idx) {
        var rows = getBlockRows();
        if (!rows.length) return;
        var n = rows.length;
        idx = ((idx % n) + n) % n;
        _activeBlockIdx = idx;

        var row = rows[idx];
        rows.forEach(function (r) { r.classList.remove('phoxtail-bar-block-row--active'); });
        row.classList.add('phoxtail-bar-block-row--active');
        row.scrollIntoView({ block: 'nearest' });

        if (row.dataset.phoxtailBarUuid) {
            var target = document.getElementById('phoxtail-block-' + row.dataset.phoxtailBarUuid);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                highlightBlock(target);
            }
        }
    }

    if (blocksPanel) {
        blocksPanel.addEventListener('click', function (e) {
            // Copy button — handle here since blocks panel is inside the chatbot drawer, not bar
            var copyBtn = e.target.closest('.phoxtail-bar-copy-btn');
            if (copyBtn) {
                e.stopPropagation();
                var copyRow = copyBtn.closest('[data-phoxtail-bar-copy]');
                var copyPayload = _payloadFromRow(copyRow);
                if (copyPayload) copyText(JSON.stringify(copyPayload, null, 2), copyBtn);
                return;
            }

            // Add button — adds block as a chip
            var addBtn = e.target.closest('.phoxtail-bar-add-btn');
            if (addBtn) {
                e.stopPropagation();
                var addRow = addBtn.closest('[data-phoxtail-bar-copy]');
                var addPayload = _payloadFromRow(addRow);
                if (addPayload) {
                    var addKey = _chipKey(addPayload);
                    var existingIdx = -1;
                    for (var ci = 0; ci < _contextBlocks.length; ci++) {
                        if (_chipKey(_contextBlocks[ci]) === addKey) { existingIdx = ci; break; }
                    }
                    if (existingIdx !== -1) {
                        _removeContextBlockAt(existingIdx);
                    } else {
                        _addContextBlock(addPayload);
                    }
                }
                return;
            }

            // Row click — scroll to and highlight block
            var row = e.target.closest('.phoxtail-bar-block-row');
            if (!row || !row.dataset.phoxtailBarUuid) return;

            var idx = getBlockRows().indexOf(row);
            if (idx !== -1) activateBlockAtIndex(idx);
        });
    }

    // ── Public API ───────────────────────────────────────────────────────────
    // For page-swapping UIs (e.g. the slides player) that replace the
    // page under the bar without a full navigation. The caller swaps
    // #phoxtail-bar-manifest (and, if it uses them, the blocks panel
    // body/count) from the new page's response, then calls refresh() so
    // everything id-dependent — publish, media picker, block payloads,
    // the dock's page info — follows the new page.

    function _syncDockPageInfo() {
        var info = bar.querySelector('.phoxtail-bar-page-info');
        if (!info || !manifest.id) return;
        var titleEl = info.querySelector('.phoxtail-bar-page-title');
        if (titleEl) {
            var t = manifest.title || '';
            titleEl.textContent = t.length > 22 ? t.slice(0, 21) + '…' : t;
            titleEl.title = t;
        }
        var badgeEl = info.querySelector('.phoxtail-bar-badge');
        if (badgeEl) badgeEl.textContent = '#' + manifest.id;
        var typeEl = info.querySelector('.phoxtail-bar-type');
        if (typeEl) typeEl.textContent = (manifest.type || '').split('.').pop();
        var localeEl = info.querySelector('.phoxtail-bar-locale');
        if (localeEl) localeEl.textContent = manifest.locale || '';
        var dotEl = info.querySelector('.phoxtail-bar-live-dot');
        if (dotEl) {
            dotEl.classList.toggle('phoxtail-bar-live-dot--on', !!manifest.live);
            dotEl.classList.toggle('phoxtail-bar-live-dot--off', !manifest.live);
            dotEl.textContent = manifest.live ? 'live' : 'draft';
        }
        // Unpublish is server-rendered only when the page was live; when
        // it exists, keep its visibility in step with the current page.
        if (unpublishBtn) unpublishBtn.style.display = manifest.live ? '' : 'none';
        if (editBtn && adminBtn) {
            editBtn.href = adminBtn.href + 'pages/' + manifest.id + '/edit/';
        }
    }

    window.phoxtailBar = {
        refresh: function () {
            manifest = _readManifest();
            _syncDockPageInfo();
            // Blocks on a freshly swapped page body need draggable
            // re-applied while the chat is open.
            if (chat.isOpen()) _setPageBlocksDraggable(true);
        },
        pageAction: _pageAction,
        getManifest: function () { return manifest; },
    };
})();
