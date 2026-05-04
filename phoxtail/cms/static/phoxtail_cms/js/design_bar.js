(function () {
    var manifestEl = document.getElementById('phoxtail-design-bar-manifest');
    if (!manifestEl) return;

    var manifest = JSON.parse(manifestEl.textContent);
    var bar = document.getElementById('phoxtail-design-bar');
    var blocksBtn = document.getElementById('phoxtail-design-bar-blocks-btn');
    var blocksPanel = document.getElementById('phoxtail-design-bar-blocks-panel');
    var blocksPanelClose = document.getElementById('phoxtail-design-bar-panel-close');
    var chatbotBtn = document.getElementById('phoxtail-design-bar-chatbot-btn');
    var chatbotDrawer = document.getElementById('phoxtail-chatbot-drawer');
    var chatbotCloseBtn = document.getElementById('phoxtail-chatbot-drawer-close');
    var chatbotNewBtn = document.getElementById('phoxtail-chatbot-new-btn');
    var chatbotForm = document.getElementById('phoxtail-chatbot-form');
    var chatbotInput = document.getElementById('phoxtail-chatbot-input');
    var chatbotMessages = document.getElementById('phoxtail-chatbot-messages');
    var menuBtn = document.getElementById('phoxtail-design-bar-menu-btn');
    var menuPanel = document.getElementById('phoxtail-design-bar-menu-panel');
    var menuClose = document.getElementById('phoxtail-design-bar-menu-close');

    // ── Generic panel toggle factory ────────────────────────────────────────

    function makeToggle(panel, button) {
        if (!panel || !button) return null;
        return {
            isOpen: function () { return panel.classList.contains('phoxtail-design-bar-panel--open'); },
            open:   function () {
                panel.classList.add('phoxtail-design-bar-panel--open');
                button.classList.add('phoxtail-design-bar-btn--active');
                button.setAttribute('aria-expanded', 'true');
            },
            close:  function () {
                panel.classList.remove('phoxtail-design-bar-panel--open');
                button.classList.remove('phoxtail-design-bar-btn--active');
                button.setAttribute('aria-expanded', 'false');
                if (panel === blocksPanel) {
                    _activeBlockIdx = -1;
                    getBlockRows().forEach(function (r) { r.classList.remove('phoxtail-design-bar-block-row--active'); });
                }
            }
        };
    }

    var blocks = makeToggle(blocksPanel, blocksBtn);
    var menu = makeToggle(menuPanel, menuBtn);

    // Chatbot uses a drawer class, not a panel class — handled manually but same shape
    var chat = {
        isOpen: function () { return chatbotDrawer && chatbotDrawer.classList.contains('phoxtail-chatbot-drawer--open'); },
        open:   function () {
            chatbotDrawer.classList.add('phoxtail-chatbot-drawer--open');
            chatbotBtn.classList.add('phoxtail-design-bar-btn--active');
            chatbotBtn.setAttribute('aria-expanded', 'true');
        },
        close:  function () {
            chatbotDrawer.classList.remove('phoxtail-chatbot-drawer--open');
            chatbotBtn.classList.remove('phoxtail-design-bar-btn--active');
            chatbotBtn.setAttribute('aria-expanded', 'false');
        }
    };

    // Close all panels except the given one
    function closeOthers(keep) {
        [blocks, menu].forEach(function (t) { if (t && t !== keep && t.isOpen()) t.close(); });
    }

    // ── Wire up toggles ─────────────────────────────────────────────────────

    if (blocks) {
        blocksBtn.addEventListener('click', function () {
            if (blocks.isOpen()) { blocks.close(); } else { closeOthers(blocks); blocks.open(); }
        });
        blocksPanelClose.addEventListener('click', function () { blocks.close(); });
    }

    if (menu) {
        menuBtn.addEventListener('click', function () {
            if (menu.isOpen()) { menu.close(); } else { closeOthers(menu); menu.open(); }
        });
        menuClose.addEventListener('click', function () { menu.close(); });
        // Close menu when a menu item link is activated (target=_blank stays open in new tab, UX still clean)
        menuPanel.addEventListener('click', function (e) {
            if (e.target.closest('.phoxtail-design-bar-menu-item')) menu.close();
        });
    }

    if (chatbotBtn && chatbotDrawer) {
        chatbotBtn.addEventListener('click', function () {
            chat.isOpen() ? chat.close() : chat.open();
        });
        chatbotCloseBtn.addEventListener('click', function () { chat.close(); });
    }

    if (chatbotNewBtn) {
        chatbotNewBtn.addEventListener('click', function () { _newConversation(); });
    }

    // ── Click-outside: close any open panel ─────────────────────────────────

    document.addEventListener('click', function (e) {
        if (bar.contains(e.target)) return;
        if (chatbotDrawer && chatbotDrawer.contains(e.target)) {
            return;
        }
        [blocks, menu].forEach(function (t) { if (t && t.isOpen()) t.close(); });
        if (chat.isOpen()) chat.close();
    });

    // ── Keyboard shortcuts ───────────────────────────────────────────────────

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            if (_hlTarget) { dismissHighlight(); return; }
            if (chat.isOpen()) { chat.close(); return; }
            if (menu && menu.isOpen()) { menu.close(); return; }
            if (blocks && blocks.isOpen()) { blocks.close(); return; }
            return;
        }
        if (e.altKey || e.ctrlKey || e.metaKey) return;
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
        if ((e.key === 'b' || e.key === 'B') && blocks) {
            blocks.isOpen() ? blocks.close() : (closeOthers(blocks), blocks.open());
        }
        if ((e.key === 'v' || e.key === 'V') && chatbotBtn) {
            chat.isOpen() ? chat.close() : chat.open();
        }
        if ((e.key === 'm' || e.key === 'M') && menu) {
            menu.isOpen() ? menu.close() : (closeOthers(menu), menu.open());
        }
    });

    // ── Context chips ────────────────────────────────────────────────────────

    var _contextBlocks = [];
    var _chipsEl = document.getElementById('phoxtail-chatbot-chips');

    function _chipLabel(payload) {
        if (payload.block_type) {
            return payload.variant_identifier
                ? payload.block_type + ' · ' + payload.variant_identifier
                : payload.block_type;
        }
        return payload.page_type || 'page';
    }

    function _chipKey(payload) {
        return payload.block_uuid ? 'block:' + payload.block_uuid : 'page:' + payload.page_id;
    }

    function _syncChipsUI() {
        if (!_chipsEl) return;
        _chipsEl.innerHTML = '';
        if (!_contextBlocks.length) {
            _chipsEl.style.display = 'none';
            return;
        }
        _chipsEl.style.display = '';
        _contextBlocks.forEach(function (payload, i) {
            var chip = document.createElement('span');
            chip.className = 'phoxtail-chatbot-chip';

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
            _chipsEl.appendChild(chip);
        });
    }

    function _addContextBlock(payload) {
        var key = _chipKey(payload);
        for (var i = 0; i < _contextBlocks.length; i++) {
            if (_chipKey(_contextBlocks[i]) === key) return; // dedupe — pulse chip instead
        }
        _contextBlocks.push(payload);
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
        if (row.dataset.phoxtailDesignBarCopy === 'page') {
            return {
                page_id: manifest.id,
                page_type: manifest.type,
                slug: manifest.slug,
                locale: manifest.locale,
                live: manifest.live
            };
        }
        if (row.dataset.phoxtailDesignBarCopy === 'block') {
            var p = {
                page_id: manifest.id,
                block_uuid: row.dataset.phoxtailDesignBarUuid,
                block_type: row.dataset.phoxtailDesignBarType
            };
            if (row.dataset.phoxtailDesignBarVariantId) {
                p.variant_id = parseInt(row.dataset.phoxtailDesignBarVariantId, 10);
                p.variant_identifier = row.dataset.phoxtailDesignBarVariantIdentifier;
            }
            return p;
        }
        return null;
    }

    if (blocksPanel) {
        blocksPanel.addEventListener('dragstart', function (e) {
            var row = e.target.closest('[data-phoxtail-design-bar-copy]');
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

    // Entire chatbot drawer is the drop target; visual highlight on the compose form
    if (chatbotDrawer) {
        chatbotDrawer.addEventListener('dragover', function (e) {
            if (!document.body.hasAttribute('data-phoxtail-dragging')) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            if (chatbotForm) chatbotForm.classList.add('phoxtail-chatbot-compose--drop-target');
        });

        chatbotDrawer.addEventListener('dragleave', function (e) {
            if (!chatbotDrawer.contains(e.relatedTarget)) {
                if (chatbotForm) chatbotForm.classList.remove('phoxtail-chatbot-compose--drop-target');
            }
        });

        chatbotDrawer.addEventListener('drop', function (e) {
            e.preventDefault();
            if (chatbotForm) chatbotForm.classList.remove('phoxtail-chatbot-compose--drop-target');
            if (_draggingPayload) {
                _addContextBlock(_draggingPayload);
                if (chatbotInput) chatbotInput.focus();
            }
        });
    }

    // ── Chatbot compose ──────────────────────────────────────────────────────

    if (chatbotInput) {
        chatbotInput.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 128) + 'px';
        });
        chatbotInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (chatbotForm) chatbotForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            }
        });
    }

    // ── Chatbot state ────────────────────────────────────────────────────────

    var _LS_KEY = 'phoxtail.chatbot.conversation_uuid';
    var _conversationUuid = null;
    var _busy = false;

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

    function _setSending(active) {
        _busy = active;
        var sendBtn = chatbotForm && chatbotForm.querySelector('.phoxtail-chatbot-send-btn');
        if (sendBtn) sendBtn.disabled = active;
        if (chatbotInput) chatbotInput.disabled = active;
    }

    function _newConversation() {
        if (_busy) return;
        _conversationUuid = null;
        _clearContextBlocks();
        try { localStorage.removeItem(_LS_KEY); } catch (_) {}
        if (chatbotMessages) {
            chatbotMessages.innerHTML = '';
            var emptyEl = document.createElement('div');
            emptyEl.className = 'phoxtail-chatbot-empty-state';
            emptyEl.id = 'phoxtail-chatbot-empty';
            chatbotMessages.appendChild(emptyEl);
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

    // Rehydrate on load if we have a stored UUID
    (function () {
        try {
            var storedUuid = localStorage.getItem(_LS_KEY);
            if (storedUuid) _rehydrate(storedUuid);
        } catch (_) {}
    })();

    // ── Block refresh (HTMX-powered per-block updates) ────────────────────────

    var _pageBodyEl = document.querySelector('.phoxtail-page-body');

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
            _clearContextBlocks();
            _setSending(true);

            var body = { message: fullMessage };
            if (_conversationUuid) body.conversation_uuid = _conversationUuid;

            var assistantEl = null;
            var toolIndicators = [];

            fetch('/api/agent/v1/chat/stream/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': _getCsrfToken(),
                },
                body: JSON.stringify(body),
            }).then(function (res) {
                if (!res.ok) {
                    _appendMessage('phoxtail-chatbot-message--assistant', 'Error ' + res.status + '. Please try again.');
                    _setSending(false);
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
                    }).catch(function () { _setSending(false); });
                }
                processChunk();
            }).catch(function () {
                _appendMessage('phoxtail-chatbot-message--assistant', 'Network error. Please try again.');
                _setSending(false);
            });
        });
    }

    // ── Copy to clipboard ────────────────────────────────────────────────────

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

    // ── Scroll-to-block + highlight ──────────────────────────────────────────

    var _activeBlockIdx = -1;

    function getBlockRows() {
        if (!blocksPanel) return [];
        return Array.prototype.slice.call(blocksPanel.querySelectorAll('.phoxtail-design-bar-block-row[data-phoxtail-design-bar-uuid]'));
    }

    function activateBlockAtIndex(idx) {
        var rows = getBlockRows();
        if (!rows.length) return;
        idx = Math.max(0, Math.min(idx, rows.length - 1));
        _activeBlockIdx = idx;

        var row = rows[idx];
        var target = document.getElementById('phoxtail-block-' + row.dataset.phoxtailDesignBarUuid);
        if (!target) return;

        rows.forEach(function (r) { r.classList.remove('phoxtail-design-bar-block-row--active'); });
        row.classList.add('phoxtail-design-bar-block-row--active');
        row.scrollIntoView({ block: 'nearest' });

        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        highlightBlock(target);
    }

    if (blocksPanel) {
        blocksPanel.addEventListener('click', function (e) {
            if (e.target.closest('.phoxtail-design-bar-copy-btn')) return;

            var row = e.target.closest('.phoxtail-design-bar-block-row');
            if (!row || !row.dataset.phoxtailDesignBarUuid) return;

            var idx = getBlockRows().indexOf(row);
            if (idx !== -1) activateBlockAtIndex(idx);
        });
    }
})();
