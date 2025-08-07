<?php
// Set error reporting for development
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// Include configuration and helper functions
require_once __DIR__ . DIRECTORY_SEPARATOR . 'php' . DIRECTORY_SEPARATOR . 'config.php';
require_once __DIR__ . DIRECTORY_SEPARATOR . 'php' . DIRECTORY_SEPARATOR . 'helpers.php';
require_once __DIR__ . DIRECTORY_SEPARATOR . 'php' . DIRECTORY_SEPARATOR . 'settings.php';
require_once __DIR__ . DIRECTORY_SEPARATOR . 'php' . DIRECTORY_SEPARATOR . 'actions.php';

// Ensure necessary directories exist and are writable
if (!is_dir($databaseBaseDir)) {
    mkdir($databaseBaseDir, 0777, true);
}
if (!is_dir($pidsDir)) {
    mkdir($pidsDir, 0777, true);
}

// Initialize next available port if file doesn't exist
if (!file_exists($nextPortFile)) {
    file_put_contents($nextPortFile, '5001'); // Starting port for Python apps
}

// Initialize settings file if it doesn't exist
if (!file_exists(SETTINGS_FILE)) {
    file_put_contents(SETTINGS_FILE, json_encode(['showCover' => true, 'enableCardAnimation' => true, 'openInIframe' => false, 'showFullUrl' => false, 'enableTaskbar' => false], JSON_PRETTY_PRINT));
}

// Find python executable once at the start
$pythonExecutable = findPythonExecutable();
$pidsDirWritable = is_writable($pidsDir);

// Determine the action based on GET parameter
$action = $_GET['action'] ?? '';

// Handle API actions if an action is specified
if ($action) {
    handleApiAction($action, $databaseBaseDir, $pidsDir, $nextPortFile, $pythonExecutable);
    exit; // Exit after handling API action
}

// If no action, serve the main HTML page
$currentSettings = getSettings();
$enableCardAnimationJs = json_encode($currentSettings['enableCardAnimation']);
$openInIframeJs = json_encode($currentSettings['openInIframe']);
$showFullUrlJs = json_encode($currentSettings['showFullUrl']);
$enableTaskbarJs = json_encode($currentSettings['enableTaskbar']);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PHP Python App Launcher</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Font Awesome for icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <!-- Only Inter font for better performance -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <!-- Custom Styles -->
    <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
    <!-- NEW: Taskbar -->
    <div id="taskbar" class="hidden">
        <div id="taskbarTabs">
            <!-- Tabs will be injected here by JavaScript -->
        </div>
    </div>

    <div id="mainContent" class="flex-grow">
        <div class="container">
            <h1 class="text-4xl font-bold text-center mb-8">SPACE WEB CREATED BY KHEDR0X00</h1>

            <!-- Settings, Stop All, and Create Project Buttons -->
            <div class="flex justify-center space-x-4 mb-6 flex-wrap">
                <button id="settingsBtn" class="btn bg-indigo-600 hover:bg-indigo-700">Settings</button>
                <button id="stopAllAppsBtn" class="btn bg-red-600 hover:bg-red-700">Stop All</button>
                <button id="createProjectBtn" class="btn btn-create-project">Create Project</button>
            </div>

            <?php if (!$pidsDirWritable): ?>
                <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4" role="alert">
                    <strong class="font-bold">Error:</strong>
                    <span class="block sm:inline">The 'pids' directory is not writable. Please set appropriate permissions (e.g., chmod 777 pids) for the application to function correctly.</span>
                </div>
            <?php endif; ?>

            <?php if (!$pythonExecutable): ?>
                <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4" role="alert">
                    <strong class="font-bold">Error:</strong>
                    <span class="block sm:inline">Python executable not found on the server. Python applications cannot be launched.</span>
                </div>
            <?php endif; ?>

            <input type="text" id="searchFolders" class="search-input" placeholder="Search for folders...">

            <div id="folderCards" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <!-- Folder cards will be injected here by JavaScript -->
            </div>

            <div id="messageBox" class="message-box"></div>
        </div>
    </div>

    <!-- Image Upload Modal (Existing - used for individual card upload) -->
    <div id="imageUploadModal" class="modal-overlay hidden">
        <div class="modal-content w-full max-w-md">
            <button id="closeModalBtn" class="modal-close-btn">&times;</button>
            <h2 class="text-3xl font-bold text-white mb-6 text-center">Upload Cover Image</h2>
            <p class="text-gray-300 text-center mb-6">For: <span id="modalFolderName" class="font-semibold text-indigo-400"></span></p>

            <div class="mb-6">
                <label for="imageInput" class="block text-gray-300 text-sm font-bold mb-2">Select Image:</label>
                <input type="file" id="imageInput" accept="image/png, image/jpeg, image/gif, image/webp" class="block w-full text-sm text-gray-300
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-full file:border-0
                    file:text-sm file:font-semibold
                    file:bg-indigo-500 file:text-white
                    hover:file:bg-indigo-600 cursor-pointer">
            </div>

            <div id="imagePreviewContainer" class="mb-6 flex justify-center items-center h-48 bg-gray-800 rounded-lg overflow-hidden border border-gray-600">
                <img id="imagePreview" src="#" alt="Image Preview" class="hidden max-h-full max-w-full object-contain">
                <p id="imagePreviewPlaceholder" class="text-gray-400">No image selected</p>
            </div>

            <button id="uploadImageBtn" class="btn bg-green-600 hover:bg-green-700 w-full">Upload Image</button>
        </div>
    </div>

    <!-- NEW: Settings Modal -->
    <div id="settingsModal" class="modal-overlay hidden">
        <div class="modal-content">
            <button id="closeSettingsModalBtn" class="modal-close-btn">&times;</button>
            <h2 class="text-3xl font-bold text-white mb-6 text-center">App Settings</h2>

            <div class="mb-6 flex items-center justify-between">
                <label for="showCoverCheckbox" class="text-lg text-gray-300 cursor-pointer">Show Cover Images on Cards</label>
                <input type="checkbox" id="showCoverCheckbox" class="form-checkbox h-6 w-6 text-indigo-500 rounded-md bg-gray-800 border-gray-600">
            </div>

            <div class="mb-6 flex items-center justify-between">
                <label for="enableCardAnimationCheckbox" class="text-lg text-gray-300 cursor-pointer">Enable Card Animations</label>
                <input type="checkbox" id="enableCardAnimationCheckbox" class="form-checkbox h-6 w-6 text-indigo-500 rounded-md bg-gray-800 border-gray-600">
            </div>

            <div class="mb-6 flex items-center justify-between">
                <label for="openInIframeCheckbox" class="text-lg text-gray-300 cursor-pointer">Open URL in Iframe Window</label>
                <input type="checkbox" id="openInIframeCheckbox" class="form-checkbox h-6 w-6 text-indigo-500 rounded-md bg-gray-800 border-gray-600">
            </div>

            <div class="mb-6 flex items-center justify-between">
                <label for="showFullUrlCheckbox" class="text-lg text-gray-300 cursor-pointer">Show Full URL on Cards (Python Only)</label>
                <input type="checkbox" id="showFullUrlCheckbox" class="form-checkbox h-6 w-6 text-indigo-500 rounded-md bg-gray-800 border-gray-600">
            </div>

            <!-- NEW: Enable Taskbar Checkbox -->
            <div class="mb-6 flex items-center justify-between">
                <label for="enableTaskbarCheckbox" class="text-lg text-gray-300 cursor-pointer">Enable Taskbar</label>
                <input type="checkbox" id="enableTaskbarCheckbox" class="form-checkbox h-6 w-6 text-indigo-500 rounded-md bg-gray-800 border-gray-600">
            </div>

            <div class="flex justify-end space-x-4">
                <button id="saveSettingsBtn" class="btn bg-green-600 hover:bg-green-700">Save Changes</button>
                <button id="backToLauncherBtn" class="btn bg-gray-600 hover:bg-gray-700">Back to Launcher</button>
            </div>
        </div>
    </div>

    <!-- NEW: Create Project Modal -->
    <div id="createProjectModal" class="modal-overlay hidden">
        <div class="modal-content">
            <button id="closeCreateProjectModalBtn" class="modal-close-btn">&times;</button>
            <h2 class="text-3xl font-bold text-white mb-6 text-center">Create New Project</h2>

            <div class="mb-4">
                <label for="projectNameInput" class="modal-label">Project Name:</label>
                <input type="text" id="projectNameInput" class="modal-input" placeholder="e.g., MyAwesomeApp">
            </div>

            <div class="mb-4">
                <label for="categoryInput" class="modal-label">Category (Optional):</label>
                <input type="text" id="categoryInput" class="modal-input" placeholder="e.g., Web App, Game, Utility">
            </div>

            <!-- NEW: Tags Input for Create Project -->
            <div class="mb-4">
                <label for="tagsInput" class="modal-label">Tags (Optional, comma-separated):</label>
                <input type="text" id="tagsInput" class="modal-input" placeholder="e.g., python, web, game">
            </div>

            <div class="mb-4">
                <label for="appPyCodeTextarea" class="modal-label">app.py Code:</label>
                <textarea id="appPyCodeTextarea" class="modal-textarea" placeholder="Write your Python Flask/FastAPI code here..."></textarea>
            </div>

            <!-- NEW: gui.py Code Input for Create Project -->
            <div class="mb-4">
                <label for="guiPyCodeTextarea" class="modal-label">gui.py Code (Optional - for standalone GUI apps):</label>
                <textarea id="guiPyCodeTextarea" class="modal-textarea" placeholder="Write your Python GUI code (e.g., Tkinter, PyQt) here..."></textarea>
            </div>

            <div class="mb-4">
                <label for="requirementsTxtTextarea" class="modal-label">requirements.txt Code (Optional):</label>
                <textarea id="requirementsTxtTextarea" class="modal-textarea" placeholder="List Python packages here, e.g., flask&#10;requests"></textarea>
            </div>

            <div class="mb-4">
                <label for="installScriptTextarea" class="modal-label">install.sh Code (Optional):</label>
                <textarea id="installScriptTextarea" class="modal-textarea" placeholder="Write your shell script here, e.g., npm install&#10;pip install -r requirements.txt"></textarea>
            </div>

            <div class="mb-4">
                <label for="sqlmapExamplesTextarea" class="modal-label">examples.txt Code (Optional):</label>
                <textarea id="sqlmapExamplesTextarea" class="modal-textarea" placeholder="Paste SQLMap examples JSON here..."></textarea>
            </div>

            <!-- NEW: notes.txt Code Input for Create Project -->
            <div class="mb-4">
                <label for="notesTextarea" class="modal-label">notes.txt Content (Optional):</label>
                <textarea id="notesTextarea" class="modal-textarea" placeholder="Write your notes here..."></textarea>
            </div>

            <!-- NEW: screen.txt Code Input for Create Project -->
            <div class="mb-4">
                <label for="screenTxtTextarea" class="modal-label">screen.txt Content (Optional - e.g., 800x600):</label>
                <input type="text" id="screenTxtTextarea" class="modal-input" placeholder="e.g., 800x600 or 1280x720">
            </div>

            <div class="mb-6">
                <label for="indexHtmlCodeTextarea" class="modal-label">index.html Code (for templates/index.html):</label>
                <textarea id="indexHtmlCodeTextarea" class="modal-textarea" placeholder="Write your HTML code for the main template here..."></textarea>
            </div>

            <div class="mb-6">
                <label for="createImageInput" class="block text-gray-300 text-sm font-bold mb-2">Upload Cover Image (Optional):</label>
                <input type="file" id="createImageInput" accept="image/png, image/jpeg, image/gif, image/webp" class="block w-full text-sm text-gray-300
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-full file:border-0
                    file:text-sm file:font-semibold
                    file:bg-indigo-500 file:text-white
                    hover:file:bg-indigo-600 cursor-pointer">
            </div>

            <div id="createImagePreviewContainer" class="mb-6 flex justify-center items-center h-48 bg-gray-800 rounded-lg overflow-hidden border border-gray-600">
                <img id="createImagePreview" src="#" alt="Image Preview" class="hidden max-h-full max-w-full object-contain">
                <p id="createImagePreviewPlaceholder" class="text-gray-400">No image selected</p>
            </div>

            <button id="saveProjectBtn" class="btn bg-indigo-600 hover:bg-indigo-700 w-full">Save Project</button>
        </div>
    </div>

    <!-- NEW: Edit Folder Modal -->
    <div id="editFolderModal" class="modal-overlay hidden">
        <div class="modal-content">
            <button id="closeEditFolderModalBtn" class="modal-close-btn">&times;</button>
            <h2 class="text-3xl font-bold text-white mb-6 text-center">Edit Folder: <span id="editModalFolderName" class="font-semibold text-indigo-400"></span></h2>

            <div class="mb-4">
                <label for="editCategoryTxtInput" class="modal-label">Category (category.txt):</label>
                <input type="text" id="editCategoryTxtInput" class="modal-input" placeholder="e.g., Web App, Game, Utility">
            </div>

            <!-- NEW: Tags Input for Edit Folder -->
            <div class="mb-4">
                <label for="editTagsTxtInput" class="modal-label">Tags (tags.txt, comma-separated):</label>
                <input type="text" id="editTagsTxtInput" class="modal-input" placeholder="e.g., python, web, game">
            </div>

            <div class="mb-4">
                <label for="editAppPyCodeTextarea" class="modal-label">app.py Code:</label>
                <textarea id="editAppPyCodeTextarea" class="modal-textarea" placeholder="Edit your Python Flask/FastAPI code here..."></textarea>
            </div>

            <!-- NEW: gui.py Code Input for Edit Folder -->
            <div class="mb-4">
                <label for="editGuiPyCodeTextarea" class="modal-label">gui.py Code (Optional):</label>
                <textarea id="editGuiPyCodeTextarea" class="modal-textarea" placeholder="Edit your Python GUI code (e.g., Tkinter, PyQt) here..."></textarea>
            </div>

            <div class="mb-4">
                <label for="editRequirementsTxtTextarea" class="modal-label">requirements.txt Code (Optional):</label>
                <textarea id="editRequirementsTxtTextarea" class="modal-textarea" placeholder="Edit Python packages here, e.g., flask&#10;requests"></textarea>
            </div>

            <div class="mb-4">
                <label for="editInstallScriptTextarea" class="modal-label">install.sh Code (Optional):</label>
                <textarea id="editInstallScriptTextarea" class="modal-textarea" placeholder="Edit your shell script here, e.g., npm install&#10;pip install -r requirements.txt"></textarea>
            </div>

            <div class="mb-4">
                <label for="editSqlmapExamplesTextarea" class="modal-label">examples.txt Code (Optional):</label>
                <textarea id="editSqlmapExamplesTextarea" class="modal-textarea" placeholder="Paste SQLMap examples JSON here..."></textarea>
            </div>

            <!-- NEW: notes.txt Code Input for Edit Folder -->
            <div class="mb-4">
                <label for="editNotesTextarea" class="modal-label">notes.txt Content (Optional):</label>
                <textarea id="editNotesTextarea" class="modal-textarea" placeholder="Edit your notes here..."></textarea>
            </div>

            <!-- NEW: screen.txt Code Input for Edit Folder -->
            <div class="mb-4">
                <label for="editScreenTxtInput" class="modal-label">screen.txt Content (Optional - e.g., 800x600):</label>
                <input type="text" id="editScreenTxtInput" class="modal-input" placeholder="e.g., 800x600 or 1280x720">
            </div>

            <div class="mb-6">
                <label for="editIndexHtmlCodeTextarea" class="modal-label">index.html Code (for templates/index.html):</label>
                <textarea id="editIndexHtmlCodeTextarea" class="modal-textarea" placeholder="Edit your HTML code for the main template here..."></textarea>
            </div>

            <div class="mb-6">
                <label for="editImageInput" class="block text-gray-300 text-sm font-bold mb-2">Update Cover Image (Optional):</label>
                <input type="file" id="editImageInput" accept="image/png, image/jpeg, image/gif, image/webp" class="block w-full text-sm text-gray-300
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-full file:border-0
                    file:text-sm file:font-semibold
                    file:bg-indigo-500 file:text-white
                    hover:file:bg-indigo-600 cursor-pointer">
            </div>

            <div id="editImagePreviewContainer" class="mb-6 flex justify-center items-center h-48 bg-gray-800 rounded-lg overflow-hidden border border-gray-600">
                <img id="editImagePreview" src="#" alt="Image Preview" class="hidden max-h-full max-w-full object-contain">
                <p id="editImagePreviewPlaceholder" class="text-gray-400">No image selected</p>
            </div>

            <button id="saveFolderContentBtn" class="btn bg-indigo-600 hover:bg-indigo-700 w-full">Save Changes</button>
        </div>
    </div>

    <!-- NEW: SQLMap Examples Modal -->
    <div id="sqlmapExamplesModal" class="modal-overlay hidden">
        <div class="modal-content">
            <button id="closeSqlmapExamplesModalBtn" class="modal-close-btn">&times;</button>
            <!-- Updated to dynamically display folder name -->
            <h2 class="text-3xl font-bold text-white mb-6 text-center">Examples for <span id="sqlmapExamplesFolderName" class="font-semibold text-indigo-400"></span></h2>
            <input type="text" id="sqlmapExamplesSearch" class="search-input mb-4" placeholder="Search examples...">
            <div id="sqlmapExamplesList" class="space-y-4">
                <!-- Examples will be loaded here -->
            </div>
            <div class="flex justify-end mt-6">
                <button id="backToLauncherFromExamplesBtn" class="btn bg-gray-600 hover:bg-gray-700">Back to Launcher</button>
            </div>
        </div>
    </div>

    <!-- NEW: Notes Modal -->
    <div id="notesModal" class="modal-overlay hidden">
        <div class="modal-content">
            <button id="closeNotesModalBtn" class="modal-close-btn">&times;</button>
            <h2 class="text-3xl font-bold text-white mb-6 text-center">Notes for <span id="notesModalFolderName" class="font-semibold text-indigo-400"></span></h2>
            <div class="mb-4">
                <label for="notesContentTextarea" class="modal-label">Edit Notes:</label>
                <textarea id="notesContentTextarea" class="modal-textarea" placeholder="Write your notes here..."></textarea>
            </div>
            <div class="flex justify-end space-x-4">
                <button id="saveNotesBtn" class="btn bg-green-600 hover:bg-green-700">Save Notes</button>
                <button id="cancelNotesBtn" class="btn bg-gray-600 hover:bg-gray-700">Cancel</button>
            </div>
        </div>
    </div>

    <!-- NEW: Screen Modal -->
    <div id="screenModal" class="modal-overlay hidden">
        <div class="modal-content">
            <button id="closeScreenModalBtn" class="modal-close-btn">&times;</button>
            <h2 class="text-3xl font-bold text-white mb-6 text-center">Screen Resolution for <span id="screenModalFolderName" class="font-semibold text-indigo-400"></span></h2>
            <div class="mb-4">
                <label for="screenContentTextarea" class="modal-label">Edit Resolution (e.g., 800x600):</label>
                <input type="text" id="screenContentTextarea" class="modal-input" placeholder="e.g., 800x600 or 1280x720">
            </div>
            <div class="flex justify-end space-x-4">
                <button id="saveScreenBtn" class="btn bg-green-600 hover:bg-green-700">Save Resolution</button>
                <button id="cancelScreenBtn" class="btn bg-gray-600 hover:bg-gray-700">Cancel</button>
            </div>
        </div>
    </div>

    <!-- NEW: Container for multiple iframe windows -->
    <div id="iframeWindowsContainer">
        <!-- Iframe windows will be injected here by JavaScript -->
    </div>


    <script>
        // PHP variables passed to JavaScript
        const WEB_SERVER_PORT = <?php echo WEB_SERVER_PORT; ?>;
        const enableCardAnimationJs = <?php echo $enableCardAnimationJs; ?>;
        const openInIframeJs = <?php echo $openInIframeJs; ?>;
        const showFullUrlJs = <?php echo $showFullUrlJs; ?>;
        const enableTaskbarJs = <?php echo $enableTaskbarJs; ?>;
    </script>
    <!-- Include JavaScript files in order of dependency -->
    <script src="assets/js/utils.js"></script>
    <script src="assets/js/iframe_manager.js"></script>
    <script src="assets/js/modals.js"></script>
    <script src="assets/js/main.js"></script>
</body>
</html>
