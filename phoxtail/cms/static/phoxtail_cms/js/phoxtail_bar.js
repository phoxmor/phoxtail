(function () {
    var manifestEl = document.getElementById('phoxtail-bar-manifest');
    if (!manifestEl) return;

    var manifest = JSON.parse(manifestEl.textContent);
    var bar = document.getElementById('phoxtail-bar');
    var blocksBtn = document.getElementById('phoxtail-bar-blocks-btn');
    var blocksPanel = document.getElementById('phoxtail-bar-blocks-panel');
    var blocksPanelClose = document.getElementById('phoxtail-bar-panel-close');
    var modelPickerBtn = document.getElementById('phoxtail-model-picker-btn');
    var modelPickerPanel = document.getElementById('phoxtail-model-picker-panel');
    var modelPickerClose = document.getElementById('phoxtail-model-picker-close');
    var modelPickerLabel = document.getElementById('phoxtail-model-picker-label');
    var chatbotBtn = document.getElementById('phoxtail-bar-chatbot-btn');
    var chatbotDrawer = document.getElementById('phoxtail-chatbot-drawer');
    var chatbotCloseBtn = document.getElementById('phoxtail-chatbot-drawer-close');
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
                    _activeBlockIdx = -1;
                    getBlockRows().forEach(function (r) { r.classList.remove('phoxtail-bar-block-row--active'); });
                }
                if (panel === modelPickerPanel) {
                    _activeModelIdx = -1;
                    getModelRows().forEach(function (r) { r.classList.remove('phoxtail-bar-block-row--active'); });
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
            chatbotDrawer.classList.add('phoxtail-chatbot-drawer--open');
            chatbotBtn.classList.add('phoxtail-bar-btn--active');
            chatbotBtn.setAttribute('aria-expanded', 'true');
            _setPageBlocksDraggable(true);
            _loadModelPickerContent();
        },
        close:  function () {
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
            modelPickerBtn.classList.toggle('phoxtail-bar-btn--active', isExplicit);
            if (modelPickerLabel) {
                modelPickerLabel.textContent = _abbreviateModelName(effectiveName || '');
            }
        } else {
            modelPickerBtn.classList.remove('phoxtail-bar-btn--active', 'phoxtail-chatbot-model-btn--labeled');
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
        idx = Math.max(0, Math.min(idx, rows.length - 1));
        _activeModelIdx = idx;
        rows.forEach(function (r) { r.classList.remove('phoxtail-bar-block-row--active'); });
        rows[idx].classList.add('phoxtail-bar-block-row--active');
        rows[idx].scrollIntoView({ block: 'nearest' });
    }

    function _loadModelPickerContent() {
        if (_modelPickerLoaded || !_modelPickerUrl || typeof htmx === 'undefined') return;
        _modelPickerLoaded = true;
        var bodyEl = document.getElementById('phoxtail-model-picker-body');
        if (!bodyEl) return;
        bodyEl.addEventListener('htmx:afterSettle', function () {
            // Read site default from the server-marked row
            var defaultRow = modelPickerPanel.querySelector('.phoxtail-model-row[data-is-site-default="true"]');
            if (defaultRow) {
                _siteDefaultArtifactId = parseInt(defaultRow.dataset.artifactId, 10);
                _siteDefaultArtifactName = defaultRow.dataset.artifactName || '';
            }
            // Clear stale explicit selection if the artifact was deactivated/removed
            if (_selectedArtifactId !== null) {
                var found = getModelRows().some(function (r) {
                    return parseInt(r.dataset.artifactId, 10) === _selectedArtifactId;
                });
                if (!found) _setSelectedArtifact(null, null);
            }
            _syncModelPickerUI();
        }, { once: false });
        htmx.ajax('GET', _modelPickerUrl, { target: '#phoxtail-model-picker-body', swap: 'innerHTML' });
    }

    if (modelPicker) {
        modelPickerBtn.addEventListener('click', function () {
            if (modelPicker.isOpen()) { modelPicker.close(); } else {
                if (blocks && blocks.isOpen()) blocks.close();
                _loadModelPickerContent();
                modelPicker.open();
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

    if (chatbotBtn && chatbotDrawer) {
        chatbotBtn.addEventListener('click', function () {
            chat.isOpen() ? chat.close() : chat.open();
        });
        chatbotCloseBtn.addEventListener('click', function () { chat.close(); });
    }

    if (chatbotStopBtn) {
        chatbotStopBtn.addEventListener('click', function () {
            if (_abortController) _abortController.abort();
        });
    }

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
        if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && blocks && blocks.isOpen()) {
            e.preventDefault();
            var rows = getBlockRows();
            if (!rows.length) return;
            if (_activeBlockIdx === -1) {
                activateBlockAtIndex(e.key === 'ArrowDown' ? 0 : rows.length - 1);
            } else {
                activateBlockAtIndex(_activeBlockIdx + (e.key === 'ArrowDown' ? 1 : -1));
            }
            return;
        }
        if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && modelPicker && modelPicker.isOpen()) {
            e.preventDefault();
            var mrows = getModelRows();
            if (!mrows.length) return;
            if (_activeModelIdx === -1) {
                activateModelAtIndex(e.key === 'ArrowDown' ? 0 : mrows.length - 1);
            } else {
                activateModelAtIndex(_activeModelIdx + (e.key === 'ArrowDown' ? 1 : -1));
            }
            return;
        }
        if ((e.key === 'b' || e.key === 'B') && blocks) {
            var chatWasOpen = chat.isOpen();
            if (!chatWasOpen) {
                chat.open();
                if (!blocks.isOpen()) { closeOthers(blocks); blocks.open(); }
            } else {
                blocks.isOpen() ? blocks.close() : (closeOthers(blocks), blocks.open());
            }
        }
        if ((e.key === 'c' || e.key === 'C') && chatbotBtn) {
            chat.isOpen() ? chat.close() : chat.open();
        }
        if ((e.key === 'f' || e.key === 'F') && chatbotInput && chat.isOpen()) {
            e.preventDefault();
            chatbotInput.focus();
        }
        if ((e.key === 'a' || e.key === 'A') && menu) {
            menu.isOpen() ? menu.close() : (closeOthers(menu), menu.open());
        }
        if ((e.key === 'i' || e.key === 'I') && modelPicker) {
            var iChatWasOpen = chat.isOpen();
            if (!iChatWasOpen) {
                chat.open();
                if (!modelPicker.isOpen()) { closeOthers(modelPicker); modelPicker.open(); }
            } else {
                modelPicker.isOpen() ? modelPicker.close() : (closeOthers(modelPicker), modelPicker.open());
            }
        }
        if ((e.key === 'm' || e.key === 'M') && window.phoxtailChat) {
            window.phoxtailChat.toggleMedia();
        }
        if ((e.key === 'h' || e.key === 'H') && window.phoxtailChat) {
            window.phoxtailChat.toggleHistory();
        }
        if (e.key === 'n' || e.key === 'N') {
            if (!chat.isOpen()) chat.open();
            _newConversation();
        }
    });

    // ── Context chips ────────────────────────────────────────────────────────

    var _contextBlocks = [];
    var _activeChipIdx = -1;
    var _chipsEl = document.getElementById('phoxtail-chatbot-chips');

    function _chipLabel(payload) {
        if (payload.media_type) {
            return payload.media_type + ':' + (payload.title || payload.media_id);
        }
        if (payload.block_type) {
            return payload.variant_identifier
                ? payload.block_type + ' · ' + payload.variant_identifier
                : payload.block_type;
        }
        return payload.page_type || 'page';
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

            var label = document.createElement('span');
            label.className = 'phoxtail-chatbot-chip-label';
            label.textContent = _chipLabel(payload);

            var dismiss = document.createElement('button');
            dismiss.type = 'button';
            dismiss.className = 'phoxtail-chatbot-chip-dismiss';
            dismiss.title = 'Remove';
            dismiss.setAttribute('aria-label', 'Remove ' + _chipLabel(payload));
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
            _dragGhost.textContent = _chipLabel(payload);
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

    function _appendToolIndicator(name) {
        var emptyState = document.getElementById('phoxtail-chatbot-empty');
        if (emptyState) emptyState.style.display = 'none';
        var el = document.createElement('div');
        el.className = 'phoxtail-chatbot-tool-call';
        el.textContent = name + '…';
        chatbotMessages.appendChild(el);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        return el;
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
        if (chatbotMessages) {
            chatbotMessages.innerHTML = _emptyStateHTML;
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
                if (msg.role === 'user') {
                    _appendMessage('phoxtail-chatbot-message--user', msg.content);
                } else if (msg.role === 'assistant') {
                    _appendMessage('phoxtail-chatbot-message--assistant', msg.content);
                } else if (msg.role === 'tool') {
                    var ind = _appendToolIndicator(msg.name);
                    ind.classList.add('phoxtail-chatbot-tool-call--done');
                }
            });
        }).catch(function () {});
    }

    function _loadChat(uuid) {
        if (_busy) return;
        _conversationUuid = uuid;
        _contextBlocks = [];
        _syncChipsUI();
        try { localStorage.setItem(_LS_KEY, uuid); } catch (_) {}
        if (chatbotMessages) {
            chatbotMessages.innerHTML = _emptyStateHTML;
        }
        _rehydrate(uuid);
    }

    var _mediaPickerUrl = chatbotDrawer ? chatbotDrawer.dataset.mediaPickerUrl : null;
    var _mediaPickerModalUrl = chatbotDrawer ? chatbotDrawer.dataset.mediaPickerModalUrl : null;
    var _mediaPickerTab = null;
    var _mediaPickerObserver = null;
    var _mediaBtn = null;

    function _getMediaBtn() {
        if (!_mediaBtn) _mediaBtn = document.getElementById('phoxtail-chatbot-media-btn');
        return _mediaBtn;
    }

    function _setMediaBtnActive(active) {
        var btn = _getMediaBtn();
        if (!btn) return;
        btn.classList.toggle('phoxtail-bar-btn--active', active);
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
        htmx.ajax('GET', _mediaPickerModalUrl, {
            target: '#core-modal-level-1-placeholder-wrapper',
            swap: 'innerHTML',
            values: { content_url: _mediaPickerUrl + '?tab=' + tab }
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
                _openMediaPicker('images');
            }
        },
        beginDrag: function (payload, event) {
            _draggingPayload = payload;
            event.dataTransfer.effectAllowed = 'copy';
            event.dataTransfer.setData('text/plain', JSON.stringify(payload));
            _dragGhost = document.createElement('div');
            _dragGhost.className = 'phoxtail-chatbot-drag-ghost';
            _dragGhost.textContent = _chipLabel(payload);
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

    var _pageBodyEl = document.querySelector('.phoxtail-page-body');

    // ── Page-body block drag-to-chip ─────────────────────────────────────────

    if (_pageBodyEl) {
        _pageBodyEl.addEventListener('dragstart', function (e) {
            // Let native link/image drags pass through untouched
            if (e.target.tagName === 'A' || e.target.tagName === 'IMG') return;
            var block = e.target.closest('.phoxtail-block[draggable="true"]');
            if (!block) return;
            var payload = _payloadFromRow(block);
            if (!payload) { e.preventDefault(); return; }

            _draggingPayload = payload;
            e.dataTransfer.effectAllowed = 'copy';
            e.dataTransfer.setData('text/plain', JSON.stringify(payload));

            _dragGhost = document.createElement('div');
            _dragGhost.className = 'phoxtail-chatbot-drag-ghost';
            _dragGhost.textContent = _chipLabel(payload);
            document.body.appendChild(_dragGhost);
            e.dataTransfer.setDragImage(_dragGhost, 12, 12);

            document.body.setAttribute('data-phoxtail-dragging', '1');
        });

        _pageBodyEl.addEventListener('dragend', function () {
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
        if (_pageBodyEl && typeof htmx !== 'undefined') {
            htmx.trigger(_pageBodyEl, 'phoxtail:page-body-refresh');
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

            var body = { message: fullMessage };
            if (_conversationUuid) body.conversation_uuid = _conversationUuid;
            if (_selectedArtifactId !== null) body.artifact_id = _selectedArtifactId;

            var assistantEl = null;
            var toolIndicators = [];

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
                        if (chunk.done) { _setSending(false); return; }
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
                                var ind = _appendToolIndicator(data.name);
                                toolIndicators.push(ind);
                            } else if (evt === 'tool_end') {
                                var last = toolIndicators.pop();
                                if (last) last.classList.add('phoxtail-chatbot-tool-call--done');
                            } else if (evt === 'blocks_changed') {
                                _handleBlocksChanged(data);
                            } else if (evt === 'token') {
                                if (!assistantEl) {
                                    assistantEl = _appendMessage('phoxtail-chatbot-message--assistant', '');
                                }
                                assistantEl.textContent += data.text;
                                chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
                            } else if (evt === 'done') {
                                _conversationUuid = data.conversation_uuid;
                                try { localStorage.setItem(_LS_KEY, _conversationUuid); } catch (_) {}
                                _setSending(false);
                            }
                        });
                        processChunk();
                    }).catch(function (err) {
                        // AbortError is user-initiated — suppress the error message
                        if (err && err.name === 'AbortError') { _setSending(false); return; }
                        _setSending(false);
                    });
                }
                processChunk();
            }).catch(function (err) {
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
        if (_hlTarget.contains(e.target)) return;
        dismissHighlight();
    });

    // ── Scroll-to-block + highlight ──────────────────────────────────────────

    var _activeBlockIdx = -1;

    function getBlockRows() {
        if (!blocksPanel) return [];
        return Array.prototype.slice.call(blocksPanel.querySelectorAll('.phoxtail-bar-block-row[data-phoxtail-bar-uuid]'));
    }

    function activateBlockAtIndex(idx) {
        var rows = getBlockRows();
        if (!rows.length) return;
        idx = Math.max(0, Math.min(idx, rows.length - 1));
        _activeBlockIdx = idx;

        var row = rows[idx];
        var target = document.getElementById('phoxtail-block-' + row.dataset.phoxtailBarUuid);
        if (!target) return;

        rows.forEach(function (r) { r.classList.remove('phoxtail-bar-block-row--active'); });
        row.classList.add('phoxtail-bar-block-row--active');
        row.scrollIntoView({ block: 'nearest' });

        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        highlightBlock(target);
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
})();
