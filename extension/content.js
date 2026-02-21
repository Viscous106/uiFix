(function extractDOM() {
    // 1. Clone the body to avoid mutating the actual page
    const bodyClone = document.body.cloneNode(true);

    // 2. Elements to completely remove
    const removeSelectors = [
        'script', 'style', 'noscript', 'iframe', 'svg', 'canvas', 'video', 'audio', 'picture', 'map'
    ];
    removeSelectors.forEach(selector => {
        bodyClone.querySelectorAll(selector).forEach(el => el.remove());
    });

    // 3. Walker to strip heavy content and unnecessary attributes
    const walker = document.createTreeWalker(bodyClone, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, null, false);
    let node;
    while ((node = walker.nextNode())) {
        if (node.nodeType === Node.TEXT_NODE) {
            const text = node.textContent.trim();
            if (text.length > 50) {
                // Truncate long text blocks to save tokens
                node.textContent = text.substring(0, 50) + "... [TRUNCATED]";
            }
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            // Keep only essential attributes for AI context
            const keepAttributes = ['id', 'class', 'role', 'aria-label', 'aria-hidden', 'type', 'name', 'placeholder', 'href', 'src', 'alt'];
            const attributes = Array.from(node.attributes);
            for (let attr of attributes) {
                if (!keepAttributes.includes(attr.name)) {
                    node.removeAttribute(attr.name);
                }
            }
        }
    }

    // 4. Serialize to string
    const domString = bodyClone.innerHTML;

    // Return the string (this is captured by chrome.scripting.executeScript in sidepanel.js)
    return domString;
})();
