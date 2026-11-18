// Help panel of the teacher pages.
//
// The panel adds a "Help" button to the page. The teacher asks a question;
// the server (POST /teacher/assistant/chat) answers with text and with
// proposed changes to input files. The teacher reviews the diff of each
// proposal and clicks "Apply" (POST /teacher/assistant/apply). Nothing
// changes before that click.
//
// A page can set window.JELAI_ASSISTANT_HOOKS before it loads this script:
//   currentPath()               the input file that is open in the editor
//   afterApply(path)            called after a proposal is saved
//   openProposal(path, content) puts a proposal in the editor, without save
(function () {
    'use strict';
    const STORAGE_KEY = 'jelai-assistant-history';
    const hooks = window.JELAI_ASSISTANT_HOOKS || {};
    const STARTERS = [
        'How do I change the prompt of the tutor?',
        'How do I add a new assignment?',
        'Which notebooks have missing files?',
        'How do I change the LLM provider?',
    ];

    // Each item: {role: 'user'|'assistant', content, raw?, proposals?}
    let history = [];
    try { history = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]'); } catch (e) { history = []; }
    let busy = false;

    const css = `
    .ja-root { --ja-bg: var(--bg-secondary, var(--surface, #fff)); --ja-soft: var(--bg-card, var(--neutral-bg, #eeede8));
        --ja-text: var(--text-primary, var(--text, #1f2328)); --ja-muted: var(--text-secondary, var(--muted, #5f6368));
        --ja-line: var(--border, var(--line, #e4e1d8)); --ja-accent: var(--accent-blue, var(--accent, #2f6fb3));
        --ja-ok: var(--accent-green, var(--ok, #2e7d4f)); --ja-err: var(--accent-red, var(--error, #b3261e));
        --ja-warn: var(--accent-orange, var(--warn, #a15c00));
        font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; color: var(--ja-text); }
    .ja-fab { position: fixed; right: 20px; bottom: 20px; z-index: 1000; border: none; border-radius: 999px;
        padding: 12px 18px; background: var(--ja-accent); color: #fff; font: inherit; font-size: 14px;
        font-weight: 600; cursor: pointer; box-shadow: 0 4px 16px rgba(0,0,0,.25); }
    .ja-panel { position: fixed; top: 0; right: 0; bottom: 0; width: min(460px, 100vw); z-index: 1001;
        background: var(--ja-bg); border-left: 1px solid var(--ja-line); display: none; flex-direction: column;
        box-shadow: -4px 0 24px rgba(0,0,0,.2); }
    .ja-panel.open { display: flex; }
    .ja-head { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--ja-line); }
    .ja-head h2 { flex: 1; font-size: 16px; margin: 0; }
    .ja-head button, .ja-btn { background: var(--ja-soft); border: 1px solid var(--ja-line); color: var(--ja-text);
        border-radius: 8px; padding: 6px 10px; font: inherit; font-size: 13px; cursor: pointer; }
    .ja-btn.primary { background: var(--ja-accent); border-color: var(--ja-accent); color: #fff; }
    .ja-btn:disabled { opacity: .5; cursor: default; }
    .ja-log { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 10px; font-size: 14px; line-height: 1.5; }
    .ja-msg { padding: 8px 12px; border-radius: 10px; max-width: 100%; overflow-wrap: anywhere; }
    .ja-msg.user { align-self: flex-end; background: var(--ja-accent); color: #fff; white-space: pre-wrap; }
    .ja-msg.assistant { background: var(--ja-soft); }
    .ja-msg.error { background: transparent; border: 1px solid var(--ja-err); color: var(--ja-err); }
    .ja-msg p { margin: 0 0 6px; } .ja-msg p:last-child { margin-bottom: 0; }
    .ja-msg ul, .ja-msg ol { margin: 0 0 6px 20px; padding: 0; }
    .ja-msg code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; background: rgba(127,127,127,.18);
        padding: 1px 4px; border-radius: 4px; }
    .ja-msg pre { background: rgba(127,127,127,.12); padding: 8px; border-radius: 6px; overflow-x: auto; margin: 0 0 6px; }
    .ja-msg pre code { background: none; padding: 0; }
    .ja-ref { font-size: 12px; font-weight: 600; color: var(--ja-accent); }
    .ja-card { border: 1px solid var(--ja-line); border-radius: 10px; padding: 10px; background: var(--ja-bg); font-size: 13px; }
    .ja-card .title { font-weight: 600; margin-bottom: 6px; overflow-wrap: anywhere; }
    .ja-diff { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; max-height: 260px; overflow: auto;
        background: rgba(127,127,127,.08); border-radius: 6px; padding: 6px; white-space: pre; }
    .ja-diff .add { color: var(--ja-ok); } .ja-diff .del { color: var(--ja-err); } .ja-diff .hunk { color: var(--ja-muted); }
    .ja-note { margin-top: 6px; font-size: 12px; } .ja-note.err { color: var(--ja-err); } .ja-note.warn { color: var(--ja-warn); }
    .ja-note.ok { color: var(--ja-ok); }
    .ja-actions { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
    .ja-starters { display: flex; flex-wrap: wrap; gap: 6px; }
    .ja-intro { color: var(--ja-muted); font-size: 13px; }
    .ja-form { border-top: 1px solid var(--ja-line); padding: 10px 16px; display: flex; gap: 8px; align-items: flex-end; }
    .ja-form textarea { flex: 1; min-height: 40px; max-height: 160px; resize: vertical; background: var(--ja-soft);
        color: var(--ja-text); border: 1px solid var(--ja-line); border-radius: 8px; padding: 8px; font: inherit; font-size: 14px; }
    `;

    function el(tag, attrs = {}, text = '') {
        const node = document.createElement(tag);
        Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
        if (text) node.textContent = text;
        return node;
    }

    function escapeHtml(text) {
        return text.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function inline(text) {
        return escapeHtml(text)
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\[Proposal (\d+)\]/g, '<span class="ja-ref">↓ Proposal $1</span>');
    }

    // A small Markdown renderer: paragraphs, lists, code blocks, inline code, bold.
    function renderMarkdown(text) {
        const lines = text.split('\n');
        const html = [];
        let list = null, para = [], code = null;
        const flushPara = () => { if (para.length) { html.push('<p>' + inline(para.join(' ')) + '</p>'); para = []; } };
        const flushList = () => { if (list) { html.push(`</${list}>`); list = null; } };
        for (const line of lines) {
            if (code !== null) {
                if (line.trim().startsWith('```')) { html.push('<pre><code>' + escapeHtml(code.join('\n')) + '</code></pre>'); code = null; }
                else code.push(line);
                continue;
            }
            if (line.trim().startsWith('```')) { flushPara(); flushList(); code = []; continue; }
            const bullet = line.match(/^\s*[-*]\s+(.*)$/);
            const number = line.match(/^\s*\d+[.)]\s+(.*)$/);
            const heading = line.match(/^#{1,6}\s+(.*)$/);
            if (bullet || number) {
                flushPara();
                const kind = bullet ? 'ul' : 'ol';
                if (list !== kind) {
                    flushList();
                    const start = number ? parseInt(line.trim(), 10) : 1;
                    html.push(kind === 'ol' && start > 1 ? `<ol start="${start}">` : `<${kind}>`);
                    list = kind;
                }
                html.push('<li>' + inline((bullet || number)[1]) + '</li>');
            } else if (heading) {
                flushPara(); flushList();
                html.push('<p><strong>' + inline(heading[1]) + '</strong></p>');
            } else if (!line.trim()) {
                flushPara(); flushList();
            } else {
                flushList(); para.push(line.trim());
            }
        }
        if (code !== null) html.push('<pre><code>' + escapeHtml(code.join('\n')) + '</code></pre>');
        flushPara(); flushList();
        return html.join('');
    }

    function save() {
        try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-30))); } catch (e) { /* not available */ }
    }

    function renderDiff(diff) {
        const box = el('div', { class: 'ja-diff' });
        diff.split('\n').forEach(line => {
            let cls = '';
            if (line.startsWith('+') && !line.startsWith('+++')) cls = 'add';
            else if (line.startsWith('-') && !line.startsWith('---')) cls = 'del';
            else if (line.startsWith('@@')) cls = 'hunk';
            box.appendChild(el('div', cls ? { class: cls } : {}, line || ' '));
        });
        return box;
    }

    function renderProposal(proposal, index) {
        const card = el('div', { class: 'ja-card' });
        card.appendChild(el('div', { class: 'title' }, `Proposal ${index + 1}: ${proposal.path}${proposal.new_file ? ' (new file)' : ''}`));
        if (proposal.error) {
            card.appendChild(el('div', { class: 'ja-note err' }, proposal.error));
            return card;
        }
        card.appendChild(renderDiff(proposal.diff));
        (proposal.errors || []).forEach(e => card.appendChild(el('div', { class: 'ja-note err' }, e)));
        (proposal.warnings || []).forEach(w => card.appendChild(el('div', { class: 'ja-note warn' }, w)));
        const status = el('div', { class: 'ja-note' });
        const actions = el('div', { class: 'ja-actions' });
        if (proposal.applied) {
            status.className = 'ja-note ok';
            status.textContent = 'Applied. The tutor uses it for the next message.';
        } else {
            const apply = el('button', { class: 'ja-btn primary' }, 'Apply');
            apply.disabled = !proposal.applicable;
            apply.onclick = async () => {
                apply.disabled = true;
                try {
                    await api('/teacher/assistant/apply', {
                        path: proposal.path, content: proposal.content, base_sha256: proposal.base_sha256,
                    });
                    proposal.applied = true;
                    save();
                    card.replaceWith(renderProposal(proposal, index));
                    if (hooks.afterApply) hooks.afterApply(proposal.path);
                } catch (err) {
                    status.className = 'ja-note err';
                    status.textContent = (err.errors || [String(err)]).join(' ');
                    apply.disabled = false;
                }
            };
            actions.appendChild(apply);
            if (hooks.openProposal) {
                const edit = el('button', { class: 'ja-btn' }, 'Edit first');
                edit.title = 'Open the proposal in the editor. It is not saved until you click Save.';
                edit.onclick = () => hooks.openProposal(proposal.path, proposal.content);
                actions.appendChild(edit);
            }
        }
        card.append(status, actions);
        return card;
    }

    async function api(url, body) {
        const resp = await fetch(url, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        let data = null;
        try { data = await resp.json(); } catch (e) { data = null; }
        if (!resp.ok) {
            const detail = data && data.detail;
            throw (typeof detail === 'object' && detail) ? detail : { errors: [detail || `HTTP ${resp.status}`] };
        }
        return data;
    }

    // --- DOM ---------------------------------------------------------------
    const style = el('style');
    style.textContent = css;
    document.head.appendChild(style);

    const root = el('div', { class: 'ja-root' });
    const fab = el('button', { class: 'ja-fab', title: 'Ask how to configure JELAI' }, '? Help');
    const panel = el('div', { class: 'ja-panel', role: 'dialog', 'aria-label': 'JELAI help' });
    const head = el('div', { class: 'ja-head' });
    const clear = el('button', { title: 'Start a new conversation' }, 'New');
    const close = el('button', { title: 'Close', 'aria-label': 'Close' }, '✕');
    head.append(el('h2', {}, 'JELAI help'), clear, close);
    const log = el('div', { class: 'ja-log', 'aria-live': 'polite' });
    const form = el('form', { class: 'ja-form' });
    const input = el('textarea', { placeholder: 'Ask how to configure JELAI…', rows: '2' });
    const send = el('button', { class: 'ja-btn primary', type: 'submit' }, 'Send');
    form.append(input, send);
    panel.append(head, log, form);
    root.append(fab, panel);
    document.body.appendChild(root);

    function render() {
        log.innerHTML = '';
        if (!history.length) {
            log.appendChild(el('div', { class: 'ja-intro' },
                'Ask how to configure the tutor, the assignments or the LLM. The assistant reads the documentation and ' +
                'the settings of this server. It can propose changes to the input files: you review each change and click Apply.'));
            const starters = el('div', { class: 'ja-starters' });
            STARTERS.forEach(q => {
                const b = el('button', { class: 'ja-btn', type: 'button' }, q);
                b.onclick = () => ask(q);
                starters.appendChild(b);
            });
            log.appendChild(starters);
        }
        history.forEach(item => {
            const msg = el('div', { class: 'ja-msg ' + item.role });
            if (item.role === 'assistant') msg.innerHTML = renderMarkdown(item.content);
            else msg.textContent = item.content;
            log.appendChild(msg);
            (item.proposals || []).forEach((p, i) => log.appendChild(renderProposal(p, i)));
        });
        if (busy) log.appendChild(el('div', { class: 'ja-intro' }, 'Thinking…'));
        log.scrollTop = log.scrollHeight;
    }

    async function ask(question) {
        question = (question || '').trim();
        if (!question || busy) return;
        history.push({ role: 'user', content: question });
        busy = true;
        send.disabled = true;
        render();
        try {
            const messages = history.filter(h => h.role !== 'error')
                .map(h => ({ role: h.role, content: h.raw || h.content }));
            const data = await api('/teacher/assistant/chat', {
                messages, current_path: hooks.currentPath ? hooks.currentPath() : null,
            });
            history.push({ role: 'assistant', content: data.reply, raw: data.raw_reply, proposals: data.proposals });
        } catch (err) {
            history.push({ role: 'error', content: (err.errors || [String(err)]).join(' ') });
        }
        busy = false;
        send.disabled = false;
        save();
        render();
    }

    fab.onclick = () => { panel.classList.add('open'); fab.style.display = 'none'; render(); input.focus(); };
    close.onclick = () => { panel.classList.remove('open'); fab.style.display = ''; };
    clear.onclick = () => { history = []; save(); render(); };
    form.onsubmit = e => { e.preventDefault(); const q = input.value; input.value = ''; ask(q); };
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
    });
})();
