let currentSessionId = null;

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

    issues.forEach(issue => {
        const severity = (issue.severity || 'low').toLowerCase();

        const card = document.createElement('div');
        card.className = 'issue-card';

        card.innerHTML = `
            <div>
                <strong>${issue.description || 'UI Issue Detected'}</strong>
                <div>Severity: ${severity}</div>
                ${issue.selector ? `<div>Selector: ${issue.selector}</div>` : ''}
                ${issue.fix ? `<div>Fix: ${issue.fix}</div>` : ''}
            </div>
        `;

        issuesList.appendChild(card);
    });

    showState(resultsState);

    if (chatContainer) {
        chatContainer.classList.remove('hidden');
    }
}

// ----------------------
// CHAT SYSTEM
// ----------------------

function appendMessage(role, text) {
    const msg = document.createElement('div');
    msg.className = role === 'user' ? 'chat-user' : 'chat-ai';
    msg.textContent = text;
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendChatMessage(message) {

    if (!currentSessionId) {
        appendMessage('ai', 'Session not found. Run audit again.');
        return;
    }

    appendMessage('user', message);
    chatInput.value = '';

    try {

        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: message
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Backend error: ${errorText}`);
        }

        const data = await response.json();

        console.log("CHAT RESPONSE:", data);

        if (!data.reply) {
            appendMessage('ai', 'No reply from AI.');
            return;
        }

        appendMessage('ai', data.reply);

        if (chatRemaining) {
            chatRemaining.textContent = data.turns_remaining ?? 0;
        }

        if (data.session_expired) {
            chatInput.disabled = true;
            chatSendBtn.disabled = true;
            appendMessage('ai', 'Session expired. Run a new audit.');
        }

    } catch (err) {
        console.error("Chat Error:", err);
        appendMessage('ai', 'Chat failed. Check backend.');
    }
}

// Button click
chatSendBtn?.addEventListener('click', () => {
    const message = chatInput.value.trim();
    if (!message) return;
    sendChatMessage(message);
});

// Enter key
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

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Backend error: ${errorText}`);
        }

        const data = await response.json();

        console.log("AUDIT RESPONSE:", data);

        if (!data.session_id) {
            throw new Error("Session ID missing from backend.");
        }

        currentSessionId = data.session_id;
        console.log("Session ID:", currentSessionId);

        renderIssues(data.issues || []);

        if (chatMessages) chatMessages.innerHTML = '';
        if (chatInput) chatInput.disabled = false;
        if (chatSendBtn) chatSendBtn.disabled = false;
        if (chatRemaining) chatRemaining.textContent = 6;

        btnText.textContent = 'Run Again';

    } catch (err) {
        console.error("Audit Error:", err);
        errorText.textContent = err.message;
        showState(errorState);
        btnText.textContent = 'Try Again';
    } finally {
        auditBtn.disabled = false;
    }
});