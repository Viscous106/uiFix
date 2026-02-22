let currentSessionId = null;
let isAuditRunning = false;

// ----------------------
// DOM ELEMENTS
// ----------------------

const auditBtn = document.getElementById('audit-btn');
const btnText = document.getElementById('btn-text');

const welcomeState = document.getElementById('welcome-state');
const loadingState = document.getElementById('loading-state');
const loadingText = document.getElementById('loading-text');
const resultsState = document.getElementById('results-state');
const errorState = document.getElementById('error-state');
const errorText = document.getElementById('error-text');

const issuesList = document.getElementById('issues-list');
const issueCount = document.getElementById('issue-count');

const chatContainer = document.getElementById('chat-container');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const chatSendBtn = document.getElementById('chat-send');
const chatRemaining = document.getElementById('chat-remaining');

// ----------------------
// STATE SWITCH
// ----------------------

function showState(state) {
    [welcomeState, loadingState, resultsState, errorState].forEach(el => {
        if (!el) return;
        el.classList.add('hidden');
    });
    state.classList.remove('hidden');
}

// ----------------------
// ISSUE RENDER
// ----------------------

function renderIssues(issues) {

    issuesList.innerHTML = '';
    issueCount.textContent = issues.length;

    if (!issues.length) {
        const empty = document.createElement('div');
        empty.textContent = "No issues detected 🎉";
        empty.style.padding = "8px";
        issuesList.appendChild(empty);
    }

    issues.forEach(issue => {

        const severity = (issue.severity || 'low').toLowerCase();

        const card = document.createElement('div');
        card.style.padding = "8px";
        card.style.marginBottom = "8px";
        card.style.borderRadius = "8px";
        card.style.background = "rgba(255,255,255,0.05)";
        card.style.border = "1px solid rgba(255,255,255,0.08)";
        card.style.fontSize = "12px";
        card.style.lineHeight = "1.5";
        card.style.cursor = issue.selector ? "pointer" : "default";

        const title = document.createElement('div');
        title.style.fontWeight = "600";
        title.style.marginBottom = "4px";
        title.textContent = issue.description || "UI Issue Detected";

        const severityDiv = document.createElement('div');
        severityDiv.style.marginBottom = "4px";
        severityDiv.style.opacity = "0.8";
        severityDiv.textContent = "Severity: " + severity;

        card.appendChild(title);
        card.appendChild(severityDiv);

        if (issue.selector) {
            const selectorDiv = document.createElement('div');
            selectorDiv.style.opacity = "0.6";
            selectorDiv.style.marginBottom = "4px";
            selectorDiv.textContent = "Selector: " + issue.selector;
            card.appendChild(selectorDiv);
        }

        if (issue.fix) {
            const fixDiv = document.createElement('div');
            fixDiv.style.marginBottom = "6px";
            fixDiv.textContent = "Fix: " + issue.fix;
            card.appendChild(fixDiv);

            const copyBtn = document.createElement('button');
            copyBtn.textContent = "Copy Fix";
            copyBtn.style.padding = "4px 8px";
            copyBtn.style.fontSize = "11px";
            copyBtn.style.borderRadius = "4px";
            copyBtn.style.border = "none";
            copyBtn.style.cursor = "pointer";
            copyBtn.style.background = "linear-gradient(90deg,#6366f1,#8b5cf6)";
            copyBtn.style.color = "white";
            copyBtn.style.transition = "0.2s ease";

            copyBtn.onmouseover = () => copyBtn.style.transform = "scale(1.05)";
            copyBtn.onmouseleave = () => copyBtn.style.transform = "scale(1)";

            copyBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(issue.fix);
            });

            card.appendChild(copyBtn);
        }

        if (issue.selector) {
            card.addEventListener('click', async () => {
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

                chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    func: (selector) => {
                        const el = document.querySelector(selector);
                        if (!el) return;
                        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        el.style.outline = '3px solid red';
                        setTimeout(() => el.style.outline = '', 3000);
                    },
                    args: [issue.selector]
                });
            });
        }

        issuesList.appendChild(card);
    });

    showState(resultsState);

    if (chatContainer) {
        chatContainer.classList.remove('hidden');
    }
}

// ----------------------
// AI TEXT FORMATTER
// ----------------------

function formatAIText(text) {

    text = text.replace(/(\d+\.\s)/g, "<br><br><strong>$1</strong>");
    text = text.replace(/-\s/g, "<br>&nbsp;&nbsp;• ");
    text = text.replace(/:\s/g, ":<br>&nbsp;&nbsp;");
    text = text.replace(/(<br>){3,}/g, "<br><br>");

    return text;
}

// ----------------------
// CHAT SYSTEM
// ----------------------

function appendMessage(role, text) {

    const wrapper = document.createElement('div');
    wrapper.style.display = "flex";
    wrapper.style.marginBottom = "6px";
    wrapper.style.justifyContent = role === 'user' ? "flex-end" : "flex-start";

    const bubble = document.createElement('div');
    bubble.style.maxWidth = "85%";
    bubble.style.padding = "8px 10px";
    bubble.style.borderRadius = "10px";
    bubble.style.fontSize = "12px";
    bubble.style.lineHeight = "1.6";
    bubble.style.wordWrap = "break-word";

    if (role === 'user') {
        bubble.style.background = "linear-gradient(90deg,#6366f1,#8b5cf6)";
        bubble.style.color = "white";
        bubble.textContent = text;
    } else {
        bubble.style.background = "rgba(255,255,255,0.06)";
        bubble.style.border = "1px solid rgba(255,255,255,0.08)";
        bubble.style.color = "#e2e8f0";
        bubble.innerHTML = formatAIText(text);
    }

    wrapper.appendChild(bubble);
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendChatMessage(message) {

    if (!currentSessionId) {
        appendMessage('ai', 'Session not found. Run audit again.');
        return;
    }

    if (!message.trim()) return;

    appendMessage('user', message);
    chatInput.value = '';
    chatSendBtn.disabled = true;

    try {

        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: message
            })
        });

        if (!response.ok) throw new Error("Backend error");

        const data = await response.json();

        appendMessage('ai', data.reply || 'No reply.');

        if (chatRemaining) {
            chatRemaining.textContent = data.turns_remaining ?? 0;
        }

        if (data.session_expired) {
            chatInput.disabled = true;
            chatSendBtn.disabled = true;
            appendMessage('ai', 'Session expired. Run new audit.');
        }

    } catch (err) {
        appendMessage('ai', 'AI unavailable.');
    } finally {
        chatSendBtn.disabled = false;
    }
}

chatSendBtn?.addEventListener('click', () => {
    const message = chatInput.value.trim();
    sendChatMessage(message);
});

chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        chatSendBtn.click();
    }
});

// ----------------------
// AUDIT SYSTEM
// ----------------------

auditBtn.addEventListener('click', async () => {

    if (isAuditRunning) return;
    isAuditRunning = true;

    auditBtn.disabled = true;
    btnText.textContent = 'Analyzing...';
    showState(loadingState);

    try {

        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) throw new Error("No active tab");

        const injectionResults = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
        });

        if (!injectionResults || !injectionResults[0]?.result) {
            throw new Error('Cannot access page');
        }

        const domString = injectionResults[0].result;

        const screenshotDataUrl =
            await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });

        const response = await fetch('http://localhost:8000/audit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screenshot_base64: screenshotDataUrl.split(',')[1],
                dom_string: domString,
                page_url: tab.url,
                page_title: tab.title
            })
        });

        if (!response.ok) throw new Error("Backend error");

        const data = await response.json();

        if (!data.session_id) {
            throw new Error("Session ID missing.");
        }

        currentSessionId = data.session_id;

        renderIssues(data.issues || []);

        chatMessages.innerHTML = '';
        chatInput.disabled = false;
        chatSendBtn.disabled = false;
        if (chatRemaining) chatRemaining.textContent = 6;

        btnText.textContent = 'Run Again';

    } catch (err) {
        errorText.textContent = err.message;
        showState(errorState);
        btnText.textContent = 'Try Again';
    } finally {
        auditBtn.disabled = false;
        isAuditRunning = false;
    }
});