// Global DOM elements for iframe windows and taskbar
const iframeWindowsContainer = document.getElementById('iframeWindowsContainer');
const taskbar = document.getElementById('taskbar');
const taskbarTabs = document.getElementById('taskbarTabs');

// Global state for iframe windows and z-index
const activeIframeWindows = new Map(); // Map: windowId -> { element, url, title, folderName, isMinimized }
let highestZIndex = 100; // Starting z-index for iframe windows

/**
 * Generates a unique ID for iframe windows.
 * @returns {string} A unique ID.
 */
function generateUniqueId() {
    return 'iframe-window-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
}

/**
 * Handles opening a URL, either in a new tab or an iframe window based on settings.
 * @param {string} url - The URL to open.
 * @param {string} title - The title for the window/tab.
 * @param {string} folderType - 'python' or 'php'
 * @param {number|null} [width=null] - Optional width for the iframe window.
 * @param {number|null} [height=null] - Optional height for the iframe window.
 */
function handleOpenUrl(url, title, folderType, width = null, height = null) {
    if (openInIframeGlobally) {
        openUrlInNewIframeWindow(url, title, folderType, width, height);
    } else {
        window.open(url, '_blank');
    }
}

/**
 * Opens a URL in a new draggable, resizable iframe window.
 * @param {string} url - The URL to load.
 * @param {string} title - The title for the window.
 * @param {string} folderName - The associated folder name.
 * @param {number|null} [initialWidth=null] - Optional initial width for the iframe window.
 * @param {number|null} [initialHeight=null] - Optional initial height for the iframe window.
 */
function openUrlInNewIframeWindow(url, title, folderName, initialWidth = null, initialHeight = null) {
    const windowId = generateUniqueId();

    const existingWindow = Array.from(activeIframeWindows.values()).find(
        win => win.folderName === folderName && win.url === url
    );

    if (existingWindow) {
        restoreWindowFromTaskbar(existingWindow.id);
        return;
    }

    const iframeWindow = document.createElement('div');
    iframeWindow.id = windowId;
    iframeWindow.className = 'iframe-window';
    iframeWindow.style.left = `${getRandomInt(10, 50)}vw`;
    iframeWindow.style.top = `${getRandomInt(10, 30)}vh`;
    // Use provided width/height or default to 70vw/70vh
    iframeWindow.style.width = initialWidth ? `${initialWidth}px` : '70vw';
    iframeWindow.style.height = initialHeight ? `${initialHeight}px` : '70vh';
    iframeWindow.dataset.folderName = folderName;

    iframeWindow.innerHTML = `
        <div class="iframe-window-titlebar">
            <span class="title-text">${title}</span>
            <div class="iframe-window-controls">
                <button class="iframe-window-control-btn minimize-btn" title="Minimize"><i class="fas fa-minus"></i></button>
                <button class="iframe-window-control-btn close-btn" title="Minimize to Taskbar"><i class="fas fa-times"></i></button>
            </div>
        </div>
        <div class="iframe-window-content">
            <div class="iframe-loading-spinner"></div>
            <iframe src="" title="${title}"></iframe>
        </div>
    `;

    const iframeElement = iframeWindow.querySelector('iframe');
    const spinner = iframeWindow.querySelector('.iframe-loading-spinner');
    const minimizeBtn = iframeWindow.querySelector('.minimize-btn');
    const closeBtn = iframeWindow.querySelector('.close-btn');
    const titlebar = iframeWindow.querySelector('.iframe-window-titlebar');

    iframeElement.classList.add('hidden');
    spinner.classList.remove('hidden');

    const loadingTimeout = setTimeout(() => {
        spinner.classList.add('hidden');
        iframeElement.classList.remove('hidden');
        showMessage(`The application '${title}' might not have loaded correctly.`, 'error');
    }, 15000);

    iframeElement.onload = () => {
        clearTimeout(loadingTimeout);
        spinner.classList.add('hidden');
        iframeElement.classList.remove('hidden');
    };
    iframeElement.src = url;

    iframeWindowsContainer.appendChild(iframeWindow);
    activeIframeWindows.set(windowId, { element: iframeWindow, url, title, folderName, isMinimized: false });

    iframeWindow.addEventListener('mousedown', () => bringWindowToFront(iframeWindow));

    minimizeBtn.addEventListener('click', () => minimizeWindowToTaskbar(windowId));
    closeBtn.addEventListener('click', () => minimizeWindowToTaskbar(windowId));

    let isDragging = false;
    let offsetX, offsetY;

    titlebar.addEventListener('mousedown', (e) => {
        isDragging = true;
        offsetX = e.clientX - iframeWindow.getBoundingClientRect().left;
        offsetY = e.clientY - iframeWindow.getBoundingClientRect().top;
        iframeWindow.style.cursor = 'grabbing';
        iframeWindow.style.userSelect = 'none';
        bringWindowToFront(iframeWindow);
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        iframeWindow.style.left = `${e.clientX - offsetX}px`;
        iframeWindow.style.top = `${e.clientY - offsetY}px`;
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
        iframeWindow.style.cursor = 'grab';
        iframeWindow.style.userSelect = 'auto';
    });

    bringWindowToFront(iframeWindow);
    addTaskbarTab(windowId, title, folderName);
}

/**
 * Brings a specific iframe window to the front by updating its z-index.
 * @param {HTMLElement} windowElement - The iframe window element.
 */
function bringWindowToFront(windowElement) {
    highestZIndex++;
    windowElement.style.zIndex = highestZIndex;

    activeIframeWindows.forEach(win => win.element.classList.remove('active'));
    windowElement.classList.add('active');

    document.querySelectorAll('.taskbar-tab').forEach(tab => {
        if (tab.dataset.windowId === windowElement.id) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
}

/**
 * Minimizes an iframe window to the taskbar.
 * @param {string} windowId - The ID of the window to minimize.
 */
function minimizeWindowToTaskbar(windowId) {
    const windowInfo = activeIframeWindows.get(windowId);
    if (windowInfo) {
        windowInfo.element.classList.add('hidden');
        windowInfo.isMinimized = true;
        windowInfo.element.classList.remove('active');
        document.querySelectorAll('.taskbar-tab').forEach(tab => {
            if (tab.dataset.windowId === windowId) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });
    }
}

/**
 * Restores a minimized iframe window from the taskbar.
 * @param {string} windowId - The ID of the window to restore.
 */
function restoreWindowFromTaskbar(windowId) {
    const windowInfo = activeIframeWindows.get(windowId);
    if (windowInfo) {
        windowInfo.element.classList.remove('hidden');
        windowInfo.isMinimized = false;
        bringWindowToFront(windowInfo.element);
    }
}

/**
 * Closes an iframe window and removes its taskbar tab.
 * @param {string} windowId - The ID of the window to close.
 */
function closeIframeWindow(windowId) {
    const windowInfo = activeIframeWindows.get(windowId);
    if (windowInfo) {
        windowInfo.element.remove();
        activeIframeWindows.delete(windowId);
        removeTaskbarTab(windowId);
    }
}

/**
 * Updates the visibility of the taskbar and main content padding.
 */
function updateTaskbarVisibility() {
    if (enableTaskbarGlobally && openInIframeGlobally) {
        taskbar.classList.remove('hidden');
        document.body.classList.add('taskbar-enabled');
    } else {
        taskbar.classList.add('hidden');
        document.body.classList.remove('taskbar-enabled');
        activeIframeWindows.forEach((_, windowId) => closeIframeWindow(windowId));
    }
}

/**
 * Adds a tab to the taskbar for an opened iframe window.
 * @param {string} windowId - The ID of the associated iframe window.
 * @param {string} title - The title for the tab.
 * @param {string} folderName - The associated folder name (for potential icon).
 */
function addTaskbarTab(windowId, title, folderName) {
    if (!enableTaskbarGlobally || !openInIframeGlobally) return;

    const tab = document.createElement('div');
    tab.className = 'taskbar-tab';
    tab.dataset.windowId = windowId;
    tab.dataset.folderName = folderName;

    tab.innerHTML = `
        <i class="fas fa-desktop taskbar-tab-icon"></i>
        <span class="taskbar-tab-title">${title}</span>
        <button class="taskbar-tab-close-btn" title="Close Tab"><i class="fas fa-times"></i></button>
    `;

    tab.addEventListener('click', (event) => {
        if (event.target.closest('.taskbar-tab-close-btn')) {
            return;
        }
        restoreWindowFromTaskbar(windowId);
    });

    tab.querySelector('.taskbar-tab-close-btn').addEventListener('click', (event) => {
        event.stopPropagation();
        closeIframeWindow(windowId);
    });

    taskbarTabs.appendChild(tab);

    document.querySelectorAll('.taskbar-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
}

/**
 * Removes a tab from the taskbar.
 * @param {string} windowId - The ID of the associated iframe window.
 */
function removeTaskbarTab(windowId) {
    const tabToRemove = taskbarTabs.querySelector(`.taskbar-tab[data-window-id="${windowId}"]`);
    if (tabToRemove) {
        tabToRemove.remove();
    }
}

// Global Escape key listener
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        let activeWindowId = null;
        for (const [id, info] of activeIframeWindows.entries()) {
            if (info.element.classList.contains('active') && !info.isMinimized) {
                activeWindowId = id;
                break;
            }
        }
        if (activeWindowId) {
            minimizeWindowToTaskbar(activeWindowId);
        }
    }
});
