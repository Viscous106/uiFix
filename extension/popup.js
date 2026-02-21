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

// function showState(state) {
//     [welcomeState, loadingState, resultsState, errorState].forEach(el => {
//         el.classList.add('hidden');
//         el.classList.remove('flex');
//     });
//     state.classList.remove('hidden');
//     state.classList.add('flex');
// }

async function sleep(ms){
  return new Promise(resolve => setTimeout(resolve, ms));
}

function showState(state) {
  [welcomeState, loadingState, resultsState, errorState].forEach(el => {
    el.classList.add('hidden');
    el.classList.remove('active');
  });

  state.classList.remove('hidden');

  requestAnimationFrame(() => {
    state.classList.add('active');
  });
}

function renderIssues(issues) {
    issuesList.innerHTML = '';
    issueCount.textContent = issues.length;

    issues.forEach(issue => {
        const severity = (issue.severity || 'low').toLowerCase();
        const card = document.createElement('div');
        card.className = 'issue-card';
        card.innerHTML = `
        <p class="issue-desc">${issue.description || 'UI Issue Detected'}</p>
        <span class="severity-pill severity-${severity}">${severity}</span>
        </div>
        
        ${issue.selector ? `<p class="issue-selector">${issue.selector}</p>` : ''}
        ${issue.fix ? `<p class="issue-fix">💡 ${issue.fix}</p>` : ''}
        <div class="issue-header">
        `;
        issuesList.appendChild(card);
    });

    showState(resultsState);
}

auditBtn.addEventListener('click', async () => {
    auditBtn.disabled = true;
    btnText.textContent = 'Analyzing...';
    // showState(loadingState);
    showState(loadingState);
    await sleep(700);   

    try {
        // Step 1: Get active tab
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) throw new Error("No active tab found");

        // Guard against restricted pages where scripts cannot be injected
        const tabUrl = tab.url || '';
        const isRestrictedPage =
            tabUrl.startsWith('chrome://') ||
            tabUrl.startsWith('chrome-extension://') ||
            tabUrl.startsWith('https://chrome.google.com/webstore') ||
            tabUrl.startsWith('https://chromewebstore.google.com');
        if (isRestrictedPage) {
            throw new Error('This extension cannot run on Chrome Web Store or internal browser pages (chrome://). Please open a regular website tab and try again.');
        }

        // Step 2: Extract DOM
        loadingText.textContent = 'Extracting DOM structure...';
        const injectionResults = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
        });

        if (
            !injectionResults ||
            !Array.isArray(injectionResults) ||
            injectionResults.length === 0 ||
            !injectionResults[0] ||
            typeof injectionResults[0].result === 'undefined' ||
            injectionResults[0].result === null
        ) {
            throw new Error('Unable to analyze this page. The extension cannot access the content of this tab. Please try a regular website page.');
        }
        const domString = injectionResults[0].result;

        // Step 3: Capture screenshot
        loadingText.textContent = 'Capturing visual snapshot...';
        let screenshotDataUrl;
        try {
            screenshotDataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });
            const captureError = chrome.runtime && chrome.runtime.lastError ? chrome.runtime.lastError.message : null;
            if (!screenshotDataUrl || captureError) {
                const message = captureError || 'Screenshot capture failed. This can happen on chrome:// pages, the Chrome Web Store, or if the tab is not fully loaded.';
                throw new Error(message);
            }
        } catch (captureErr) {
            const message = (chrome.runtime && chrome.runtime.lastError && chrome.runtime.lastError.message) ||
                captureErr.message ||
                'Screenshot capture failed. This can happen on chrome:// pages, the Chrome Web Store, or if the tab is not fully loaded.';
            throw new Error(message);
        }

        // Step 4: Send to backend
        // loadingText.textContent = 'Analyzing with Gemini AI...';
        typeText(loadingText, "Analyzing with Gemini AI...");
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


function typeText(el, text, speed = 40){
  // Clear any existing typing interval on this element
  if (el._typeTextTimer) {
    clearInterval(el._typeTextTimer);
    delete el._typeTextTimer;
  }
  el.textContent = "";
  let i = 0;
  const timer = setInterval(() => {
    el.textContent += text[i++];
    if (i === text.length) {
      clearInterval(timer);
      delete el._typeTextTimer;
    }
  }, speed);
  // Store timer id on the element so it can be cleared on subsequent calls
  el._typeTextTimer = timer;
}