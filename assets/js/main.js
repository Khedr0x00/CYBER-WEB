// Global DOM elements
const folderCardsContainer = document.getElementById('folderCards');
const searchInput = document.getElementById('searchFolders');
const settingsBtn = document.getElementById('settingsBtn');
const stopAllAppsBtn = document.getElementById('stopAllAppsBtn');
const createProjectBtn = document.getElementById('createProjectBtn');
const mainContent = document.getElementById('mainContent');
// NEW: Edit URL button element
const editUrlBtn = document.getElementById('editUrlBtn');

// Global state variables, initialized from PHP in index.php
let allFolders = [];
let currentSearchTerm = '';
let showCoverImages = true; // Will be updated by fetchSettings
let enableCardAnimation = enableCardAnimationJs; // From PHP
let openInIframeGlobally = openInIframeJs; // From PHP
let showFullUrlGlobally = showFullUrlJs; // From PHP
let enableTaskbarGlobally = enableTaskbarJs; // From PHP

const renderedCards = new Map();

/**
 * Fetches settings from the server and updates global flags.
 * Then triggers fetching and displaying folders and updates taskbar visibility.
 */
async function fetchSettings() {
    try {
        const response = await fetch('index.php?action=get_settings');
        const settings = await response.json();
        showCoverImages = settings.showCover;
        enableCardAnimation = settings.enableCardAnimation;
        openInIframeGlobally = settings.openInIframe;
        showFullUrlGlobally = settings.showFullUrl;
        enableTaskbarGlobally = settings.enableTaskbar;
        updateTaskbarVisibility(); // Update taskbar display based on new setting
        fetchAndDisplayFolders();
    } catch (error) {
        console.error('Error fetching settings:', error);
        showMessage('Failed to load display settings. Using default.', 'error');
        fetchAndDisplayFolders();
    }
}

/**
 * Fetches the list of folders from the server and updates the display.
 */
async function fetchAndDisplayFolders() {
    try {
        const response = await fetch('index.php?action=list_folders');
        const folders = await response.json();
        allFolders = folders;
        filterAndRenderFolders();
    } catch (error) {
        console.error('Error fetching folders:', error);
        showMessage('Failed to load folders. Please check the server and PHP error logs.', 'error');
    }
}

/**
 * Creates a new folder card HTML element.
 * @param {object} folder - The folder data.
 * @returns {HTMLElement} The created card element.
 */
function createFolderCard(folder) {
    const card = document.createElement('div');
    card.className = 'folder-card';
    card.dataset.folderName = folder.name;

    const baseUrl = window.location.origin + window.location.pathname.substring(0, window.location.pathname.lastIndexOf('/') + 1);
    const imagePath = `${baseUrl}database/${folder.name}/cover.png`;

    if (showCoverImages) {
        card.style.backgroundImage = `url('${imagePath}')`;
        card.style.minHeight = '200px';
        card.style.padding = '0';
        card.classList.remove('no-cover');
    } else {
        card.style.backgroundImage = 'none';
        card.style.minHeight = 'auto';
        card.style.padding = '1.5rem';
        card.classList.add('no-cover');
    }

    if (!enableCardAnimation) {
        card.classList.add('no-animation');
    } else {
        card.classList.remove('no-animation');
    }

    const borderLightEffect = document.createElement('div');
    borderLightEffect.className = 'border-light-effect';

    if (enableCardAnimation) {
        const randomDuration = getRandomFloat(8, 15);
        const randomInitialAngle = getRandomInt(0, 360);
        const randomLightColor = getRandomColor();

        borderLightEffect.style.setProperty('--animation-duration', `${randomDuration}s`);
        borderLightEffect.style.setProperty('--initial-angle', `${randomInitialAngle}deg`);
        borderLightEffect.style.setProperty('--light-color', randomLightColor);
    }

    card.prepend(borderLightEffect);

    // Initial inner HTML with all icons and placeholders
    card.innerHTML += `
        <div class="card-overlay">
            <i class="fas fa-image upload-icon" data-folder="${folder.name}" title="Upload Cover Image"></i>
            ${folder.has_requirements_file ? `<i class="fas fa-download download-icon" data-folder="${folder.name}" title="Install Requirements"></i>` : ''}
            ${folder.has_install_script ? `<i class="fas fa-wrench install-script-icon" data-folder="${folder.name}" title="Run Install Script"></i>` : ''}
            <i class="fas fa-edit edit-icon" data-folder="${folder.name}" title="Edit Folder Content"></i>
            <i class="fas fa-trash-alt delete-icon" data-folder="${folder.name}" title="Delete Project"></i>
            ${folder.has_gui_py_file ? `<i class="fab fa-windows gui-icon" data-folder="${folder.name}" title="Open GUI.py"></i>` : ''}
            <i class="fas fa-terminal terminal-icon" data-folder="${folder.name}" title="Open Terminal Here"></i>
            <i class="fas fa-folder-open explorer-icon" data-folder="${folder.name}" title="Open Folder in Explorer"></i>
            ${folder.has_sqlmap_examples_file ? `<i class="fas fa-list-alt examples-icon" data-folder="${folder.name}" title="View SQLMap Examples"></i>` : ''}
            <i class="fas fa-sticky-note notes-icon" data-folder="${folder.name}" title="Edit Notes"></i>
            ${folder.has_screen_file ? `<i class="fas fa-expand screen-icon" data-folder="${folder.name}" title="Edit Screen Resolution"></i>` : ''}
            <div class="folder-name">${folder.name}</div>
            <div class="app-type"></div>
            ${folder.has_category_file && folder.category_text ? `<div class="category-display">${folder.category_text}</div>` : ''}
            <div class="tags-display"></div>
            <div class="status-indicator"></div>
            <div class="port-display"></div>
            <div class="full-url-display"></div>
            <div class="flex space-x-2 mt-auto card-buttons"></div>
        </div>
    `;
    return card;
}

/**
 * Updates the content of an existing folder card.
 * @param {HTMLElement} cardElement - The card element to update.
 * @param {object} folder - The updated folder data.
 */
function updateFolderCardContent(cardElement, folder) {
    const statusIndicator = cardElement.querySelector('.status-indicator');
    const portDisplay = cardElement.querySelector('.port-display');
    const categoryDisplay = cardElement.querySelector('.category-display');
    const tagsDisplay = cardElement.querySelector('.tags-display');
    const fullUrlDisplay = cardElement.querySelector('.full-url-display');
    const buttonsContainer = cardElement.querySelector('.card-buttons');
    const appTypeDisplay = cardElement.querySelector('.app-type');

    // Update the app type based on what files exist
    let appType = '';
    if (folder.has_python_app && folder.has_php_app) {
        appType = 'PYTHON & PHP';
    } else if (folder.has_python_app) {
        appType = 'PYTHON';
    } else if (folder.has_php_app) {
        appType = 'PHP';
    }
    appTypeDisplay.textContent = appType;


    // Update status and port for Python apps
    if (folder.has_python_app) {
        const statusClass = folder.is_running ? 'status-running' : 'status-stopped';
        const statusText = folder.is_running ? 'Running' : 'Stopped';
        statusIndicator.className = `status-indicator ${statusClass}`;
        statusIndicator.textContent = statusText;
        portDisplay.textContent = folder.port ? `Port: ${folder.port}` : '';
        portDisplay.style.display = (folder.port) ? 'block' : 'none';
    } else {
        statusIndicator.style.display = 'none';
        portDisplay.style.display = 'none';
    }


    if (categoryDisplay) {
        categoryDisplay.textContent = folder.category_text || '';
        categoryDisplay.style.display = folder.has_category_file && folder.category_text ? 'block' : 'none';
    }

    tagsDisplay.innerHTML = '';
    if (folder.has_tags_file && folder.tags_text) {
        const tags = folder.tags_text.split(',').map(tag => tag.trim()).filter(tag => tag !== '');
        tags.forEach(tag => {
            const tagSpan = document.createElement('span');
            tagSpan.className = 'tag-item';
            tagSpan.textContent = tag;
            tagsDisplay.appendChild(tagSpan);
        });
        tagsDisplay.style.display = 'flex';
    } else {
        tagsDisplay.style.display = 'none';
    }

    buttonsContainer.innerHTML = '';
    fullUrlDisplay.innerHTML = '';


    // Add buttons based on what files are present
    if (folder.has_python_app) {
        const startBtn = document.createElement('button');
        startBtn.className = 'btn btn-start';
        startBtn.textContent = 'Start';
        startBtn.disabled = folder.is_running;
        startBtn.onclick = (event) => startApp(folder.name, event.target);
        buttonsContainer.appendChild(startBtn);

        const stopBtn = document.createElement('button');
        stopBtn.className = 'btn btn-stop';
        stopBtn.textContent = 'Stop';
        stopBtn.disabled = !folder.is_running;
        stopBtn.onclick = () => stopApp(folder.name);
        buttonsContainer.appendChild(stopBtn);

        if (folder.is_running && folder.full_url) {
            const openPythonUrlBtn = document.createElement('button');
            openPythonUrlBtn.className = 'btn btn-open-url';
            openPythonUrlBtn.textContent = 'Open App';
            openPythonUrlBtn.onclick = () => handleOpenUrl(folder.full_url, folder.name, 'python', folder.screen_resolution ? parseInt(folder.screen_resolution.split('x')[0], 10) : null, folder.screen_resolution ? parseInt(folder.screen_resolution.split('x')[1], 10) : null);
            buttonsContainer.appendChild(openPythonUrlBtn);
        }
    }

    if (folder.has_php_app) {
        const openPhpUrlBtn = document.createElement('button');
        openPhpUrlBtn.className = 'btn btn-web';
        openPhpUrlBtn.textContent = 'Web';
        openPhpUrlBtn.onclick = () => handleOpenUrl(folder.php_url, folder.name + ' (Web)', 'php', folder.screen_resolution ? parseInt(folder.screen_resolution.split('x')[0], 10) : null, folder.screen_resolution ? parseInt(folder.screen_resolution.split('x')[1], 10) : null);
        buttonsContainer.appendChild(openPhpUrlBtn);
    }

    // Handle full URL display for Python apps when enabled
    if (folder.has_python_app && showFullUrlGlobally && folder.is_running && folder.full_url) {
        fullUrlDisplay.textContent = folder.full_url;
        fullUrlDisplay.style.display = 'block';
        fullUrlDisplay.onclick = () => handleOpenUrl(folder.full_url, folder.name, 'python', folder.screen_resolution ? parseInt(folder.screen_resolution.split('x')[0], 10) : null, folder.screen_resolution ? parseInt(folder.screen_resolution.split('x')[1], 10) : null);
    } else {
        fullUrlDisplay.style.display = 'none';
    }


    // Icons logic (remains the same)
    const downloadIcon = cardElement.querySelector('.download-icon');
    const installScriptIcon = cardElement.querySelector('.install-script-icon');
    const uploadIcon = cardElement.querySelector('.upload-icon');
    const editIcon = cardElement.querySelector('.edit-icon');
    const deleteIcon = cardElement.querySelector('.delete-icon');
    const guiIcon = cardElement.querySelector('.gui-icon');
    const terminalIcon = cardElement.querySelector('.terminal-icon');
    const explorerIcon = cardElement.querySelector('.explorer-icon');
    const examplesIcon = cardElement.querySelector('.examples-icon');
    const notesIcon = cardElement.querySelector('.notes-icon');
    const screenIcon = cardElement.querySelector('.screen-icon');

    if (downloadIcon) {
        downloadIcon.style.display = folder.has_requirements_file ? 'block' : 'none';
        downloadIcon.onclick = (event) => {
            event.stopPropagation();
            installRequirements(folder.name, event.target);
        };
    }
    if (installScriptIcon) {
        installScriptIcon.style.display = folder.has_install_script ? 'block' : 'none';
        installScriptIcon.onclick = (event) => {
            event.stopPropagation();
            runInstallScript(folder.name, event.target);
        };
    }
    if (uploadIcon) {
        uploadIcon.onclick = (event) => {
            event.stopPropagation();
            openImageUploadModal(folder.name);
        };
    }
    if (editIcon) {
        editIcon.onclick = (event) => {
            event.stopPropagation();
            openEditFolderModal(folder.name);
        };
    }
    if (deleteIcon) {
        deleteIcon.onclick = (event) => {
            event.stopPropagation();
            showConfirmationDialog(`Are you sure you want to delete the project '${folder.name}'? This action cannot be undone.`, () => {
                deleteProject(folder.name);
            });
        };
    }
    if (guiIcon) {
        guiIcon.style.display = folder.has_gui_py_file ? 'block' : 'none';
        guiIcon.onclick = (event) => {
            event.stopPropagation();
            openGuiPy(folder.name);
        };
    }
    if (terminalIcon) {
        terminalIcon.onclick = (event) => {
            event.stopPropagation();
            openTerminal(folder.name);
        };
    }
    if (explorerIcon) {
        explorerIcon.onclick = (event) => {
            event.stopPropagation();
            openExplorer(folder.name);
        };
    }
    if (examplesIcon) {
        examplesIcon.style.display = folder.has_sqlmap_examples_file ? 'block' : 'none';
        examplesIcon.onclick = (event) => {
            event.stopPropagation();
            openSqlmapExamplesModal(folder.name);
        };
    }
    if (notesIcon) {
        notesIcon.style.display = 'block';
        notesIcon.onclick = (event) => {
            event.stopPropagation();
            openNotesModal(folder.name);
        };
    }
    if (screenIcon) {
        screenIcon.style.display = folder.has_screen_file ? 'block' : 'none';
        screenIcon.onclick = (event) => {
            event.stopPropagation();
            openScreenModal(folder.name);
        };
    }
}

/**
 * Renders the given list of folders into the display.
 * Handles adding new cards, updating existing ones, and removing old ones.
 * @param {Array<object>} foldersToRender - An array of folder data to render.
 */
function renderFolders(foldersToRender) {
    const currentFolderNames = new Set(foldersToRender.map(f => f.name));
    const existingCardNames = new Set(renderedCards.keys());

    existingCardNames.forEach(name => {
        if (!currentFolderNames.has(name)) {
            const cardToRemove = renderedCards.get(name);
            if (cardToRemove) {
                cardToRemove.remove();
                renderedCards.delete(name);
            }
        }
    });

    foldersToRender.forEach(folder => {
        let cardElement = renderedCards.get(folder.name);
        if (!cardElement) {
            cardElement = createFolderCard(folder);
            folderCardsContainer.appendChild(cardElement);
            renderedCards.set(folder.name, cardElement);
        }
        updateFolderCardContent(cardElement, folder);

        const baseUrl = window.location.origin + window.location.pathname.substring(0, window.location.pathname.lastIndexOf('/') + 1);
        const imagePath = `${baseUrl}database/${folder.name}/cover.png?t=${new Date().getTime()}`;
        
        if (showCoverImages) {
            cardElement.style.backgroundImage = `url('${imagePath}')`;
            cardElement.style.minHeight = '200px';
            cardElement.style.padding = '0';
            cardElement.classList.remove('no-cover');
        } else {
            cardElement.style.backgroundImage = 'none';
            cardElement.style.minHeight = 'auto';
            cardElement.style.padding = '1.5rem';
            cardElement.classList.add('no-cover');
        }

        const borderLightEffect = cardElement.querySelector('.border-light-effect');
        if (borderLightEffect) {
            if (!enableCardAnimation) {
                cardElement.classList.add('no-animation');
                borderLightEffect.style.animation = 'none';
                borderLightEffect.style.background = 'none';
            } else {
                cardElement.classList.remove('no-animation');
                const randomDuration = getRandomFloat(8, 15);
                const randomInitialAngle = getRandomInt(0, 360);
                const randomLightColor = getRandomColor();
                borderLightEffect.style.setProperty('--animation-duration', `${randomDuration}s`);
                borderLightEffect.style.setProperty('--initial-angle', `${randomInitialAngle}deg`);
                borderLightEffect.style.setProperty('--light-color', randomLightColor);
                borderLightEffect.style.animation = `border-worm-walk ${randomDuration}s linear infinite`;
            }
        }
    });

    if (foldersToRender.length === 0 && renderedCards.size === 0) {
        folderCardsContainer.innerHTML = '<p class="text-center text-gray-400 col-span-full">No applications found or matching your search.</p>';
    }
}

/**
 * Sends a request to start a Python application.
 * @param {string} folderName - The name of the folder containing the app.
 * @param {HTMLElement} buttonElement - The button element that triggered the action.
 */
async function startApp(folderName, buttonElement) {
    buttonElement.disabled = true;
    showMessage(`Starting ${folderName}...`, 'info');

    try {
        const response = await fetch('index.php?action=start_app', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_name: folderName })
        });
        const result = await response.json();
        if (response.ok) {
            showMessage(result.message);
            // Re-fetch to update the card with the new running state and URL
            fetchAndDisplayFolders();
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error starting app:', error);
        showMessage('An error occurred while trying to start the app.', 'error');
    } finally {
        // Button state will be updated by the fetchAndDisplayFolders polling
    }
}

/**
 * Sends a request to stop a Python application.
 * @param {string} folderName - The name of the folder containing the app.
 */
async function stopApp(folderName) {
    try {
        const response = await fetch('index.php?action=stop_app', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_name: folderName })
        });
        const result = await response.json();
        if (response.ok) {
            showMessage(result.message);
            // Re-fetch to update the card with the new stopped state
            fetchAndDisplayFolders();
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error stopping app:', error);
        showMessage('An error occurred while trying to stop the app.', 'error');
    }
}

/**
 * Sends a request to stop all running Python applications.
 */
async function stopAllApps() {
    showMessage('Attempting to stop all running Python applications...', 'info');

    try {
        const response = await fetch('index.php?action=stop_all_apps', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();
        if (response.ok) {
            showMessage(result.message);
            fetchAndDisplayFolders();
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error stopping all apps:', error);
        showMessage('An error occurred while trying to stop all apps.', 'error');
    }
}

/**
 * Sends a request to install requirements for a Python application.
 * @param {string} folderName - The name of the folder containing the app.
 * @param {HTMLElement} iconElement - The icon element to animate during installation.
 */
async function installRequirements(folderName, iconElement) {
    iconElement.classList.add('installing');
    iconElement.style.pointerEvents = 'none';

    showMessage(`Installing requirements for ${folderName}...`, 'info');

    try {
        const response = await fetch('index.php?action=install_requirements', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_name: folderName })
        });
        const result = await response.json();
        if (response.ok && result.status === 'success') {
            showMessage(result.message);
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error installing requirements:', error);
        showMessage('An error occurred while trying to install requirements.', 'error');
    } finally {
        iconElement.classList.remove('installing');
        iconElement.style.pointerEvents = 'auto';
    }
}

/**
 * Sends a request to run the install.sh script for an application.
 * @param {string} folderName - The name of the folder containing the app.
 * @param {HTMLElement} iconElement - The icon element to animate during script execution.
 */
async function runInstallScript(folderName, iconElement) {
    showMessage(`Running install.sh for ${folderName}... This may take a moment and can make significant changes.`, 'info');

    iconElement.classList.add('running');
    iconElement.style.pointerEvents = 'none';

    try {
        const response = await fetch('index.php?action=run_install_script', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_name: folderName })
        });
        const result = await response.json();
        if (response.ok && result.status === 'success') {
            showMessage(result.message);
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error running install.sh:', error);
        showMessage('An error occurred while trying to run install.sh.', 'error');
    } finally {
        iconElement.classList.remove('running');
        iconElement.style.pointerEvents = 'auto';
    }
}

/**
 * Filters the `allFolders` array based on the current search term
 * and triggers a re-render of the filtered folders.
 */
function filterAndRenderFolders() {
    const searchTerm = currentSearchTerm.toLowerCase();
    const filteredFolders = allFolders.filter(folder =>
        folder.name.toLowerCase().includes(searchTerm) ||
        (folder.category_text && folder.category_text.toLowerCase().includes(searchTerm)) ||
        (folder.tags_text && folder.tags_text.toLowerCase().includes(searchTerm))
    );
    renderFolders(filteredFolders);
}

/**
 * Sends a request to delete a project.
 * @param {string} folderName - The name of the folder to delete.
 */
async function deleteProject(folderName) {
    showMessage(`Deleting project '${folderName}'...`, 'info');

    try {
        const response = await fetch('index.php?action=delete_project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_name: folderName })
        });
        const result = await response.json();

        if (response.ok && result.status === 'success') {
            showMessage(result.message);
            fetchAndDisplayFolders();
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error deleting project:', error);
        showMessage('An error occurred while trying to delete the project.', 'error');
    }
}

/**
 * Sends a request to open GUI.py for a Python application.
 * @param {string} folderName - The name of the folder containing the app.
 */
async function openGuiPy(folderName) {
    showMessage(`Attempting to open GUI.py for ${folderName}...`, 'info');
    try {
        const response = await fetch('index.php?action=open_gui_py', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_name: folderName })
        });
        const result = await response.json();
        if (response.ok && result.status === 'success') {
            showMessage(result.message);
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error opening GUI.py:', error);
        showMessage('An error occurred while trying to open GUI.py.', 'error');
    }
}

/**
 * Sends a request to open a terminal in the specified folder.
 * @param {string} folderName - The name of the folder.
 */
async function openTerminal(folderName) {
    showMessage(`Opening terminal for ${folderName}...`, 'info');
    try {
        const response = await fetch('index.php?action=open_terminal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_name: folderName })
        });
        const result = await response.json();
        if (response.ok && result.status === 'success') {
            showMessage(result.message);
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error opening terminal:', error);
        showMessage('An error occurred while trying to open the terminal.', 'error');
    }
}

/**
 * Sends a request to open the folder in the file explorer.
 * @param {string} folderName - The name of the folder.
 */
async function openExplorer(folderName) {
    showMessage(`Opening folder in explorer for ${folderName}...`, 'info');
    try {
        const response = await fetch('index.php?action=open_explorer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_name: folderName })
        });
        const result = await response.json();
        if (response.ok && result.status === 'success') {
            showMessage(result.message);
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error opening explorer:', error);
        showMessage('An error occurred while trying to open the folder in explorer.', 'error');
    }
}

/**
 * Opens a URL in a new iframe window with custom resolution if provided.
 * @param {string} url - The URL to open.
 * @param {string} title - The title for the window/tab.
 * @param {string} folderType - 'python' or 'php'
 * @param {number|null} [width=null] - Optional width for the iframe window.
 * @param {number|null} [height=null] - Optional height for the iframe window.
 */
function openScreenWithResolution(url, title, folderType, width = null, height = null) {
    // Call the updated handleOpenUrl with width and height
    handleOpenUrl(url, title, folderType, width, height);
}

// Event Listeners for main elements
searchInput.addEventListener('input', (event) => {
    currentSearchTerm = event.target.value;
    filterAndRenderFolders();
});

stopAllAppsBtn.addEventListener('click', stopAllApps);
createProjectBtn.addEventListener('click', openCreateProjectModal);
// NEW: Event listener for the "Edit URL" button
editUrlBtn.addEventListener('click', () => {
    window.open('edit_base_url.php', '_blank');
});

// Listen for messages from child iframes (like edit_base_url.php)
window.addEventListener('message', (event) => {
    if (event.data.type === 'reloadLauncher') {
        fetchAndDisplayFolders();
        showMessage('Launcher has been refreshed to apply URL changes.');
    }
});

// Initial fetch and polling for updates
document.addEventListener('DOMContentLoaded', fetchSettings);
setInterval(fetchAndDisplayFolders, 5000);
