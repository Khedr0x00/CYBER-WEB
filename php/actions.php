<?php
// Include config, helpers, and settings to access necessary constants and functions
require_once __DIR__ . DIRECTORY_SEPARATOR . 'config.php';
require_once __DIR__ . DIRECTORY_SEPARATOR . 'helpers.php';
require_once __DIR__ . DIRECTORY_SEPARATOR . 'settings.php';

/**
 * Handles various API actions based on the provided action string.
 * This function centralizes the logic for all backend operations.
 *
 * @param string $action The action to perform (e.g., 'list_folders', 'start_app').
 * @param string $databaseBaseDir Base directory for application folders.
 * @param string $pidsDir Directory for PID files.
 * @param string $nextPortFile File storing the next available port.
 * @param string|null $pythonExecutable Path to the Python executable.
 */
function handleApiAction($action, $databaseBaseDir, $pidsDir, $nextPortFile, $pythonExecutable) {
    header('Content-Type: application/json');

    switch ($action) {
        case 'list_folders':
            $folders = [];
            if (is_dir($databaseBaseDir)) {
                foreach (scandir($databaseBaseDir) as $folderName) {
                    if ($folderName === '.' || $folderName === '..') {
                        continue;
                    }
                    $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;
                    $pythonAppFilePath = $folderPath . DIRECTORY_SEPARATOR . 'app.py';
                    $phpAppFilePath = $folderPath . DIRECTORY_SEPARATOR . 'index.php';
                    $requirementsFilePath = $folderPath . DIRECTORY_SEPARATOR . 'requirements.txt';
                    $installScriptPath = $folderPath . DIRECTORY_SEPARATOR . 'install.sh';
                    $categoryFilePath = $folderPath . DIRECTORY_SEPARATOR . 'category.txt';
                    $tagsFilePath = $folderPath . DIRECTORY_SEPARATOR . 'tags.txt';
                    $guiPyFilePath = $folderPath . DIRECTORY_SEPARATOR . 'gui.py';
                    $sqlmapExamplesFilePath = $folderPath . DIRECTORY_SEPARATOR . 'examples.txt';
                    $notesFilePath = $folderPath . DIRECTORY_SEPARATOR . NOTES_FILE_NAME;
                    // NEW: Path for screen.txt
                    $screenFilePath = $folderPath . DIRECTORY_SEPARATOR . SCREEN_FILE_NAME;


                    $isPythonApp = file_exists($pythonAppFilePath);
                    $isPhpApp = file_exists($phpAppFilePath);
                    $hasRequirementsFile = file_exists($requirementsFilePath);
                    $hasInstallScript = file_exists($installScriptPath);
                    $hasCategoryFile = file_exists($categoryFilePath);
                    $hasTagsFile = file_exists($tagsFilePath);
                    $hasGuiPyFile = file_exists($guiPyFilePath);
                    $hasSqlmapExamplesFile = file_exists($sqlmapExamplesFilePath);
                    $hasNotesFile = file_exists($notesFilePath);
                    // NEW: Check for screen.txt existence
                    $hasScreenFile = file_exists($screenFilePath);


                    $categoryText = '';
                    if ($hasCategoryFile) {
                        $categoryText = trim(file_get_contents($categoryFilePath));
                    }

                    $tagsText = '';
                    if ($hasTagsFile) {
                        $tagsText = trim(file_get_contents($tagsFilePath));
                    }

                    // NEW: Read screen resolution
                    $screenResolution = '';
                    if ($hasScreenFile) {
                        $screenResolution = trim(file_get_contents($screenFilePath));
                    }

                    if ($isPythonApp) {
                        $pidFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '.json';
                        $isRunning = false;
                        $port = null;
                        $fullUrl = '';

                        if (file_exists($pidFile)) {
                            $pidInfo = json_decode(file_get_contents($pidFile), true);
                            if ($pidInfo && isset($pidInfo['port'])) {
                                $port = $pidInfo['port'];
                                $currentPid = getPidByPort($port);
                                if ($currentPid && isProcessRunning($currentPid)) {
                                    $isRunning = true;
                                    $fullUrl = "http://127.0.0.1:{$port}";
                                } else {
                                    error_log("list_folders: Stale PID file detected for Python app {$folderName}. Cleaning up.");
                                    if (file_exists($pidFile)) {
                                        unlink($pidFile);
                                    }
                                }
                            } else {
                                error_log("list_folders: Invalid PID file detected for Python app {$folderName}. Cleaning up.");
                                if (file_exists($pidFile)) {
                                    unlink($pidFile);
                                }
                            }
                        }

                        $folders[] = [
                            'name' => $folderName,
                            'type' => 'python',
                            'is_running' => $isRunning,
                            'port' => $port,
                            'full_url' => $fullUrl,
                            'has_requirements_file' => $hasRequirementsFile,
                            'has_install_script' => $hasInstallScript,
                            'has_category_file' => $hasCategoryFile,
                            'category_text' => $categoryText,
                            'has_tags_file' => $hasTagsFile,
                            'tags_text' => $tagsText,
                            'has_gui_py_file' => $hasGuiPyFile,
                            'has_sqlmap_examples_file' => $hasSqlmapExamplesFile,
                            'has_notes_file' => $hasNotesFile,
                            // NEW: Add screen file info
                            'has_screen_file' => $hasScreenFile,
                            'screen_resolution' => $screenResolution
                        ];
                    } elseif ($isPhpApp) {
                        $phpAppUrl = 'http://127.0.0.1:' . WEB_SERVER_PORT . '/database/' . $folderName . '/index.php';

                        $folders[] = [
                            'name' => $folderName,
                            'type' => 'php',
                            'is_running' => true,
                            'url' => $phpAppUrl,
                            'full_url' => $phpAppUrl,
                            'has_requirements_file' => false,
                            'has_install_script' => false,
                            'has_category_file' => $hasCategoryFile,
                            'category_text' => $categoryText,
                            'has_tags_file' => $hasTagsFile,
                            'tags_text' => $tagsText,
                            'has_gui_py_file' => $hasGuiPyFile,
                            'has_sqlmap_examples_file' => $hasSqlmapExamplesFile,
                            'has_notes_file' => $hasNotesFile,
                            // NEW: Add screen file info
                            'has_screen_file' => $hasScreenFile,
                            'screen_resolution' => $screenResolution
                        ];
                    }
                }
            }
            echo json_encode($folders);
            break;

        case 'start_app':
            $input = json_decode(file_get_contents('php://input'), true);
            $folderName = $input['folder_name'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;
            $appFilePath = $folderPath . DIRECTORY_SEPARATOR . 'app.py';

            if (!file_exists($appFilePath)) {
                echo json_encode(['status' => 'error', 'message' => "This is not a Python app or app.py not found in {$folderName}."]);
                break;
            }

            if (!$pythonExecutable) {
                echo json_encode(['status' => 'error', 'message' => 'Python executable not found on the server. Please ensure Python is installed and in the system\'s PATH.']);
                break;
            }

            $pidFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '.json';
            $logFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '_output.log';

            if (file_exists($logFile)) {
                file_put_contents($logFile, '');
            }

            if (file_exists($pidFile)) {
                $pidInfo = json_decode(file_get_contents($pidFile), true);
                if ($pidInfo && isset($pidInfo['port'])) {
                    $port = $pidInfo['port'];
                    $currentPid = getPidByPort($port);
                    if ($currentPid && isProcessRunning($currentPid)) {
                        error_log("start_app: App in {$folderName} already running on port {$port}.");
                        echo json_encode(['status' => 'info', 'message' => "App in {$folderName} is already running.", 'url' => "http://127.0.0.1:{$port}", 'full_url' => "http://127.0.0.1:{$port}"]);
                        break;
                    } else {
                        error_log("start_app: Stale PID file detected for {$folderName}. Cleaning up before restart.");
                        if (file_exists($pidFile)) {
                            unlink($pidFile);
                        }
                    }
                }
            }

            $port = getNextAvailablePort($nextPortFile);
            $appUrl = "http://127.0.0.1:{$port}";

            $command = escapeshellarg($pythonExecutable) . " " . escapeshellarg($appFilePath) . " --port " . escapeshellarg($port);

            if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
                $fullCommand = "cd /D " . escapeshellarg($folderPath) . " && start /B " . $command . " > " . escapeshellarg($logFile) . " 2>&1";
            } else {
                $fullCommand = "cd " . escapeshellarg($folderPath) . " && nohup " . $command . " > " . escapeshellarg($logFile) . " 2>&1 &";
            }

            error_log("start_app: Attempting to execute command: {$fullCommand}");
            exec($fullCommand, $output, $return_var);
            error_log("start_app: Command execution returned: {$return_var}. Output: " . implode("\n", $output));

            $isActuallyRunning = false;
            $currentPidAfterStart = null;
            $maxRetries = 15; // Try for up to 15 seconds
            $retryDelay = 1; // 1 second delay between retries

            for ($i = 0; $i < $maxRetries; $i++) {
                $currentPidAfterStart = getPidByPort($port);
                if ($currentPidAfterStart && isProcessRunning($currentPidAfterStart)) {
                    $isActuallyRunning = true;
                    break;
                }
                sleep($retryDelay);
            }

            if ($return_var === 0 && $isActuallyRunning) {
                file_put_contents($pidFile, json_encode(['port' => $port, 'pid' => $currentPidAfterStart]));
                error_log("start_app: App in {$folderName} successfully started on port {$port} with PID {$currentPidAfterStart}.");
                echo json_encode(['status' => 'success', 'message' => "App in {$folderName} started on port {$port}.", 'url' => $appUrl, 'full_url' => $appUrl]);
            } else {
                $errorMessage = "Failed to start app in {$folderName}.";
                if (!$isActuallyRunning) {
                    $errorMessage .= " Process not detected running after start attempt.";
                }
                $errorMessage .= " Command: {$fullCommand} Return Var: {$return_var} Output: " . implode("\n", $output) . ". Check {$logFile} for details.";

                $logContent = '';
                if (file_exists($logFile) && filesize($logFile) > 0) {
                    $logContent = file_get_contents($logFile);
                    $errorMessage .= "\nLog content: " . substr($logContent, -500);
                } else {
                    $errorMessage .= "\nLog file is empty or not found.";
                }

                if (strpos($logContent, 'ModuleNotFoundError: No module named') !== false) {
                    $errorMessage = "Failed to start app in {$folderName}. It appears a required Python module is missing. Please click the 'Install Requirements' icon (download arrow) on the app's card to install dependencies, then try starting the app again.";
                    error_log("start_app: ModuleNotFoundError detected for {$folderName}. Suggesting requirements installation.");
                }

                error_log("start_app: " . $errorMessage);
                echo json_encode(['status' => 'error', 'message' => $errorMessage]);
            }
            break;

        case 'stop_app':
            $input = json_decode(file_get_contents('php://input'), true);
            $folderName = $input['folder_name'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;
            $appFilePath = $folderPath . DIRECTORY_SEPARATOR . 'app.py';

            if (!file_exists($appFilePath)) {
                echo json_encode(['status' => 'error', 'message' => "This is not a Python app or app.py not found in {$folderName}."]);
                break;
            }

            $pidFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '.json';
            $logFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '_output.log';

            if (!file_exists($pidFile)) {
                error_log("stop_app: No PID file found for {$folderName}. Assuming not running.");
                echo json_encode(['status' => 'info', 'message' => "No running app found for {$folderName} (no PID file)."]);
                break;
            }

            $pidInfo = json_decode(file_get_contents($pidFile), true);
            if (!$pidInfo || !isset($pidInfo['port'])) {
                error_log("stop_app: Invalid PID file for {$folderName}. Cleaning up.");
                echo json_encode(['status' => 'error', 'message' => "Invalid PID file for {$folderName}. Attempting cleanup."]);
                if (file_exists($pidFile)) {
                    unlink($pidFile);
                }
                break;
            }

            $port = $pidInfo['port'];
            $pid = getPidByPort($port);

            $gracefulShutdownAttempted = false;
            if ($pid && isProcessRunning($pid)) {
                $shutdownUrl = "http://127.0.0.1:{$port}/shutdown";
                error_log("stop_app: Attempting graceful shutdown for {$folderName} at {$shutdownUrl}");

                $options = [
                    'http' => [
                        'method' => 'POST',
                        'header' => 'Content-type: application/json',
                        'content' => json_encode(['action' => 'shutdown']),
                        'timeout' => 5,
                        'ignore_errors' => true
                    ]
                ];
                $context = stream_context_create($options);
                $result = @file_get_contents($shutdownUrl, false, $context);

                if ($result !== FALSE) {
                    $http_response_header_array = $http_response_header;
                    $status_line = $http_response_header_array[0];
                    preg_match('{HTTP\/\S+\s(\d{3})}', $status_line, $match);
                    $status_code = $match[1];
                    error_log("stop_app: Graceful shutdown HTTP request to {$shutdownUrl} returned status {$status_code}. Response: {$result}");

                    if ($status_code >= 200 && $status_code < 300) {
                        $gracefulShutdownAttempted = true;
                        error_log("stop_app: Graceful shutdown initiated for {$folderName}. Waiting for process to terminate.");
                        sleep(2);
                    }
                } else {
                    error_log("stop_app: Graceful shutdown HTTP request to {$shutdownUrl} failed. Result was FALSE. Error: " . (error_get_last()['message'] ?? 'Unknown error'));
                }
            }

            $currentPidAfterGracefulAttempt = getPidByPort($port);
            $isStillRunning = ($currentPidAfterGracefulAttempt && isProcessRunning($currentPidAfterGracefulAttempt));

            if ($isStillRunning) {
                error_log("stop_app: Process for {$folderName} (PID {$currentPidAfterGracefulAttempt}) is still running after graceful attempt. Proceeding with forceful kill.");
                if (killProcess($currentPidAfterGracefulAttempt)) {
                    if (file_exists($pidFile)) {
                        unlink($pidFile);
                        error_log("stop_app: Successfully removed PID file for {$folderName} after forceful kill.");
                    }
                    echo json_encode(['status' => 'success', 'message' => "App in {$folderName} stopped forcefully."]);
                } else {
                    error_log("stop_app: Failed to forcefully kill process for {$folderName} with PID {$currentPidAfterGracefulAttempt}.");
                    echo json_encode(['status' => 'error', 'message' => "Failed to stop app in {$folderName}. Check server logs for details."]);
                }
            } else {
                error_log("stop_app: App in {$folderName} successfully stopped (either gracefully or was already off). Cleaning up PID file.");
                if (file_exists($pidFile)) {
                    unlink($pidFile);
                }
                echo json_encode(['status' => 'success', 'message' => "App in {$folderName} stopped."]);
            }
            break;

        case 'stop_all_apps':
            $stoppedCount = 0;
            $failedCount = 0;
            $messages = [];

            if (is_dir($pidsDir)) {
                foreach (scandir($pidsDir) as $pidFileName) {
                    if (pathinfo($pidFileName, PATHINFO_EXTENSION) === 'json') {
                        $folderName = pathinfo($pidFileName, PATHINFO_FILENAME);
                        $pidFile = $pidsDir . DIRECTORY_SEPARATOR . $pidFileName;

                        $pidInfo = json_decode(file_get_contents($pidFile), true);
                        if ($pidInfo && isset($pidInfo['port'])) {
                            $port = $pidInfo['port'];
                            $pid = getPidByPort($port);

                            if ($pid && isProcessRunning($pid)) {
                                error_log("stop_all_apps: Attempting to stop app '{$folderName}' (PID: {$pid}, Port: {$port})");
                                if (killProcess($pid)) {
                                    unlink($pidFile);
                                    $stoppedCount++;
                                    $messages[] = "App '{$folderName}' stopped.";
                                } else {
                                    $failedCount++;
                                    $messages[] = "Failed to stop app '{$folderName}'.";
                                }
                            } else {
                                unlink($pidFile);
                                $messages[] = "Cleaned up stale PID file for '{$folderName}'.";
                            }
                        } else {
                            unlink($pidFile);
                            $messages[] = "Cleaned up invalid PID file for '{$folderName}'.";
                        }
                    }
                }
            }

            if ($stoppedCount > 0 || $failedCount > 0) {
                echo json_encode([
                    'status' => 'success',
                    'message' => "Stopped {$stoppedCount} apps, failed to stop {$failedCount} apps.",
                    'details' => $messages
                ]);
            } else {
                echo json_encode(['status' => 'info', 'message' => 'No Python apps were found running to stop.']);
            }
            break;

        case 'install_requirements':
            $input = json_decode(file_get_contents('php://input'), true);
            $folderName = $input['folder_name'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;
            $requirementsFilePath = $folderPath . DIRECTORY_SEPARATOR . 'requirements.txt';

            if (!file_exists($requirementsFilePath)) {
                echo json_encode(['status' => 'error', 'message' => "requirements.txt not found in {$folderName}."]);
                break;
            }

            if (!$pythonExecutable) {
                echo json_encode(['status' => 'error', 'message' => 'Python executable not found on the server. Cannot install requirements.']);
                break;
            }

            $command = escapeshellarg($pythonExecutable) . " -m pip install -r " . escapeshellarg($requirementsFilePath);

            if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
                $fullCommand = "cd /D " . escapeshellarg($folderPath) . " && " . $command . " 2>&1";
            } else {
                $fullCommand = "cd " . escapeshellarg($folderPath) . " && " . $command . " 2>&1";
            }

            error_log("install_requirements: Executing command: {$fullCommand}");
            exec($fullCommand, $output, $return_var);
            error_log("install_requirements: Command output: " . implode("\n", $output));
            error_log("install_requirements: Return var: {$return_var}");

            if ($return_var === 0) {
                echo json_encode(['status' => 'success', 'message' => "Requirements installed successfully for {$folderName}."]);
            } else {
                echo json_encode(['status' => 'error', 'message' => "Failed to install requirements for {$folderName}. Output: " . implode("\n", $output)]);
            }
            break;

        case 'run_install_script':
            $input = json_decode(file_get_contents('php://input'), true);
            $folderName = $input['folder_name'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;
            $installScriptPath = $folderPath . DIRECTORY_SEPARATOR . 'install.sh';

            if (!file_exists($installScriptPath)) {
                echo json_encode(['status' => 'error', 'message' => "install.sh not found in {$folderName}."]);
                break;
            }

            if (strtoupper(substr(PHP_OS, 0, 3)) !== 'WIN') {
                chmod($installScriptPath, 0755);
            }

            $command = "bash " . escapeshellarg($installScriptPath);

            if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
                $fullCommand = "cd /D " . escapeshellarg($folderPath) . " && " . $command . " 2>&1";
            } else {
                $fullCommand = "cd " . escapeshellarg($folderPath) . " && " . $command . " 2>&1";
            }

            error_log("run_install_script: Executing command: {$fullCommand}");
            exec($fullCommand, $output, $return_var);
            error_log("run_install_script: Command output: " . implode("\n", $output));
            error_log("run_install_script: Return var: {$return_var}");

            if ($return_var === 0) {
                echo json_encode(['status' => 'success', 'message' => "install.sh executed successfully for {$folderName}."]);
            } else {
                echo json_encode(['status' => 'error', 'message' => "Failed to execute install.sh for {$folderName}. Output: " . implode("\n", $output)]);
            }
            break;

        case 'save_settings':
            $input = json_decode(file_get_contents('php://input'), true);
            $showCover = $input['showCover'] ?? true;
            $enableCardAnimation = $input['enableCardAnimation'] ?? true;
            $openInIframe = $input['openInIframe'] ?? false;
            $showFullUrl = $input['showFullUrl'] ?? false;
            $enableTaskbar = $input['enableTaskbar'] ?? false;

            $settings = [
                'showCover' => (bool)$showCover,
                'enableCardAnimation' => (bool)$enableCardAnimation,
                'openInIframe' => (bool)$openInIframe,
                'showFullUrl' => (bool)$showFullUrl,
                'enableTaskbar' => (bool)$enableTaskbar
            ];
            if (saveSettings($settings)) {
                echo json_encode(['status' => 'success', 'message' => 'Settings saved successfully.']);
            } else {
                echo json_encode(['status' => 'error', 'message' => 'Failed to save settings.']);
            }
            break;

        case 'get_settings':
            echo json_encode(getSettings());
            break;

        case 'upload_cover_image':
            $folderName = $_POST['folder_name'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $targetDir = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName . DIRECTORY_SEPARATOR;

            if (!is_dir($targetDir)) {
                if (!mkdir($targetDir, 0777, true)) {
                    echo json_encode(['status' => 'error', 'message' => 'Target folder does not exist and could not be created.']);
                    break;
                }
            }

            if (!isset($_FILES['cover_image']) || $_FILES['cover_image']['error'] !== UPLOAD_ERR_OK) {
                $error_message = 'No file uploaded or upload error. Error code: ' . ($_FILES['cover_image']['error'] ?? 'N/A');
                error_log("Upload error for {$folderName}: {$error_message}");
                echo json_encode(['status' => 'error', 'message' => $error_message]);
                break;
            }

            $file = $_FILES['cover_image'];
            $fileName = 'cover.png';
            $targetFilePath = $targetDir . $fileName;
            
            $finfo = new finfo(FILEINFO_MIME_TYPE);
            $fileType = $finfo->file($file['tmp_name']);

            $allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
            if (!in_array($fileType, $allowedTypes)) {
                echo json_encode(['status' => 'error', 'message' => 'Invalid file type. Only JPG, PNG, GIF, WEBP are allowed. Detected: ' . $fileType]);
                break;
            }

            if ($file['size'] > 5 * 1024 * 1024) {
                echo json_encode(['status' => 'error', 'message' => 'File size exceeds 5MB limit.']);
                break;
            }

            if (move_uploaded_file($file['tmp_name'], $targetFilePath)) {
                echo json_encode(['status' => 'success', 'message' => 'Cover image uploaded successfully.']);
            } else {
                error_log("Failed to move uploaded file for {$folderName} from {$file['tmp_name']} to {$targetFilePath}. Check directory permissions.");
                echo json_encode(['status' => 'error', 'message' => 'Failed to move uploaded file.']);
            }
            break;

        case 'create_project':
            $input = json_decode(file_get_contents('php://input'), true);

            $projectName = trim($input['project_name'] ?? '');
            $appPyCode = $input['app_code'] ?? '';
            $indexHtmlCode = $input['html_code'] ?? '';
            $categoryName = trim($input['category_name'] ?? '');
            $requirementsTxtCode = $input['requirements_code'] ?? '';
            $installScriptCode = $input['install_script_code'] ?? '';
            $tagsCode = trim($input['tags_code'] ?? '');
            $guiPyCode = $input['gui_py_code'] ?? '';
            $sqlmapExamplesCode = $input['sqlmap_examples_code'] ?? '';
            $notesCode = $input['notes_code'] ?? '';
            // NEW: Get screen.txt content
            $screenTxtCode = $input['screen_txt_code'] ?? '';


            if (empty($projectName)) {
                echo json_encode(['status' => 'error', 'message' => 'Project name cannot be empty.']);
                break;
            }

            $projectName = preg_replace('/[^a-zA-Z0-9_-]/', '', $projectName);
            if (empty($projectName)) {
                echo json_encode(['status' => 'error', 'message' => 'Invalid project name after sanitization.']);
                break;
            }

            $projectPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $projectName;
            $templatesPath = $projectPath . DIRECTORY_SEPARATOR . 'templates';
            $categoryFilePath = $projectPath . DIRECTORY_SEPARATOR . 'category.txt';
            $appPyFilePath = $projectPath . DIRECTORY_SEPARATOR . 'app.py';
            $indexHtmlFilePath = $templatesPath . DIRECTORY_SEPARATOR . 'index.html';
            $requirementsFilePath = $projectPath . DIRECTORY_SEPARATOR . 'requirements.txt';
            $installScriptPath = $projectPath . DIRECTORY_SEPARATOR . 'install.sh';
            $tagsFilePath = $projectPath . DIRECTORY_SEPARATOR . 'tags.txt';
            $guiPyFilePath = $projectPath . DIRECTORY_SEPARATOR . 'gui.py';
            $sqlmapExamplesFilePath = $projectPath . DIRECTORY_SEPARATOR . 'examples.txt';
            $notesFilePath = $projectPath . DIRECTORY_SEPARATOR . NOTES_FILE_NAME;
            // NEW: Path for screen.txt
            $screenFilePath = $projectPath . DIRECTORY_SEPARATOR . SCREEN_FILE_NAME;


            if (is_dir($projectPath)) {
                echo json_encode(['status' => 'error', 'message' => "Project folder '{$projectName}' already exists. Please choose a different name."]);
                break;
            }

            if (!mkdir($projectPath, 0777, true)) {
                echo json_encode(['status' => 'error', 'message' => "Failed to create project directory: {$projectPath}."]);
                break;
            }

            if (!mkdir($templatesPath, 0777, true)) {
                rrmdir($projectPath);
                echo json_encode(['status' => 'error', 'message' => "Failed to create templates directory: {$templatesPath}."]);
                break;
            }

            if (file_put_contents($appPyFilePath, $appPyCode) === false) {
                rrmdir($projectPath);
                echo json_encode(['status' => 'error', 'message' => "Failed to save app.py for project '{$projectName}'."]);
                break;
            }

            if (file_put_contents($indexHtmlFilePath, $indexHtmlCode) === false) {
                rrmdir($projectPath);
                echo json_encode(['status' => 'error', 'message' => "Failed to save index.html for project '{$projectName}'."]);
                break;
            }

            if (!empty($requirementsTxtCode)) {
                if (file_put_contents($requirementsFilePath, $requirementsTxtCode) === false) {
                    error_log("Failed to save requirements.txt for project '{$projectName}'.");
                }
            }

            if (!empty($installScriptCode)) {
                if (file_put_contents($installScriptPath, $installScriptCode) === false) {
                    error_log("Failed to save install.sh for project '{$projectName}'.");
                } else {
                    if (strtoupper(substr(PHP_OS, 0, 3)) !== 'WIN') {
                        chmod($installScriptPath, 0755);
                    }
                }
            }

            if (!empty($categoryName)) {
                if (file_put_contents($categoryFilePath, $categoryName) === false) {
                    error_log("Failed to save category.txt for project '{$projectName}'.");
                }
            }

            if (!empty($tagsCode)) {
                if (file_put_contents($tagsFilePath, $tagsCode) === false) {
                    error_log("Failed to save tags.txt for project '{$projectName}'.");
                }
            }

            if (!empty($guiPyCode)) {
                if (file_put_contents($guiPyFilePath, $guiPyCode) === false) {
                    error_log("Failed to save gui.py for project '{$projectName}'.");
                }
            }

            if (!empty($sqlmapExamplesCode)) {
                if (file_put_contents($sqlmapExamplesFilePath, $sqlmapExamplesCode) === false) {
                    error_log("Failed to save examples.txt for project '{$projectName}'.");
                }
            }

            if (!empty($notesCode)) {
                if (file_put_contents($notesFilePath, $notesCode) === false) {
                    error_log("Failed to save notes.txt for project '{$projectName}'.");
                }
            }

            // NEW: Save screen.txt
            if (!empty($screenTxtCode)) {
                if (file_put_contents($screenFilePath, $screenTxtCode) === false) {
                    error_log("Failed to save screen.txt for project '{$projectName}'.");
                }
            }

            echo json_encode(['status' => 'success', 'message' => "Project '{$projectName}' created successfully!"]);
            break;

        case 'get_folder_content':
            $folderName = $_GET['folder_name'] ?? '';
            $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;

            $files = [
                'app_py' => $folderPath . DIRECTORY_SEPARATOR . 'app.py',
                'index_html' => $folderPath . DIRECTORY_SEPARATOR . 'templates' . DIRECTORY_SEPARATOR . 'index.html',
                'requirements_txt' => $folderPath . DIRECTORY_SEPARATOR . 'requirements.txt',
                'install_sh' => $folderPath . DIRECTORY_SEPARATOR . 'install.sh',
                'category_txt' => $folderPath . DIRECTORY_SEPARATOR . 'category.txt',
                'tags_txt' => $folderPath . DIRECTORY_SEPARATOR . 'tags.txt',
                'gui_py' => $folderPath . DIRECTORY_SEPARATOR . 'gui.py',
                'sqlmap_examples_txt' => $folderPath . DIRECTORY_SEPARATOR . 'examples.txt',
                'notes_txt' => $folderPath . DIRECTORY_SEPARATOR . NOTES_FILE_NAME,
                // NEW: Add screen.txt to files to fetch
                'screen_txt' => $folderPath . DIRECTORY_SEPARATOR . SCREEN_FILE_NAME
            ];

            $content = [];
            foreach ($files as $key => $path) {
                $content[$key] = file_exists($path) ? file_get_contents($path) : '';
            }
            echo json_encode(['status' => 'success', 'content' => $content]);
            break;

        case 'save_folder_content':
            $input = json_decode(file_get_contents('php://input'), true);

            $folderName = $input['folder_name'] ?? '';
            $appPyCode = $input['app_py'] ?? '';
            $indexHtmlCode = $input['index_html'] ?? '';
            $requirementsTxtCode = $input['requirements_txt'] ?? '';
            $installScriptCode = $input['install_sh'] ?? '';
            $categoryName = $input['category_txt'] ?? '';
            $tagsContent = $input['tags_txt'] ?? '';
            $guiPyCode = $input['gui_py'] ?? '';
            $sqlmapExamplesCode = $input['sqlmap_examples_txt'] ?? '';
            $notesCode = $input['notes_txt'] ?? '';
            // NEW: Get screen.txt content
            $screenTxtCode = $input['screen_txt'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;
            $templatesPath = $folderPath . DIRECTORY_SEPARATOR . 'templates';

            if (!is_dir($folderPath)) {
                mkdir($folderPath, 0777, true);
            }
            if (!is_dir($templatesPath)) {
                mkdir($templatesPath, 0777, true);
            }

            $success = true;
            $messages = [];

            if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'app.py', $appPyCode) === false) {
                $success = false;
                $messages[] = 'Failed to save app.py.';
            }

            if (file_put_contents($templatesPath . DIRECTORY_SEPARATOR . 'index.html', $indexHtmlCode) === false) {
                $success = false;
                $messages[] = 'Failed to save index.html.';
            }

            if (!empty($requirementsTxtCode)) {
                if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'requirements.txt', $requirementsTxtCode) === false) {
                    $messages[] = 'Failed to save requirements.txt.';
                }
            } else {
                if (file_exists($folderPath . DIRECTORY_SEPARATOR . 'requirements.txt')) {
                    unlink($folderPath . DIRECTORY_SEPARATOR . 'requirements.txt');
                }
            }

            if (!empty($installScriptCode)) {
                if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'install.sh', $installScriptCode) === false) {
                    $messages[] = 'Failed to save install.sh.';
                } else {
                    if (strtoupper(substr(PHP_OS, 0, 3)) !== 'WIN') {
                        chmod($folderPath . DIRECTORY_SEPARATOR . 'install.sh', 0755);
                    }
                }
            } else {
                if (file_exists($folderPath . DIRECTORY_SEPARATOR . 'install.sh')) {
                    unlink($folderPath . DIRECTORY_SEPARATOR . 'install.sh');
                }
            }

            if (!empty($categoryName)) {
                if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'category.txt', $categoryName) === false) {
                    $messages[] = 'Failed to save category.txt.';
                }
            } else {
                if (file_exists($folderPath . DIRECTORY_SEPARATOR . 'category.txt')) {
                    unlink($folderPath . DIRECTORY_SEPARATOR . 'category.txt');
                }
            }

            if (!empty($tagsContent)) {
                if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'tags.txt', $tagsContent) === false) {
                    $messages[] = 'Failed to save tags.txt.';
                }
            } else {
                if (file_exists($folderPath . DIRECTORY_SEPARATOR . 'tags.txt')) {
                    unlink($folderPath . DIRECTORY_SEPARATOR . 'tags.txt');
                }
            }

            if (!empty($guiPyCode)) {
                if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'gui.py', $guiPyCode) === false) {
                    $messages[] = 'Failed to save gui.py.';
                }
            } else {
                if (file_exists($folderPath . DIRECTORY_SEPARATOR . 'gui.py')) {
                    unlink($folderPath . DIRECTORY_SEPARATOR . 'gui.py');
                }
            }

            if (!empty($sqlmapExamplesCode)) {
                if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'examples.txt', $sqlmapExamplesCode) === false) {
                    $messages[] = 'Failed to save examples.txt.';
                }
            } else {
                if (file_exists($folderPath . DIRECTORY_SEPARATOR . 'examples.txt')) {
                    unlink($folderPath . DIRECTORY_SEPARATOR . 'examples.txt');
                }
            }

            if (!empty($notesCode)) {
                if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . NOTES_FILE_NAME, $notesCode) === false) {
                    $messages[] = 'Failed to save ' . NOTES_FILE_NAME . '.';
                }
            } else {
                if (file_exists($folderPath . DIRECTORY_SEPARATOR . NOTES_FILE_NAME)) {
                    unlink($folderPath . DIRECTORY_SEPARATOR . NOTES_FILE_NAME);
                }
            }

            // NEW: Save screen.txt content
            $screenFilePath = $folderPath . DIRECTORY_SEPARATOR . SCREEN_FILE_NAME;
            if (!empty($screenTxtCode)) {
                if (file_put_contents($screenFilePath, $screenTxtCode) === false) {
                    $messages[] = 'Failed to save screen.txt.';
                }
            } else {
                if (file_exists($screenFilePath)) {
                    unlink($screenFilePath);
                }
            }

            if ($success && empty($messages)) {
                echo json_encode(['status' => 'success', 'message' => "Folder '{$folderName}' content updated successfully!"]);
            } else {
                echo json_encode(['status' => 'error', 'message' => "Failed to update folder '{$folderName}' content. Details: " . implode(", ", $messages)]);
            }
            break;

        case 'delete_project':
            $input = json_decode(file_get_contents('php://input'), true);
            $folderName = $input['folder_name'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;
            $pidFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '.json';

            if (!is_dir($folderPath)) {
                echo json_encode(['status' => 'error', 'message' => "Project folder '{$folderName}' not found."]);
                break;
            }

            $pythonAppFilePath = $folderPath . DIRECTORY_SEPARATOR . 'app.py';
            if (file_exists($pythonAppFilePath) && file_exists($pidFile)) {
                $pidInfo = json_decode(file_get_contents($pidFile), true);
                if ($pidInfo && isset($pidInfo['port'])) {
                    $port = $pidInfo['port'];
                    $pid = getPidByPort($port);
                    if ($pid && isProcessRunning($pid)) {
                        error_log("delete_project: Stopping running app '{$folderName}' before deletion.");
                        $shutdownUrl = "http://127.0.0.1:{$port}/shutdown";
                        @file_get_contents($shutdownUrl, false, stream_context_create(['http' => ['method' => 'POST', 'header' => 'Content-type: application/json', 'content' => json_encode(['action' => 'shutdown']), 'timeout' => 2, 'ignore_errors' => true]]));
                        sleep(1);
                        $currentPidAfterShutdown = getPidByPort($port);
                        if ($currentPidAfterShutdown && isProcessRunning($currentPidAfterShutdown)) {
                            killProcess($currentPidAfterShutdown);
                        }
                    }
                }
                if (file_exists($pidFile)) {
                    unlink($pidFile);
                }
            }

            if (rrmdir($folderPath)) {
                echo json_encode(['status' => 'success', 'message' => "Project '{$folderName}' deleted successfully."]);
            } else {
                echo json_encode(['status' => 'error', 'message' => "Failed to delete project '{$folderName}'. Check directory permissions."]);
            }
            break;

        case 'open_gui_py':
            $input = json_decode(file_get_contents('php://input'), true);
            $folderName = $input['folder_name'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;
            $guiPyFilePath = $folderPath . DIRECTORY_SEPARATOR . 'gui.py';

            if (!file_exists($guiPyFilePath)) {
                echo json_encode(['status' => 'error', 'message' => "gui.py not found in {$folderName}."]);
                break;
            }

            if (!$pythonExecutable) {
                echo json_encode(['status' => 'error', 'message' => 'Python executable not found on the server. Cannot open GUI.']);
                break;
            }

            $command = escapeshellarg($pythonExecutable) . " " . escapeshellarg($guiPyFilePath);

            if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
                $fullCommand = "start /B " . $command . " > NUL 2>&1";
            } else {
                $fullCommand = "nohup " . $command . " > /dev/null 2>&1 &";
            }

            error_log("open_gui_py: Executing command: {$fullCommand}");
            exec($fullCommand, $output, $return_var);
            error_log("open_gui_py: Command execution returned: {$return_var}. Output: " . implode("\n", $output));

            if ($return_var === 0) {
                echo json_encode(['status' => 'success', 'message' => "GUI.py opened successfully for {$folderName}."]);
            } else {
                echo json_encode(['status' => 'error', 'message' => "Failed to open GUI.py for {$folderName}. Return Var: {$return_var}. Output: " . implode("\n", $output)]);
            }
            break;

        case 'open_terminal':
            $input = json_decode(file_get_contents('php://input'), true);
            $folderName = $input['folder_name'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;

            if (!is_dir($folderPath)) {
                echo json_encode(['status' => 'error', 'message' => "Folder '{$folderName}' not found."]);
                break;
            }

            if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
                $fullCommand = "start cmd /K \"cd /D " . escapeshellarg($folderPath) . "\"";
            } else {
                $fullCommand = "gnome-terminal --working-directory=" . escapeshellarg($folderPath) . " > /dev/null 2>&1 &";
            }

            error_log("open_terminal: Executing command: {$fullCommand}");
            exec($fullCommand, $output, $return_var);
            error_log("open_terminal: Command execution returned: {$return_var}. Output: " . implode("\n", $output));

            if ($return_var === 0) {
                echo json_encode(['status' => 'success', 'message' => "Terminal opened in '{$folderName}'."]);
            } else {
                echo json_encode(['status' => 'error', 'message' => "Failed to open terminal for '{$folderName}'. Return Var: {$return_var}. Output: " . implode("\n", $output)]);
            }
            break;

        case 'open_explorer':
            $input = json_decode(file_get_contents('php://input'), true);
            $folderName = $input['folder_name'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $folderPath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName;

            if (!is_dir($folderPath)) {
                echo json_encode(['status' => 'error', 'message' => "Folder '{$folderName}' not found."]);
                break;
            }

            if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
                $fullCommand = "start explorer " . escapeshellarg($folderPath);
            } else {
                $fullCommand = "xdg-open " . escapeshellarg($folderPath) . " > /dev/null 2>&1 &";
            }

            error_log("open_explorer: Executing command: {$fullCommand}");
            exec($fullCommand, $output, $return_var);
            error_log("open_explorer: Command execution returned: {$return_var}. Output: " . implode("\n", $output));

            if ($return_var === 0) {
                echo json_encode(['status' => 'success', 'message' => "Folder '{$folderName}' opened in file explorer."]);
            } else {
                echo json_encode(['status' => 'error', 'message' => "Failed to open file explorer for '{$folderName}'. Return Var: {$return_var}. Output: " . implode("\n", $output)]);
            }
            break;

        case 'get_sqlmap_examples':
            $folderName = $_GET['folder_name'] ?? '';
            $examplesFilePath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName . DIRECTORY_SEPARATOR . 'examples.txt';

            if (!file_exists($examplesFilePath)) {
                echo json_encode(['status' => 'error', 'message' => 'SQLMap examples file not found.']);
                break;
            }

            $content = file_get_contents($examplesFilePath);
            $examples = json_decode($content, true);

            if (json_last_error() !== JSON_ERROR_NONE) {
                echo json_encode(['status' => 'error', 'message' => 'Failed to parse SQLMap examples file. Invalid JSON.']);
                break;
            }

            echo json_encode(['status' => 'success', 'examples' => $examples]);
            break;

        case 'get_notes_content':
            $folderName = $_GET['folder_name'] ?? '';
            $notesFilePath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName . DIRECTORY_SEPARATOR . NOTES_FILE_NAME;

            if (!file_exists($notesFilePath)) {
                echo json_encode(['status' => 'success', 'content' => '', 'message' => 'notes.txt not found.']);
                break;
            }

            $content = file_get_contents($notesFilePath);
            echo json_encode(['status' => 'success', 'content' => $content]);
            break;

        case 'save_notes_content':
            $input = json_decode(file_get_contents('php://input'), true);
            $folderName = $input['folder_name'] ?? '';
            $notesContent = $input['notes_content'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $notesFilePath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName . DIRECTORY_SEPARATOR . NOTES_FILE_NAME;

            if (!empty($notesContent)) {
                if (file_put_contents($notesFilePath, $notesContent) === false) {
                    echo json_encode(['status' => 'error', 'message' => 'Failed to save notes.txt.']);
                    break;
                }
            } else {
                if (file_exists($notesFilePath)) {
                    unlink($notesFilePath);
                }
            }
            echo json_encode(['status' => 'success', 'message' => 'notes.txt saved successfully.']);
            break;

        // NEW: API endpoint to get screen.txt content
        case 'get_screen_content':
            $folderName = $_GET['folder_name'] ?? '';
            $screenFilePath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName . DIRECTORY_SEPARATOR . SCREEN_FILE_NAME;

            if (!file_exists($screenFilePath)) {
                echo json_encode(['status' => 'success', 'content' => '', 'message' => 'screen.txt not found.']);
                break;
            }

            $content = file_get_contents($screenFilePath);
            echo json_encode(['status' => 'success', 'content' => $content]);
            break;

        // NEW: API endpoint to save screen.txt content
        case 'save_screen_content':
            $input = json_decode(file_get_contents('php://input'), true);
            $folderName = $input['folder_name'] ?? '';
            $screenContent = $input['screen_content'] ?? '';

            if (empty($folderName)) {
                echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
                break;
            }

            $screenFilePath = $databaseBaseDir . DIRECTORY_SEPARATOR . $folderName . DIRECTORY_SEPARATOR . SCREEN_FILE_NAME;

            if (!empty($screenContent)) {
                if (file_put_contents($screenFilePath, $screenContent) === false) {
                    echo json_encode(['status' => 'error', 'message' => 'Failed to save screen.txt.']);
                    break;
                }
            } else {
                if (file_exists($screenFilePath)) {
                    unlink($screenFilePath);
                }
            }
            echo json_encode(['status' => 'success', 'message' => 'screen.txt saved successfully.']);
            break;

        default:
            // No action specified, or invalid action, let index.php render the HTML
            // This case is now handled by the initial check in index.php
            break;
    }
}

