const auditBtn = document.getElementById('audit-btn');
const btnText = document.getElementById('btn-text');
const welcomeState = document.getElementById('welcome-state');
const loadingState = document.getElementById('loading-state');
const loadingText = document.getElementById('loading-text');
const resultsState = document.getElementById('results-state');
const issuesList = document.getElementById('issues-list');
const issueCount = document.getElementById('issue-count');
const errorState = document.getElementById('error-state');
const errorText = document.getElementById('error-text');

function showState(state) {
    [welcomeState, loadingState, resultsState, errorState].forEach(el => {
        el.classList.add('hidden');
        el.classList.remove('flex');
    });
    state.classList.remove('hidden');
    state.classList.add('flex');
}

function renderIssues(issues) {
    issuesList.innerHTML = '';
    issueCount.textContent = issues.length;

    issues.forEach(issue => {
        const severity = (issue.severity || 'low').toLowerCase();
        const card = document.createElement('div');
        card.className = 'issue-card';
        card.innerHTML = `
            <div class="flex items-start justify-between gap-2 mb-2">
                <p class="text-xs font-semibold text-white/90 leading-snug flex-1">${issue.description || 'UI Issue Detected'}</p>
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-md border severity-${severity} shrink-0 uppercase">${severity}</span>
            </div>
            ${issue.selector ? `<p class="text-[10px] font-mono text-blue-400/70 bg-blue-500/5 border border-blue-500/10 rounded px-2 py-1 mb-2 truncate">${issue.selector}</p>` : ''}
            ${issue.fix ? `<p class="text-[10px] text-white/40 leading-relaxed">💡 ${issue.fix}</p>` : ''}
        `;
        issuesList.appendChild(card);
    });

    showState(resultsState);
}

auditBtn.addEventListener('click', async () => {
    auditBtn.disabled = true;
    btnText.textContent = 'Analyzing...';
    showState(loadingState);

    try {
        // Step 1: Get active tab
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) throw new Error("No active tab found");

        // Step 2: Extract DOM
        loadingText.textContent = 'Extracting DOM structure...';
        const injectionResults = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
        });
        const domString = injectionResults[0].result;

        // Step 3: Capture screenshot
        loadingText.textContent = 'Capturing visual snapshot...';
        const screenshotDataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });

        // Step 4: Send to backend
        loadingText.textContent = 'Analyzing with Gemini AI...';
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

        if (!response.ok) throw new Error(`Backend error: ${response.status}`);

        const data = await response.json();
        renderIssues(data.issues || []);
        btnText.textContent = 'Run Again';

    } catch (err) {
        console.error("Audit Error:", err);
        // Check if it's just backend not running yet
        if (err.message.includes('fetch') || err.message.includes('Failed to fetch')) {
            errorText.textContent = 'Backend not running. Start the FastAPI server first.';
        } else {
            errorText.textContent = err.message || 'Something went wrong. Check the console.';
        }
        showState(errorState);
        btnText.textContent = 'Try Again';
    } finally {
        auditBtn.disabled = false;
    }
});
