// Modal DOM elements (declared in index.php, accessible globally after script load)
const imageUploadModal = document.getElementById('imageUploadModal');
const closeModalBtn = document.getElementById('closeModalBtn');
const modalFolderNameSpan = document.getElementById('modalFolderName');
const imageInput = document.getElementById('imageInput');
const imagePreview = document.getElementById('imagePreview');
const imagePreviewPlaceholder = document.getElementById('imagePreviewPlaceholder');
const uploadImageBtn = document.getElementById('uploadImageBtn');

const settingsModal = document.getElementById('settingsModal');
const closeSettingsModalBtn = document.getElementById('closeSettingsModalBtn');
const showCoverCheckbox = document.getElementById('showCoverCheckbox');
const enableCardAnimationCheckbox = document.getElementById('enableCardAnimationCheckbox');
const openInIframeCheckbox = document.getElementById('openInIframeCheckbox');
const showFullUrlCheckbox = document.getElementById('showFullUrlCheckbox');
const enableTaskbarCheckbox = document.getElementById('enableTaskbarCheckbox');
// Removed: const baseUrlInput = document.getElementById('baseUrlInput');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');
const backToLauncherBtn = document.getElementById('backToLauncherBtn');

const createProjectModal = document.getElementById('createProjectModal');
const closeCreateProjectModalBtn = document.getElementById('closeCreateProjectModalBtn');
const projectNameInput = document.getElementById('projectNameInput');
const appPyCodeTextarea = document.getElementById('appPyCodeTextarea');
const indexHtmlCodeTextarea = document.getElementById('indexHtmlCodeTextarea');
const categoryInput = document.getElementById('categoryInput');
const requirementsTxtTextarea = document.getElementById('requirementsTxtTextarea');
const installScriptTextarea = document.getElementById('installScriptTextarea');
const tagsInput = document.getElementById('tagsInput');
const guiPyCodeTextarea = document.getElementById('guiPyCodeTextarea');
const sqlmapExamplesTextarea = document.getElementById('sqlmapExamplesTextarea');
const notesTextarea = document.getElementById('notesTextarea');
const screenTxtTextarea = document.getElementById('screenTxtTextarea'); // screen.txt textarea for create project
const saveProjectBtn = document.getElementById('saveProjectBtn');
const createImageInput = document.getElementById('createImageInput');
const createImagePreview = document.getElementById('createImagePreview');
const createImagePreviewPlaceholder = document.getElementById('createImagePreviewPlaceholder');

const editFolderModal = document.getElementById('editFolderModal');
const closeEditFolderModalBtn = document.getElementById('closeEditFolderModalBtn');
const editModalFolderNameSpan = document.getElementById('editModalFolderName');
const editAppPyCodeTextarea = document.getElementById('editAppPyCodeTextarea');
const editIndexHtmlCodeTextarea = document.getElementById('editIndexHtmlCodeTextarea');
const editRequirementsTxtTextarea = document.getElementById('editRequirementsTxtTextarea');
const editInstallScriptTextarea = document.getElementById('editInstallScriptTextarea');
const editCategoryTxtInput = document.getElementById('editCategoryTxtInput');
const editTagsTxtInput = document.getElementById('editTagsTxtInput');
const editGuiPyCodeTextarea = document.getElementById('editGuiPyCodeTextarea');
const editSqlmapExamplesTextarea = document.getElementById('editSqlmapExamplesTextarea');
const editNotesTextarea = document.getElementById('editNotesTextarea');
const editScreenTxtInput = document.getElementById('editScreenTxtInput'); // edit screen.txt input for edit folder
const saveFolderContentBtn = document.getElementById('saveFolderContentBtn');
const editImageInput = document.getElementById('editImageInput');
const editImagePreview = document.getElementById('editImagePreview');
const editImagePreviewPlaceholder = document.getElementById('editImagePreviewPlaceholder');

const sqlmapExamplesModal = document.getElementById('sqlmapExamplesModal');
const closeSqlmapExamplesModalBtn = document.getElementById('closeSqlmapExamplesModalBtn');
const sqlmapExamplesFolderNameSpan = document.getElementById('sqlmapExamplesFolderName');
const sqlmapExamplesList = document.getElementById('sqlmapExamplesList');
const sqlmapExamplesSearchInput = document.getElementById('sqlmapExamplesSearch');
const backToLauncherFromExamplesBtn = document.getElementById('backToLauncherFromExamplesBtn');

const notesModal = document.getElementById('notesModal');
const closeNotesModalBtn = document.getElementById('closeNotesModalBtn');
const notesModalFolderNameSpan = document.getElementById('notesModalFolderName');
const notesContentTextarea = document.getElementById('notesContentTextarea');
const saveNotesBtn = document.getElementById('saveNotesBtn');
const cancelNotesBtn = document.getElementById('cancelNotesBtn');

// NEW: Screen Modal DOM elements
const screenModal = document.getElementById('screenModal');
const closeScreenModalBtn = document.getElementById('closeScreenModalBtn');
const screenModalFolderNameSpan = document.getElementById('screenModalFolderName');
const screenContentTextarea = document.getElementById('screenContentTextarea');
const saveScreenBtn = document.getElementById('saveScreenBtn');
const cancelScreenBtn = document.getElementById('cancelScreenBtn');


// Internal state for modals
let currentFolderForUpload = null;
let currentFolderForEdit = null;
let currentFolderForSqlmapExamples = null;
let currentSqlmapExamples = [];
let currentFolderForNotes = null;
let currentFolderForScreen = null; // NEW: State for screen modal


// Image Upload Modal Functions
function openImageUploadModal(folderName) {
    currentFolderForUpload = folderName;
    modalFolderNameSpan.textContent = folderName;
    imageInput.value = '';
    imagePreview.src = '#';
    imagePreview.classList.add('hidden');
    imagePreviewPlaceholder.classList.remove('hidden');
    imageUploadModal.classList.remove('hidden');
    imageUploadModal.classList.add('show');
}

function closeImageUploadModal() {
    imageUploadModal.classList.remove('show');
    imageUploadModal.classList.add('hidden');
    currentFolderForUpload = null;
}

function handleImageSelect(event, previewElement, placeholderElement) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            previewElement.src = e.target.result;
            previewElement.classList.remove('hidden');
            placeholderElement.classList.add('hidden');
        };
        reader.readAsDataURL(file);
    } else {
        previewElement.src = '#';
        previewElement.classList.add('hidden');
        placeholderElement.classList.remove('hidden');
    }
}

async function uploadImageForProject(folderName, fileInput, buttonElement) {
    const file = fileInput.files[0];
    if (!file) {
        return true;
    }

    showMessage(`Uploading cover image for ${folderName}...`, 'info');
    if (buttonElement) {
        buttonElement.disabled = true;
    }

    const formData = new FormData();
    formData.append('folder_name', folderName);
    formData.append('cover_image', file);

    try {
        const response = await fetch('index.php?action=upload_cover_image', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        if (response.ok && result.status === 'success') {
            showMessage(result.message);
            return true;
        } else {
            showMessage(result.message, 'error');
            return false;
        }
    } catch (error) {
        console.error('Error uploading image:', error);
        showMessage('An error occurred while trying to upload the image.', 'error');
        return false;
    } finally {
        if (buttonElement) {
            buttonElement.disabled = false;
        }
    }
}

// Settings Modal Functions
function openSettingsModal() {
    loadSettingsForModal();
    settingsModal.classList.remove('hidden');
    settingsModal.classList.add('show');
}

function closeSettingsModal() {
    settingsModal.classList.remove('show');
    settingsModal.classList.add('hidden');
}

async function loadSettingsForModal() {
    try {
        const response = await fetch('index.php?action=get_settings');
        const settings = await response.json();
        showCoverCheckbox.checked = settings.showCover;
        enableCardAnimationCheckbox.checked = settings.enableCardAnimation;
        openInIframeCheckbox.checked = settings.openInIframe;
        showFullUrlCheckbox.checked = settings.showFullUrl;
        enableTaskbarCheckbox.checked = settings.enableTaskbar;
    } catch (error) {
        console.error('Error loading settings for modal:', error);
        showMessage('Failed to load display settings. Using default.', 'error');
    }
}

async function saveSettingsFromModal() {
    const settings = {
        showCover: showCoverCheckbox.checked,
        enableCardAnimation: enableCardAnimationCheckbox.checked,
        openInIframe: openInIframeCheckbox.checked,
        showFullUrl: showFullUrlCheckbox.checked,
        enableTaskbar: enableTaskbarCheckbox.checked,
    };
    try {
        const response = await fetch('index.php?action=save_settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        const result = await response.json();
        if (response.ok) {
            showMessage(result.message);
            showCoverImages = settings.showCover;
            enableCardAnimation = settings.enableCardAnimation;
            openInIframeGlobally = settings.openInIframe;
            showFullUrlGlobally = settings.showFullUrl;
            enableTaskbarGlobally = settings.enableTaskbar;
            // No need to update baseUrl here, as it's handled by the new button
            updateTaskbarVisibility();
            filterAndRenderFolders();
            closeSettingsModal();
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        showMessage('An error occurred while trying to save settings.', 'error');
    }
}

// Create Project Modal Functions
function openCreateProjectModal() {
    projectNameInput.value = '';
    appPyCodeTextarea.value = '';
    indexHtmlCodeTextarea.value = '';
    categoryInput.value = '';
    requirementsTxtTextarea.value = '';
    installScriptTextarea.value = '';
    tagsInput.value = '';
    guiPyCodeTextarea.value = '';
    sqlmapExamplesTextarea.value = '';
    notesTextarea.value = '';
    screenTxtTextarea.value = ''; // Clear screen.txt input
    createImageInput.value = '';
    createImagePreview.src = '#';
    createImagePreview.classList.add('hidden');
    createImagePreviewPlaceholder.classList.remove('hidden');

    createProjectModal.classList.remove('hidden');
    createProjectModal.classList.add('show');
}

function closeCreateProjectModal() {
    createProjectModal.classList.remove('show');
    createProjectModal.classList.add('hidden');
}

async function saveProject() {
    const projectName = projectNameInput.value.trim();
    const appPyCode = appPyCodeTextarea.value;
    const indexHtmlCode = indexHtmlCodeTextarea.value;
    const categoryName = categoryInput.value.trim();
    const requirementsTxtCode = requirementsTxtTextarea.value;
    const installScriptCode = installScriptTextarea.value;
    const tagsCode = tagsInput.value.trim();
    const guiPyCode = guiPyCodeTextarea.value;
    const sqlmapExamplesCode = sqlmapExamplesTextarea.value;
    const notesCode = notesTextarea.value;
    const screenTxtCode = screenTxtTextarea.value.trim(); // Get screen.txt content

    if (!projectName) {
        showMessage('Project name is required.', 'error');
        return;
    }

    saveProjectBtn.disabled = true;
    showMessage(`Creating project '${projectName}'...`, 'info');

    try {
        const response = await fetch('index.php?action=create_project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_name: projectName,
                app_code: appPyCode,
                html_code: indexHtmlCode,
                category_name: categoryName,
                requirements_code: requirementsTxtCode,
                install_script_code: installScriptCode,
                tags_code: tagsCode,
                gui_py_code: guiPyCode,
                sqlmap_examples_code: sqlmapExamplesCode,
                notes_code: notesCode,
                screen_txt_code: screenTxtCode // Send screen.txt content
            })
        });
        const result = await response.json();

        if (response.ok && result.status === 'success') {
            showMessage(result.message);
            const uploadSuccess = await uploadImageForProject(projectName, createImageInput, saveProjectBtn);
            if (uploadSuccess) {
                closeCreateProjectModal();
                fetchAndDisplayFolders();
            } else {
                closeCreateProjectModal();
                fetchAndDisplayFolders();
            }
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error creating project:', error);
        showMessage('An error occurred while trying to create the project.', 'error');
    } finally {
        saveProjectBtn.disabled = false;
    }
}

// Edit Folder Modal Functions
async function openEditFolderModal(folderName) {
    currentFolderForEdit = folderName;
    editModalFolderNameSpan.textContent = folderName;

    editAppPyCodeTextarea.value = 'Loading...';
    editIndexHtmlCodeTextarea.value = 'Loading...';
    editRequirementsTxtTextarea.value = 'Loading...';
    editInstallScriptTextarea.value = 'Loading...';
    editCategoryTxtInput.value = 'Loading...';
    editTagsTxtInput.value = 'Loading...';
    editGuiPyCodeTextarea.value = 'Loading...';
    editSqlmapExamplesTextarea.value = 'Loading...';
    editNotesTextarea.value = 'Loading...';
    editScreenTxtInput.value = 'Loading...'; // Loading for screen.txt
    saveFolderContentBtn.disabled = true;

    editImageInput.value = '';
    editImagePreview.src = '#';
    editImagePreview.classList.add('hidden');
    editImagePreviewPlaceholder.classList.remove('hidden');

    try {
        const response = await fetch(`index.php?action=get_folder_content&folder_name=${encodeURIComponent(folderName)}`);
        const result = await response.json();

        if (result.status === 'success') {
            editAppPyCodeTextarea.value = result.content.app_py;
            editIndexHtmlCodeTextarea.value = result.content.index_html;
            editRequirementsTxtTextarea.value = result.content.requirements_txt;
            editInstallScriptTextarea.value = result.content.install_sh;
            editCategoryTxtInput.value = result.content.category_txt;
            editTagsTxtInput.value = result.content.tags_txt;
            editGuiPyCodeTextarea.value = result.content.gui_py;
            editSqlmapExamplesTextarea.value = result.content.sqlmap_examples_txt;
            editNotesTextarea.value = result.content.notes_txt;
            editScreenTxtInput.value = result.content.screen_txt; // Populate screen.txt

            const baseUrl = window.location.origin + window.location.pathname.substring(0, window.location.pathname.lastIndexOf('/') + 1);
            const imagePath = `${baseUrl}database/${folderName}/cover.png?t=${new Date().getTime()}`;
            
            const img = new Image();
            img.onload = () => {
                editImagePreview.src = imagePath;
                editImagePreview.classList.remove('hidden');
                editImagePreviewPlaceholder.classList.add('hidden');
            };
            img.onerror = () => {
                editImagePreview.src = '#';
                editImagePreview.classList.add('hidden');
                editImagePreviewPlaceholder.classList.remove('hidden');
            };
            img.src = imagePath;
        } else {
            showMessage(result.message, 'error');
            editAppPyCodeTextarea.value = '';
            editIndexHtmlCodeTextarea.value = '';
            editRequirementsTxtTextarea.value = '';
            editInstallScriptTextarea.value = '';
            editCategoryTxtInput.value = '';
            editTagsTxtInput.value = '';
            editGuiPyCodeTextarea.value = '';
            editSqlmapExamplesTextarea.value = '';
            editNotesTextarea.value = '';
            editScreenTxtInput.value = ''; // Clear screen.txt
        }
    } catch (error) {
        console.error('Error fetching folder content:', error);
        showMessage('An error occurred while loading folder content.', 'error');
        editAppPyCodeTextarea.value = '';
        editIndexHtmlCodeTextarea.value = '';
        editRequirementsTxtTextarea.value = '';
        editInstallScriptTextarea.value = '';
        editCategoryTxtInput.value = '';
        editTagsTxtInput.value = '';
        editGuiPyCodeTextarea.value = '';
        editSqlmapExamplesTextarea.value = '';
        editNotesTextarea.value = '';
        editScreenTxtInput.value = ''; // Clear screen.txt
    } finally {
        saveFolderContentBtn.disabled = false;
        editFolderModal.classList.remove('hidden');
        editFolderModal.classList.add('show');
    }
}

function closeEditFolderModal() {
    editFolderModal.classList.remove('show');
    editFolderModal.classList.add('hidden');
    currentFolderForEdit = null;
}

async function saveFolderContent() {
    if (!currentFolderForEdit) {
        showMessage('No folder selected for editing.', 'error');
        return;
    }

    saveFolderContentBtn.disabled = true;
    showMessage(`Saving changes for ${currentFolderForEdit}...`, 'info');

    const dataToSave = {
        folder_name: currentFolderForEdit,
        app_py: editAppPyCodeTextarea.value,
        index_html: editIndexHtmlCodeTextarea.value,
        requirements_txt: editRequirementsTxtTextarea.value,
        install_sh: editInstallScriptTextarea.value,
        category_txt: editCategoryTxtInput.value,
        tags_txt: editTagsTxtInput.value,
        gui_py: editGuiPyCodeTextarea.value,
        sqlmap_examples_txt: editSqlmapExamplesTextarea.value,
        notes_txt: editNotesTextarea.value,
        screen_txt: editScreenTxtInput.value.trim() // Send screen.txt content
    };

    try {
        const response = await fetch('index.php?action=save_folder_content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dataToSave)
        });
        const result = await response.json();

        if (response.ok && result.status === 'success') {
            showMessage(result.message);
            const uploadSuccess = await uploadImageForProject(currentFolderForEdit, editImageInput, saveFolderContentBtn);
            if (uploadSuccess) {
                closeEditFolderModal();
                fetchAndDisplayFolders();
            } else {
                closeEditFolderModal();
                fetchAndDisplayFolders();
            }
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error saving folder content:', error);
        showMessage('An error occurred while trying to save folder content.', 'error');
    } finally {
        saveFolderContentBtn.disabled = false;
    }
}

// SQLMap Examples Modal Functions
async function openSqlmapExamplesModal(folderName) {
    currentFolderForSqlmapExamples = folderName;
    // Dynamically set the folder name in the modal title
    sqlmapExamplesFolderNameSpan.textContent = folderName; 
    sqlmapExamplesList.innerHTML = '<p class="text-center text-gray-400">Loading examples...</p>';
    sqlmapExamplesSearchInput.value = '';

    sqlmapExamplesModal.classList.remove('hidden');
    sqlmapExamplesModal.classList.add('show');

    try {
        const response = await fetch(`index.php?action=get_sqlmap_examples&folder_name=${encodeURIComponent(folderName)}`);
        const result = await response.json();

        if (result.status === 'success') {
            currentSqlmapExamples = result.examples;
            filterAndDisplaySqlmapExamples();
        } else {
            sqlmapExamplesList.innerHTML = `<p class="text-center text-red-400">${result.message}</p>`;
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error fetching SQLMap examples:', error);
        sqlmapExamplesList.innerHTML = '<p class="text-center text-red-400">An error occurred while loading SQLMap examples.</p>';
        showMessage('An error occurred while loading SQLMap examples.', 'error');
    }
}

function closeSqlmapExamplesModal() {
    sqlmapExamplesModal.classList.remove('show');
    sqlmapExamplesModal.classList.add('hidden');
    currentFolderForSqlmapExamples = null;
    currentSqlmapExamples = [];
}

function filterAndDisplaySqlmapExamples() {
    const searchTerm = sqlmapExamplesSearchInput.value.toLowerCase();
    const filteredExamples = currentSqlmapExamples.filter(example =>
        example.name.toLowerCase().includes(searchTerm) ||
        example.description.toLowerCase().includes(searchTerm) ||
        JSON.stringify(example.options).toLowerCase().includes(searchTerm) ||
        example.example_output.toLowerCase().includes(searchTerm)
    );
    displaySqlmapExamples(filteredExamples);
}

function displaySqlmapExamples(examples) {
    sqlmapExamplesList.innerHTML = '';
    if (examples.length === 0) {
        sqlmapExamplesList.innerHTML = '<p class="text-center text-gray-400">No SQLMap examples found matching your search.</p>';
        return;
    }

    examples.forEach(example => {
        const exampleDiv = document.createElement('div');
        exampleDiv.className = 'sqlmap-example-item';
        exampleDiv.innerHTML = `
            <h3>${example.name}</h3>
            <p class="example-description">${example.description}</p>
            <div class="sqlmap-example-buttons">
                <button class="btn btn-notes" data-action="notes" data-name="${example.name}" data-description="${example.description}">Notes</button>
                <button class="btn btn-output" data-action="output" data-name="${example.name}" data-output='${example.example_output}'>Output</button>
                <button class="btn btn-terminal" data-action="terminal" data-name="${example.name}" data-options='${JSON.stringify(example.options)}'>Terminal/CMD Command</button>
            </div>
        `;
        sqlmapExamplesList.appendChild(exampleDiv);
    });

    sqlmapExamplesList.querySelectorAll('.sqlmap-example-buttons .btn').forEach(button => {
        button.addEventListener('click', (event) => {
            const action = event.target.dataset.action;
            const name = event.target.dataset.name;
            let content = '';
            let title = '';

            if (action === 'notes') {
                const description = event.target.dataset.description;
                content = `<div class="font-semibold text-gray-300">Description:</div><pre class="bg-gray-800 text-gray-200 p-3 rounded-md overflow-x-auto whitespace-pre-wrap">${description}</pre>`;
                title = `Notes for ${name}`;
            } else if (action === 'output') {
                const output = event.target.dataset.output;
                content = `<div class="font-semibold text-gray-300">Example Output:</div><pre class="bg-gray-800 text-gray-200 p-3 rounded-md overflow-x-auto whitespace-pre-wrap">${ansiToHtml(output)}</pre>`;
                title = `Output for ${name}`;
            } else if (action === 'terminal') {
                const options = JSON.parse(event.target.dataset.options);
                const command = generateSqlmapCommand(options);
                content = `
                    <div class="font-semibold text-gray-300">SQLMap Command:</div>
                    <pre class="bg-gray-800 text-green-400 p-3 rounded-md overflow-x-auto whitespace-pre-wrap">${command}</pre>
                    <button class="btn bg-blue-500 hover:bg-blue-600 mt-2" onclick="copyToClipboard('${command}')">Copy Command</button>
                `;
                title = `Command for ${name}`;
            }

            // Create a temporary URL for the content to be displayed in the iframe
            const blob = new Blob([`
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>${title}</title>
                    <script src="https://cdn.tailwindcss.com"></script>
                    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
                    <style>
                        body { font-family: 'Inter', sans-serif; background-color: #1f2937; color: #f3f4f6; padding: 1rem; }
                        pre { white-space: pre-wrap; word-break: break-all; }
                        .btn { padding: 0.5rem 1rem; border-radius: 0.5rem; font-weight: 600; cursor: pointer; transition: all 0.2s ease-in-out; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); color: white; border: 1px solid; }
                        .bg-blue-500 { background-color: #3b82f6; }
                        .hover\\:bg-blue-600:hover { background-color: #2563eb; }
                        /* ANSI Color Mapping - copied from style.css */
                        .ansi-black { color: #000; }
                        .ansi-red { color: #f44336; }
                        .ansi-green { color: #4CAF50; }
                        .ansi-yellow { color: #ffeb3b; }
                        .ansi-blue { color: #2196f3; }
                        .ansi-magenta { color: #9c27b0; }
                        .ansi-cyan { color: #00bcd4; }
                        .ansi-white { color: #fff; }
                        .ansi-bright-black { color: #616161; }
                        .ansi-bright-red { color: #ef5350; }
                        .ansi-bright-green { color: #66bb6a; }
                        .ansi-bright-yellow { color: #ffee58; }
                        .ansi-bright-blue { color: #42a5f5; }
                        .ansi-bright-magenta { color: #ab47bc; }
                        .ansi-bright-cyan { color: #26c6da; }
                        .ansi-bright-white { color: #e0e0e0; }
                        .ansi-bold { font-weight: bold; }
                        .ansi-underline { text-decoration: underline; }
                        .ansi-reset { color: inherit; font-weight: normal; text-decoration: none; }
                    </style>
                    <script>
                        // Function to convert ANSI escape codes to HTML spans for coloring, copied from utils.js
                        function ansiToHtml(text) {
                            const ansiColors = {
                                '30': 'ansi-black', '31': 'ansi-red', '32': 'ansi-green', '33': 'ansi-yellow',
                                '34': 'ansi-blue', '35': 'ansi-magenta', '36': 'ansi-cyan', '37': 'ansi-white',
                                '90': 'ansi-bright-black', '91': 'ansi-bright-red', '92': 'ansi-bright-green',
                                '93': 'ansi-bright-yellow', '94': 'ansi-bright-blue', '95': 'ansi-bright-magenta',
                                '96': 'ansi-bright-cyan', '97': 'ansi-bright-white',
                                '1': 'ansi-bold', '4': 'ansi-underline', '0': 'ansi-reset'
                            };

                            let html = '';
                            let parts = text.split(/(\\x1b\\[[0-9;]*m)/g);

                            parts.forEach(part => {
                                if (part.startsWith('\\x1b[')) {
                                    const codes = part.substring(2, part.length - 1).split(';');
                                    codes.forEach(code => {
                                        if (ansiColors[code]) {
                                            html += \`<span class="\${ansiColors[code]}">\`;
                                        } else if (code === '0') {
                                            html += \`</span>\`.repeat(10); // Close all open spans for reset
                                        }
                                    });
                                } else {
                                    html += part;
                                }
                            });
                            return html;
                        }

                        // Function to copy to clipboard, copied from utils.js
                        function copyToClipboard(text) {
                            const textarea = document.createElement('textarea');
                            textarea.value = text;
                            document.body.appendChild(textarea);
                            textarea.select();
                            try {
                                document.execCommand('copy');
                                alert('Command copied to clipboard!'); // Using alert here as it's a temporary iframe
                            } catch (err) {
                                console.error('Failed to copy text: ', err);
                                alert('Failed to copy command.');
                            }
                            document.body.removeChild(textarea);
                        }

                        document.addEventListener('DOMContentLoaded', () => {
                            document.getElementById('content').innerHTML = decodeURIComponent(window.location.hash.substring(1));
                        });
                    </script>
                </head>
                <body>
                    <div id="content"></div>
                </body>
                </html>
            `], { type: 'text/html' });
            const objectUrl = URL.createObjectURL(blob);
            // Open in a new iframe window using handleOpenUrl
            handleOpenUrl(`${objectUrl}#${encodeURIComponent(content)}`, title, currentFolderForSqlmapExamples);
            // Removed: closeSqlmapExamplesModal();
        });
    });
}


// Notes Modal Functions
async function openNotesModal(folderName) {
    currentFolderForNotes = folderName;
    notesModalFolderNameSpan.textContent = folderName;
    notesContentTextarea.value = 'Loading notes...';
    saveNotesBtn.disabled = true;

    notesModal.classList.remove('hidden');
    notesModal.classList.add('show');

    try {
        const response = await fetch(`index.php?action=get_notes_content&folder_name=${encodeURIComponent(folderName)}`);
        const result = await response.json();

        if (result.status === 'success') {
            notesContentTextarea.value = result.content;
        } else {
            notesContentTextarea.value = '';
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error fetching notes content:', error);
        notesContentTextarea.value = '';
        showMessage('An error occurred while loading notes.', 'error');
    } finally {
        saveNotesBtn.disabled = false;
    }
}

function closeNotesModal() {
    notesModal.classList.remove('show');
    notesModal.classList.add('hidden');
    currentFolderForNotes = null;
}

async function saveNotes() {
    if (!currentFolderForNotes) {
        showMessage('No folder selected for notes.', 'error');
        return;
    }

    saveNotesBtn.disabled = true;
    showMessage(`Saving notes for ${currentFolderForNotes}...`, 'info');

    const notesContent = notesContentTextarea.value;

    try {
        const response = await fetch('index.php?action=save_notes_content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder_name: currentFolderForNotes,
                notes_content: notesContent
            })
        });
        const result = await response.json();

        if (response.ok && result.status === 'success') {
            showMessage(result.message);
            closeNotesModal();
            fetchAndDisplayFolders();
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error saving notes:', error);
        showMessage('An error occurred while trying to save notes.', 'error');
    } finally {
        saveNotesBtn.disabled = false;
    }
}

// NEW: Screen Modal Functions
async function openScreenModal(folderName) {
    currentFolderForScreen = folderName;
    screenModalFolderNameSpan.textContent = folderName;
    screenContentTextarea.value = 'Loading resolution...';
    saveScreenBtn.disabled = true;

    screenModal.classList.remove('hidden');
    screenModal.classList.add('show');

    try {
        const response = await fetch(`index.php?action=get_screen_content&folder_name=${encodeURIComponent(folderName)}`);
        const result = await response.json();

        if (result.status === 'success') {
            screenContentTextarea.value = result.content;
        } else {
            screenContentTextarea.value = '';
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error fetching screen content:', error);
        screenContentTextarea.value = '';
        showMessage('An error occurred while loading screen resolution.', 'error');
    } finally {
        saveScreenBtn.disabled = false;
    }
}

function closeScreenModal() {
    screenModal.classList.remove('show');
    screenModal.classList.add('hidden');
    currentFolderForScreen = null;
}

async function saveScreenContent() {
    if (!currentFolderForScreen) {
        showMessage('No folder selected for screen resolution.', 'error');
        return;
    }

    saveScreenBtn.disabled = true;
    showMessage(`Saving resolution for ${currentFolderForScreen}...`, 'info');

    const screenContent = screenContentTextarea.value.trim();

    // Basic validation for resolution format (e.g., "800x600")
    const resolutionRegex = /^\d+x\d+$/;
    if (screenContent && !resolutionRegex.test(screenContent)) {
        showMessage('Invalid resolution format. Please use WIDTHxHEIGHT (e.g., 800x600).', 'error');
        saveScreenBtn.disabled = false;
        return;
    }

    try {
        const response = await fetch('index.php?action=save_screen_content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder_name: currentFolderForScreen,
                screen_content: screenContent
            })
        });
        const result = await response.json();

        if (response.ok && result.status === 'success') {
            showMessage(result.message);
            closeScreenModal();
            fetchAndDisplayFolders(); // Re-fetch to update card with new resolution
        } else {
            showMessage(result.message, 'error');
        }
    } catch (error) {
        console.error('Error saving screen resolution:', error);
        showMessage('An error occurred while trying to save screen resolution.', 'error');
    } finally {
        saveScreenBtn.disabled = false;
    }
}


// Event Listeners for modals
closeModalBtn.addEventListener('click', closeImageUploadModal);
imageInput.addEventListener('change', (event) => handleImageSelect(event, imagePreview, imagePreviewPlaceholder));
uploadImageBtn.addEventListener('click', async () => {
    if (currentFolderForUpload) {
        const success = await uploadImageForProject(currentFolderForUpload, imageInput, uploadImageBtn);
        if (success) {
            fetchAndDisplayFolders();
            closeImageUploadModal();
        }
    }
});

settingsBtn.addEventListener('click', openSettingsModal);
closeSettingsModalBtn.addEventListener('click', closeSettingsModal);
saveSettingsBtn.addEventListener('click', saveSettingsFromModal);
backToLauncherBtn.addEventListener('click', closeSettingsModal);

closeCreateProjectModalBtn.addEventListener('click', closeCreateProjectModal);
saveProjectBtn.addEventListener('click', saveProject);
createImageInput.addEventListener('change', (event) => handleImageSelect(event, createImagePreview, createImagePreviewPlaceholder));

closeEditFolderModalBtn.addEventListener('click', closeEditFolderModal);
saveFolderContentBtn.addEventListener('click', saveFolderContent);
editImageInput.addEventListener('change', (event) => handleImageSelect(event, editImagePreview, editImagePreviewPlaceholder));

closeSqlmapExamplesModalBtn.addEventListener('click', closeSqlmapExamplesModal);
backToLauncherFromExamplesBtn.addEventListener('click', closeSqlmapExamplesModal);
sqlmapExamplesSearchInput.addEventListener('input', filterAndDisplaySqlmapExamples);

closeNotesModalBtn.addEventListener('click', closeNotesModal);
saveNotesBtn.addEventListener('click', saveNotes);
cancelNotesBtn.addEventListener('click', closeNotesModal);

// NEW: Event Listeners for Screen Modal
closeScreenModalBtn.addEventListener('click', closeScreenModal);
saveScreenBtn.addEventListener('click', saveScreenContent);
cancelScreenBtn.addEventListener('click', closeScreenModal);
