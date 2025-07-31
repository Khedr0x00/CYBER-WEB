<?php
// Set error reporting for development
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// Define base directories
$scriptsBaseDir = __DIR__ . DIRECTORY_SEPARATOR . 'scripts';
$pidsDir = __DIR__ . DIRECTORY_SEPARATOR . 'pids';
$nextPortFile = __DIR__ . DIRECTORY_SEPARATOR . 'next_port.txt';
const SETTINGS_FILE = __DIR__ . DIRECTORY_SEPARATOR . 'settings.json'; // Define settings file path

// Define the web server's port for PHP app URLs.
// Adjust this if your XAMPP/Apache is running on a different port (e.g., 8080).
// For PHP's built-in server (php -S localhost:8000), it's 8000.
// For default Apache, it's 80.
const WEB_SERVER_PORT = 80; // Assuming default HTTP port for PHP apps

// Ensure necessary directories exist and are writable
if (!is_dir($scriptsBaseDir)) {
    mkdir($scriptsBaseDir, 0777, true);
}
if (!is_dir($pidsDir)) {
    mkdir($pidsDir, 0777, true);
}
// Check writability of pids directory
$pidsDirWritable = is_writable($pidsDir);


// Initialize next available port if file doesn't exist
if (!file_exists($nextPortFile)) {
    file_put_contents($nextPortFile, '5001'); // Starting port for Python apps
}

// Initialize settings file if it doesn't exist
if (!file_exists(SETTINGS_FILE)) {
    // Add enableCardAnimation with a default value of true
    file_put_contents(SETTINGS_FILE, json_encode(['showCover' => true, 'enableCardAnimation' => true], JSON_PRETTY_PRINT));
}


/**
 * Helper function to get the next available port and increment the counter.
 * @param string $file The path to the next_port.txt file.
 * @return int The next available port.
 */
function getNextAvailablePort($file) {
    $fp = fopen($file, "r+");
    if (flock($fp, LOCK_EX)) {
        $port = (int)fread($fp, filesize($file));
        ftruncate($fp, 0);
        rewind($fp);
        fwrite($fp, $port + 1);
        fflush($fp);
        flock($fp, LOCK_UN);
    } else {
        error_log("Failed to acquire lock on {$file}. Proceeding without lock (less safe).");
        $port = (int)file_get_contents($file);
        file_put_contents($file, $port + 1);
    }
    fclose($fp);
    return $port;
}

/**
 * Helper function to find the PID of a process listening on a given port.
 * @param int $port The port to check.
 * @return int|null The PID if found, null otherwise.
 */
function getPidByPort($port) {
    error_log("getPidByPort: Checking port {$port}");
    $pid = null;
    if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
        $command = "netstat -ano | findstr LISTEN | findstr :" . escapeshellarg($port);
        exec($command, $output, $return_var);
        error_log("getPidByPort (Windows) Command: {$command}");
        error_log("getPidByPort (Windows) Output: " . implode("\n", $output));
        error_log("getPidByPort (Windows) Return Var: {$return_var}");

        if ($return_var === 0) {
            foreach ($output as $line) {
                if (preg_match('/\s+(\d+)$/', $line, $matches)) {
                    $pid = (int)$matches[1];
                    error_log("getPidByPort (Windows): Found PID {$pid} for port {$port}");
                    break;
                }
            }
        }
    } else {
        $command = "lsof -ti:" . escapeshellarg($port);
        exec($command, $output, $return_var);
        error_log("getPidByPort (Unix) Command: {$command}");
        error_log("getPidByPort (Unix) Output: " . implode("\n", $output));
        error_log("getPidByPort (Unix) Return Var: {$return_var}");

        if ($return_var === 0 && !empty($output)) {
            $pid = (int)$output[0];
            error_log("getPidByPort (Unix): Found PID {$pid} for port {$port}");
        }
    }
    if ($pid === null) {
        error_log("getPidByPort: No PID found for port {$port}");
    }
    return $pid;
}

/**
 * Helper function to check if a process with a given PID is running.
 * @param int $pid The PID to check.
 * @return bool True if running, false otherwise.
 */
function isProcessRunning($pid) {
    error_log("isProcessRunning: Checking PID {$pid}");
    if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
        $command = "tasklist /FI \"PID eq " . escapeshellarg($pid) . "\"";
        exec($command, $output, $return_var);
        error_log("isProcessRunning (Windows) Command: {$command}");
        error_log("isProcessRunning (Windows) Output: " . implode("\n", $output));
        error_log("isProcessRunning (Windows) Return Var: {$return_var}");

        foreach ($output as $line) {
            if (strpos($line, (string)$pid) !== false && strpos($line, 'PID') === false) {
                error_log("isProcessRunning (Windows): PID {$pid} is running.");
                return true;
            }
        }
        error_log("isProcessRunning (Windows): PID {$pid} is NOT running.");
        return false;
    } else {
        exec("kill -0 " . escapeshellarg($pid) . " 2>&1", $output, $return_var);
        error_log("isProcessRunning (Unix) Command: kill -0 " . escapeshellarg($pid));
        error_log("isProcessRunning (Unix) Return Var: {$return_var}");
        if ($return_var === 0) {
            error_log("isProcessRunning (Unix): PID {$pid} is running.");
            return true;
        }
        error_log("isProcessRunning (Unix): PID {$pid} is NOT running.");
        return false;
    }
}

/**
 * Helper function to kill a process by PID.
 * @param int $pid The PID to kill.
 * @return bool True on success, false on failure.
 */
function killProcess($pid) {
    error_log("killProcess: Attempting to kill PID {$pid}");
    if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
        $command = "taskkill /F /T /PID " . escapeshellarg($pid) . " 2>&1";
        exec($command, $output, $return_var);
        error_log("killProcess (Windows) Command: {$command}");
        error_log("killProcess (Windows) Output: " . implode("\n", $output));
        error_log("killProcess (Windows) Return Var: {$return_var}");
        if ($return_var === 0) {
            error_log("killProcess (Windows): Successfully killed PID {$pid}.");
            return true;
        } else {
            error_log("killProcess (Windows): Failed to kill PID {$pid}.");
            return false;
        }
    } else {
        // Attempt to kill the process group first to catch child processes
        $command = "kill -9 -" . escapeshellarg($pid) . " 2>&1";
        exec($command, $output, $return_var);
        error_log("killProcess (Unix) Command: {$command}");
        error_log("killProcess (Unix) Output: " . implode("\n", $output));
        error_log("killProcess (Unix) Return Var: {$return_var}");

        if ($return_var === 0) {
            error_log("killProcess (Unix): Successfully killed PID {$pid} (or its process group).");
            return true;
        } else {
            error_log("killProcess (Unix): Process group kill failed for PID {$pid}. Trying individual kill.");
            $command = "kill -9 " . escapeshellarg($pid) . " 2>&1";
            exec($command, $output, $return_var);
            error_log("killProcess (Unix) Fallback Command: {$command}");
            error_log("killProcess (Unix) Fallback Output: " . implode("\n", $output));
            error_log("killProcess (Unix) Fallback Return Var: {$return_var}");
            if ($return_var === 0) {
                error_log("killProcess (Unix): Successfully killed individual PID {$pid}.");
                return true;
            } else {
                error_log("killProcess (Unix): Failed to kill PID {$pid} even with fallback.");
                return false;
            }
        }
    }
}

/**
 * Helper function to find the absolute path of the python executable.
 * @return string|null The path to python executable, or null if not found.
 */
function findPythonExecutable() {
    $pythonPath = null;
    if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
        exec("where python", $output, $return_var);
        if ($return_var === 0 && !empty($output)) {
            $pythonPath = trim($output[0]);
            error_log("findPythonExecutable (Windows): Found Python at {$pythonPath}");
        } else {
            error_log("findPythonExecutable (Windows): Python not found using 'where python'.");
        }
    } else {
        exec("which python", $output, $return_var);
        if ($return_var === 0 && !empty($output)) {
            $pythonPath = trim($output[0]);
            error_log("findPythonExecutable (Unix): Found Python at {$pythonPath}");
        } else {
            error_log("findPythonExecutable (Unix): Python not found using 'which python'.");
        }
    }
    return $pythonPath;
}

// Find python executable once at the start
$pythonExecutable = findPythonExecutable();

/**
 * Function to read settings from settings.json.
 * @return array The settings array.
 */
function getSettings() {
    if (file_exists(SETTINGS_FILE)) {
        $settings = json_decode(file_get_contents(SETTINGS_FILE), true);
        // Ensure default values if settings are missing
        return array_merge(['showCover' => true, 'enableCardAnimation' => true], $settings ?: []);
    }
    // Default settings if file doesn't exist
    return ['showCover' => true, 'enableCardAnimation' => true];
}

/**
 * Function to save settings to settings.json.
 * @param array $settings The settings array to save.
 * @return bool True on success, false on failure.
 */
function saveSettings($settings) {
    return file_put_contents(SETTINGS_FILE, json_encode($settings, JSON_PRETTY_PRINT));
}


// Determine the action based on GET parameter
$action = $_GET['action'] ?? '';

switch ($action) {
    case 'list_folders':
        header('Content-Type: application/json');
        $folders = [];
        if (is_dir($scriptsBaseDir)) {
            foreach (scandir($scriptsBaseDir) as $folderName) {
                if ($folderName === '.' || $folderName === '..') {
                    continue;
                }
                $folderPath = $scriptsBaseDir . DIRECTORY_SEPARATOR . $folderName;
                $pythonAppFilePath = $folderPath . DIRECTORY_SEPARATOR . 'app.py';
                $phpAppFilePath = $folderPath . DIRECTORY_SEPARATOR . 'index.php';
                $requirementsFilePath = $folderPath . DIRECTORY_SEPARATOR . 'requirements.txt'; // Path to requirements.txt
                $installScriptPath = $folderPath . DIRECTORY_SEPARATOR . 'install.sh'; // Path to install.sh
                $categoryFilePath = $folderPath . DIRECTORY_SEPARATOR . 'category.txt'; // Path to category.txt

                $isPythonApp = file_exists($pythonAppFilePath);
                $isPhpApp = file_exists($phpAppFilePath);
                $hasRequirementsFile = file_exists($requirementsFilePath); // Check for requirements.txt
                $hasInstallScript = file_exists($installScriptPath); // Check for install.sh
                $hasCategoryFile = file_exists($categoryFilePath); // Check for category.txt
                $categoryText = '';

                if ($hasCategoryFile) {
                    $categoryText = trim(file_get_contents($categoryFilePath));
                }

                if ($isPythonApp) {
                    $pidFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '.json';
                    $isRunning = false;
                    $port = null;

                    if (file_exists($pidFile)) {
                        $pidInfo = json_decode(file_get_contents($pidFile), true);
                        if ($pidInfo && isset($pidInfo['port'])) {
                            $port = $pidInfo['port'];
                            $currentPid = getPidByPort($port);
                            if ($currentPid && isProcessRunning($currentPid)) {
                                $isRunning = true;
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
                        'has_requirements_file' => $hasRequirementsFile, // Add this flag
                        'has_install_script' => $hasInstallScript, // Add this flag
                        'has_category_file' => $hasCategoryFile, // Add this flag
                        'category_text' => $categoryText // Add category text
                    ];
                } elseif ($isPhpApp) {
                    // PHP apps are always "running" as they are served by the web server
                    // The URL will be relative to the web server's document root
                    $phpAppUrl = (WEB_SERVER_PORT == 80 ? 'http://' : 'http://127.0.0.1:' . WEB_SERVER_PORT . '/') . basename(__DIR__) . '/scripts/' . $folderName . '/index.php';

                    $folders[] = [
                        'name' => $folderName,
                        'type' => 'php',
                        'is_running' => true, // PHP apps are always considered running if their index.php exists
                        'url' => $phpAppUrl, // Provide the direct URL for PHP apps
                        'has_requirements_file' => $hasRequirementsFile, // Add this flag
                        'has_install_script' => $hasInstallScript, // Add this flag
                        'has_category_file' => $hasCategoryFile, // Add this flag
                        'category_text' => $categoryText // Add category text
                    ];
                }
            }
        }
        echo json_encode($folders);
        break;

    case 'start_app':
        header('Content-Type: application/json');
        $input = json_decode(file_get_contents('php://input'), true);
        $folderName = $input['folder_name'] ?? '';

        if (empty($folderName)) {
            echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
            exit;
        }

        $folderPath = $scriptsBaseDir . DIRECTORY_SEPARATOR . $folderName;
        $appFilePath = $folderPath . DIRECTORY_SEPARATOR . 'app.py';

        if (!file_exists($appFilePath)) {
            echo json_encode(['status' => 'error', 'message' => "This is not a Python app or app.py not found in {$folderName}."]);
            exit;
        }

        if (!$pythonExecutable) {
            echo json_encode(['status' => 'error', 'message' => 'Python executable not found on the server. Please ensure Python is installed and in the system\'s PATH.']);
            exit;
        }

        $pidFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '.json';
        $logFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '_output.log';

        // Clear previous log file content to get fresh output
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
                    echo json_encode(['status' => 'info', 'message' => "App in {$folderName} is already running.", 'url' => "http://127.0.0.1:{$port}"]);
                    exit;
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
            // Using `start /B` to run in background, redirecting output to log file
            $fullCommand = "cd /D " . escapeshellarg($folderPath) . " && start /B " . $command . " > " . escapeshellarg($logFile) . " 2>&1";
        } else {
            // Using `nohup` and `&` for background execution on Unix-like systems
            $fullCommand = "cd " . escapeshellarg($folderPath) . " && nohup " . $command . " > " . escapeshellarg($logFile) . " 2>&1 &";
        }

        error_log("start_app: Attempting to execute command: {$fullCommand}");
        exec($fullCommand, $output, $return_var);
        error_log("start_app: Command execution returned: {$return_var}. Output: " . implode("\n", $output));

        // --- Improved process detection with retries ---
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
        // --- End of improved process detection ---

        if ($return_var === 0 && $isActuallyRunning) {
            file_put_contents($pidFile, json_encode(['port' => $port, 'pid' => $currentPidAfterStart])); // Store PID as well
            error_log("start_app: App in {$folderName} successfully started on port {$port} with PID {$currentPidAfterStart}.");
            echo json_encode(['status' => 'success', 'message' => "App in {$folderName} started on port {$port}.", 'url' => $appUrl]);
        } else {
            $errorMessage = "Failed to start app in {$folderName}.";
            if (!$isActuallyRunning) {
                $errorMessage .= " Process not detected running after start attempt.";
            }
            $errorMessage .= " Command: {$fullCommand} Return Var: {$return_var} Output: " . implode("\n", $output) . ". Check {$logFile} for details.";

            $logContent = '';
            if (file_exists($logFile) && filesize($logFile) > 0) {
                $logContent = file_get_contents($logFile);
                $errorMessage .= "\nLog content: " . substr($logContent, -500); // Get last 500 chars of log
            } else {
                $errorMessage .= "\nLog file is empty or not found.";
            }

            // Check for ModuleNotFoundError and suggest action
            if (strpos($logContent, 'ModuleNotFoundError: No module named') !== false) {
                $errorMessage = "Failed to start app in {$folderName}. It appears a required Python module is missing. Please click the 'Install Requirements' icon (download arrow) on the app's card to install dependencies, then try starting the app again.";
                error_log("start_app: ModuleNotFoundError detected for {$folderName}. Suggesting requirements installation.");
            }

            error_log("start_app: " . $errorMessage);
            echo json_encode(['status' => 'error', 'message' => $errorMessage]);
        }
        break;

    case 'stop_app':
        header('Content-Type: application/json');
        $input = json_decode(file_get_contents('php://input'), true);
        $folderName = $input['folder_name'] ?? '';

        if (empty($folderName)) {
            echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
            exit;
        }

        $folderPath = $scriptsBaseDir . DIRECTORY_SEPARATOR . $folderName;
        $appFilePath = $folderPath . DIRECTORY_SEPARATOR . 'app.py';

        if (!file_exists($appFilePath)) {
            echo json_encode(['status' => 'error', 'message' => "This is not a Python app or app.py not found in {$folderName}."]);
            exit;
        }

        $pidFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '.json';
        $logFile = $pidsDir . DIRECTORY_SEPARATOR . $folderName . '_output.log';

        if (!file_exists($pidFile)) {
            error_log("stop_app: No PID file found for {$folderName}. Assuming not running.");
            echo json_encode(['status' => 'info', 'message' => "No running app found for {$folderName} (no PID file)."]);
            exit;
        }

        $pidInfo = json_decode(file_get_contents($pidFile), true);
        if (!$pidInfo || !isset($pidInfo['port'])) {
            error_log("stop_app: Invalid PID file for {$folderName}. Cleaning up.");
            echo json_encode(['status' => 'error', 'message' => "Invalid PID file for {$folderName}. Attempting cleanup."]);
            if (file_exists($pidFile)) {
                unlink($pidFile);
            }
            exit;
        }

        $port = $pidInfo['port'];
        $pid = getPidByPort($port);

        $gracefulShutdownAttempted = false;
        if ($pid && isProcessRunning($pid)) {
            // Attempt graceful shutdown via HTTP POST to /shutdown endpoint
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
            // Use @to suppress warnings from file_get_contents if the server is not reachable
            $result = @file_get_contents($shutdownUrl, false, $context);

            if ($result !== FALSE) {
                // Check HTTP response headers for status code
                $http_response_header_array = $http_response_header;
                $status_line = $http_response_header_array[0];
                preg_match('{HTTP\/\S+\s(\d{3})}', $status_line, $match);
                $status_code = $match[1];
                error_log("stop_app: Graceful shutdown HTTP request to {$shutdownUrl} returned status {$status_code}. Response: {$result}");

                if ($status_code >= 200 && $status_code < 300) {
                    $gracefulShutdownAttempted = true;
                    error_log("stop_app: Graceful shutdown initiated for {$folderName}. Waiting for process to terminate.");
                    sleep(2); // Wait 2 seconds for graceful shutdown
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
        header('Content-Type: application/json');
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
                            // PID file exists but process is not running, clean up
                            unlink($pidFile);
                            $messages[] = "Cleaned up stale PID file for '{$folderName}'.";
                        }
                    } else {
                        // Invalid PID file, clean up
                        unlink($pidFile);
                        $messages[] = "Cleaned up invalid PID file for '{$folderName}'.";
                    }
                }
            }
        }

        if ($stoppedCount > 0 || $failedCount > 0) {
            echo json_encode([
                'status' => 'success', // Even if some fail, overall action was attempted
                'message' => "Stopped {$stoppedCount} apps, failed to stop {$failedCount} apps.",
                'details' => $messages
            ]);
        } else {
            echo json_encode(['status' => 'info', 'message' => 'No Python apps were found running to stop.']);
        }
        break;

    case 'install_requirements': // Action to install requirements
        header('Content-Type: application/json');
        $input = json_decode(file_get_contents('php://input'), true);
        $folderName = $input['folder_name'] ?? '';

        if (empty($folderName)) {
            echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
            exit;
        }

        $folderPath = $scriptsBaseDir . DIRECTORY_SEPARATOR . $folderName;
        $requirementsFilePath = $folderPath . DIRECTORY_SEPARATOR . 'requirements.txt';

        if (!file_exists($requirementsFilePath)) {
            echo json_encode(['status' => 'error', 'message' => "requirements.txt not found in {$folderName}."]);
            exit;
        }

        if (!$pythonExecutable) {
            echo json_encode(['status' => 'error', 'message' => 'Python executable not found on the server. Cannot install requirements.']);
            exit;
        }

        // Construct the pip install command
        // Using `python -m pip install` is more robust than just `pip install`
        $command = escapeshellarg($pythonExecutable) . " -m pip install -r " . escapeshellarg($requirementsFilePath);

        // Change directory to the app folder before running pip install
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

    case 'run_install_script': // New action to run install.sh
        header('Content-Type: application/json');
        $input = json_decode(file_get_contents('php://input'), true);
        $folderName = $input['folder_name'] ?? '';

        if (empty($folderName)) {
            echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
            exit;
        }

        $folderPath = $scriptsBaseDir . DIRECTORY_SEPARATOR . $folderName;
        $installScriptPath = $folderPath . DIRECTORY_SEPARATOR . 'install.sh';

        if (!file_exists($installScriptPath)) {
            echo json_encode(['status' => 'error', 'message' => "install.sh not found in {$folderName}."]);
            exit;
        }

        // Make sure the script is executable (important for Unix-like systems)
        if (strtoupper(substr(PHP_OS, 0, 3)) !== 'WIN') {
            chmod($installScriptPath, 0755); // Make it executable
        }

        // Construct the command to run the install.sh script using bash
        // Change directory to the app folder before running the script
        $command = "bash " . escapeshellarg($installScriptPath);

        if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
            // On Windows, if bash is not in PATH, this might fail.
            // A more robust solution for Windows might involve WSL or Git Bash.
            // For now, assuming bash is accessible if it's a Windows system running such scripts.
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
        header('Content-Type: application/json');
        $input = json_decode(file_get_contents('php://input'), true);
        $showCover = $input['showCover'] ?? true; // Default to true if not provided
        $enableCardAnimation = $input['enableCardAnimation'] ?? true; // New setting, default to true

        $settings = [
            'showCover' => (bool)$showCover,
            'enableCardAnimation' => (bool)$enableCardAnimation // Save the new setting
        ];
        if (saveSettings($settings)) {
            echo json_encode(['status' => 'success', 'message' => 'Settings saved successfully.']);
        } else {
            echo json_encode(['status' => 'error', 'message' => 'Failed to save settings.']);
        }
        exit; // Important to exit after JSON response

    case 'get_settings':
        header('Content-Type: application/json');
        echo json_encode(getSettings());
        exit; // Important to exit after JSON response

    // NEW: Action to handle image uploads for cover.png
    case 'upload_cover_image':
        header('Content-Type: application/json');
        $folderName = $_POST['folder_name'] ?? '';

        if (empty($folderName)) {
            echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
            exit;
        }

        // Define the target directory for the cover image
        $targetDir = $scriptsBaseDir . DIRECTORY_SEPARATOR . $folderName . DIRECTORY_SEPARATOR;

        // Ensure the target directory exists
        if (!is_dir($targetDir)) {
            // Attempt to create the directory if it doesn't exist
            if (!mkdir($targetDir, 0777, true)) {
                echo json_encode(['status' => 'error', 'message' => 'Target folder does not exist and could not be created.']);
                exit;
            }
        }

        // Check if file was uploaded without errors
        if (!isset($_FILES['cover_image']) || $_FILES['cover_image']['error'] !== UPLOAD_ERR_OK) {
            $error_message = 'No file uploaded or upload error. Error code: ' . ($_FILES['cover_image']['error'] ?? 'N/A');
            error_log("Upload error for {$folderName}: {$error_message}");
            echo json_encode(['status' => 'error', 'message' => $error_message]);
            exit;
        }

        $file = $_FILES['cover_image'];
        $fileName = 'cover.png'; // Always save as cover.png
        $targetFilePath = $targetDir . $fileName;
        
        // Use finfo to get the MIME type, which is more reliable than $_FILES['type']
        $finfo = new finfo(FILEINFO_MIME_TYPE);
        $fileType = $finfo->file($file['tmp_name']);

        // Basic validation for image types
        $allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
        if (!in_array($fileType, $allowedTypes)) {
            echo json_encode(['status' => 'error', 'message' => 'Invalid file type. Only JPG, PNG, GIF, WEBP are allowed. Detected: ' . $fileType]);
            exit;
        }

        // File size limit (e.g., 5MB)
        if ($file['size'] > 5 * 1024 * 1024) {
            echo json_encode(['status' => 'error', 'message' => 'File size exceeds 5MB limit.']);
            exit;
        }

        // Move the uploaded file to its final destination
        if (move_uploaded_file($file['tmp_name'], $targetFilePath)) {
            echo json_encode(['status' => 'success', 'message' => 'Cover image uploaded successfully.']);
        } else {
            error_log("Failed to move uploaded file for {$folderName} from {$file['tmp_name']} to {$targetFilePath}. Check directory permissions.");
            echo json_encode(['status' => 'error', 'message' => 'Failed to move uploaded file. Check directory permissions.']);
        }
        exit;

    case 'create_project': // NEW: Action to create a new project
        header('Content-Type: application/json');
        $input = json_decode(file_get_contents('php://input'), true);

        $projectName = trim($input['project_name'] ?? '');
        $appPyCode = $input['app_code'] ?? '';
        $indexHtmlCode = $input['html_code'] ?? '';
        $categoryName = trim($input['category_name'] ?? '');
        $requirementsTxtCode = $input['requirements_code'] ?? '';
        $installScriptCode = $input['install_script_code'] ?? ''; // NEW: Get install.sh code

        if (empty($projectName)) {
            echo json_encode(['status' => 'error', 'message' => 'Project name cannot be empty.']);
            exit;
        }

        // Sanitize project name to be safe for directory names
        $projectName = preg_replace('/[^a-zA-Z0-9_-]/', '', $projectName);
        if (empty($projectName)) {
            echo json_encode(['status' => 'error', 'message' => 'Invalid project name after sanitization.']);
            exit;
        }

        $projectPath = $scriptsBaseDir . DIRECTORY_SEPARATOR . $projectName;
        $templatesPath = $projectPath . DIRECTORY_SEPARATOR . 'templates';
        $categoryFilePath = $projectPath . DIRECTORY_SEPARATOR . 'category.txt';
        $appPyFilePath = $projectPath . DIRECTORY_SEPARATOR . 'app.py';
        $indexHtmlFilePath = $templatesPath . DIRECTORY_SEPARATOR . 'index.html';
        $requirementsFilePath = $projectPath . DIRECTORY_SEPARATOR . 'requirements.txt';
        $installScriptPath = $projectPath . DIRECTORY_SEPARATOR . 'install.sh'; // NEW: Path for install.sh

        // Check if project folder already exists
        if (is_dir($projectPath)) {
            echo json_encode(['status' => 'error', 'message' => "Project folder '{$projectName}' already exists. Please choose a different name."]);
            exit;
        }

        // Create project directory
        if (!mkdir($projectPath, 0777, true)) {
            echo json_encode(['status' => 'error', 'message' => "Failed to create project directory: {$projectPath}."]);
            exit;
        }

        // Create templates directory
        if (!mkdir($templatesPath, 0777, true)) {
            // Clean up project directory if templates creation fails
            rmdir($projectPath);
            echo json_encode(['status' => 'error', 'message' => "Failed to create templates directory: {$templatesPath}."]);
            exit;
        }

        // Save app.py code
        if (file_put_contents($appPyFilePath, $appPyCode) === false) {
            // Clean up created files and directories
            rmdir($templatesPath);
            rmdir($projectPath);
            echo json_encode(['status' => 'error', 'message' => "Failed to save app.py for project '{$projectName}'."]);
            exit;
        }

        // Save index.html code
        if (file_put_contents($indexHtmlFilePath, $indexHtmlCode) === false) {
            // Clean up created files and directories
            unlink($appPyFilePath);
            rmdir($templatesPath);
            rmdir($projectPath);
            echo json_encode(['status' => 'error', 'message' => "Failed to save index.html for project '{$projectName}'."]);
            exit;
        }

        // Save requirements.txt code
        if (!empty($requirementsTxtCode)) {
            if (file_put_contents($requirementsFilePath, $requirementsTxtCode) === false) {
                error_log("Failed to save requirements.txt for project '{$projectName}'.");
            }
        }

        // NEW: Save install.sh code
        if (!empty($installScriptCode)) {
            if (file_put_contents($installScriptPath, $installScriptCode) === false) {
                error_log("Failed to save install.sh for project '{$projectName}'.");
            } else {
                // Make the script executable on Unix-like systems
                if (strtoupper(substr(PHP_OS, 0, 3)) !== 'WIN') {
                    chmod($installScriptPath, 0755);
                }
            }
        }

        // Save category.txt
        if (!empty($categoryName)) {
            if (file_put_contents($categoryFilePath, $categoryName) === false) {
                // Log error but don't fail the whole project creation if category fails
                error_log("Failed to save category.txt for project '{$projectName}'.");
            }
        }

        echo json_encode(['status' => 'success', 'message' => "Project '{$projectName}' created successfully!"]);
        exit;

    case 'get_folder_content': // NEW: Action to get all file content for a folder
        header('Content-Type: application/json');
        $folderName = $_GET['folder_name'] ?? '';
        $folderPath = $scriptsBaseDir . DIRECTORY_SEPARATOR . $folderName;

        $files = [
            'app_py' => $folderPath . DIRECTORY_SEPARATOR . 'app.py',
            'index_html' => $folderPath . DIRECTORY_SEPARATOR . 'templates' . DIRECTORY_SEPARATOR . 'index.html',
            'requirements_txt' => $folderPath . DIRECTORY_SEPARATOR . 'requirements.txt',
            'install_sh' => $folderPath . DIRECTORY_SEPARATOR . 'install.sh',
            'category_txt' => $folderPath . DIRECTORY_SEPARATOR . 'category.txt'
        ];

        $content = [];
        foreach ($files as $key => $path) {
            $content[$key] = file_exists($path) ? file_get_contents($path) : '';
        }
        echo json_encode(['status' => 'success', 'content' => $content]);
        exit;

    case 'save_folder_content': // NEW: Action to save all file content for a folder
        header('Content-Type: application/json');
        $input = json_decode(file_get_contents('php://input'), true);

        $folderName = $input['folder_name'] ?? '';
        $appPyCode = $input['app_py'] ?? '';
        $indexHtmlCode = $input['index_html'] ?? '';
        $requirementsTxtCode = $input['requirements_txt'] ?? '';
        $installScriptCode = $input['install_sh'] ?? '';
        $categoryName = $input['category_txt'] ?? '';

        if (empty($folderName)) {
            echo json_encode(['status' => 'error', 'message' => 'Folder name not provided.']);
            exit;
        }

        $folderPath = $scriptsBaseDir . DIRECTORY_SEPARATOR . $folderName;
        $templatesPath = $folderPath . DIRECTORY_SEPARATOR . 'templates';

        // Ensure folder and templates directories exist
        if (!is_dir($folderPath)) {
            mkdir($folderPath, 0777, true);
        }
        if (!is_dir($templatesPath)) {
            mkdir($templatesPath, 0777, true);
        }

        $success = true;
        $messages = [];

        // Save app.py
        if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'app.py', $appPyCode) === false) {
            $success = false;
            $messages[] = 'Failed to save app.py.';
        }

        // Save index.html
        if (file_put_contents($templatesPath . DIRECTORY_SEPARATOR . 'index.html', $indexHtmlCode) === false) {
            $success = false;
            $messages[] = 'Failed to save index.html.';
        }

        // Save requirements.txt
        if (!empty($requirementsTxtCode)) {
            if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'requirements.txt', $requirementsTxtCode) === false) {
                $messages[] = 'Failed to save requirements.txt.';
            }
        } else {
            // If content is empty, delete the file if it exists
            if (file_exists($folderPath . DIRECTORY_SEPARATOR . 'requirements.txt')) {
                unlink($folderPath . DIRECTORY_SEPARATOR . 'requirements.txt');
            }
        }

        // Save install.sh
        if (!empty($installScriptCode)) {
            if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'install.sh', $installScriptCode) === false) {
                $messages[] = 'Failed to save install.sh.';
            } else {
                if (strtoupper(substr(PHP_OS, 0, 3)) !== 'WIN') {
                    chmod($folderPath . DIRECTORY_SEPARATOR . 'install.sh', 0755);
                }
            }
        } else {
            // If content is empty, delete the file if it exists
            if (file_exists($folderPath . DIRECTORY_SEPARATOR . 'install.sh')) {
                unlink($folderPath . DIRECTORY_SEPARATOR . 'install.sh');
            }
        }

        // Save category.txt
        if (!empty($categoryName)) {
            if (file_put_contents($folderPath . DIRECTORY_SEPARATOR . 'category.txt', $categoryName) === false) {
                $messages[] = 'Failed to save category.txt.';
            }
        } else {
            // If content is empty, delete the file if it exists
            if (file_exists($folderPath . DIRECTORY_SEPARATOR . 'category.txt')) {
                unlink($folderPath . DIRECTORY_SEPARATOR . 'category.txt');
            }
        }


        if ($success && empty($messages)) {
            echo json_encode(['status' => 'success', 'message' => "Folder '{$folderName}' content updated successfully!"]);
        } else {
            echo json_encode(['status' => 'error', 'message' => "Failed to update folder '{$folderName}' content. Details: " . implode(", ", $messages)]);
        }
        exit;

    default:
        // Serve the HTML page with embedded CSS and JS
        header('Content-Type: text/html');
        // Get settings to pass to JavaScript
        $currentSettings = getSettings();
        $enableCardAnimationJs = json_encode($currentSettings['enableCardAnimation']);
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
            <style>
                /* Root variables for colors and theme */
                :root {
                    --primary-color: #4f46e5; /* Indigo 600 */
                    --secondary-color: #6366f1; /* Indigo 500 */
                    --bg-dark: #1f2937; /* Gray 800 */
                    --text-light: #f3f4f6; /* Gray 100 */
                    --card-bg: #374151; /* Gray 700 */
                    --border-color: #4b5563; /* Gray 600 */
                    --radius: 0.75rem; /* 12px */
                    --shadow-light: rgba(0, 0, 0, 0.1);
                    --shadow-dark: rgba(0, 0, 0, 0.2);
                }

                body {
                    font-family: 'Inter', sans-serif;
                    background-color: var(--bg-dark);
                    color: var(--text-light);
                    min-height: 100vh;
                    overflow-y: auto;
                    padding: 1rem; /* Adjusted for mobile */
                }

                .container {
                    background-color: var(--card-bg);
                    border-radius: var(--radius);
                    box-shadow: 0 10px 25px var(--shadow-dark);
                    padding: 1.5rem; /* Adjusted for mobile */
                    width: 100%;
                    max-width: 900px;
                    margin: 1rem auto; /* Adjusted for mobile */
                    border: 1px solid var(--border-color);
                }

                h1, h2, p {
                    color: var(--text-light);
                }

                .folder-card {
                    background-color: var(--card-bg);
                    border: 1px solid var(--border-color);
                    border-radius: var(--radius);
                    box-shadow: 0 4px 6px var(--shadow-light);
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    align-items: center;
                    text-align: center;
                    transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
                    position: relative;
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    min-height: auto;
                    overflow: hidden; /* Crucial for clipping the border light effect */
                    padding: 1.5rem;
                    color: white;
                    /* Removed cursor: pointer from here as the card itself won't open the modal */
                }
                /* Only apply hover effects if animation is enabled */
                .folder-card:not(.no-animation):hover {
                    transform: translateY(-5px);
                    /* Existing shadow + new green blurry shadow */
                    box-shadow: 0 8px 12px var(--shadow-dark), 0 0 30px 10px rgba(0, 255, 0, 0.4);
                }

                /* Border light animation effect */
                .border-light-effect {
                    position: absolute;
                    inset: -2px; /* Slightly larger than the card to create the border effect */
                    border-radius: inherit; /* Inherit rounded corners from parent */
                    /* The conic-gradient creates the "worm" effect. Variables are set by JS. */
                    background: conic-gradient(from var(--initial-angle) at 50% 50%, transparent 0%, transparent 20%, var(--light-color) 30%, transparent 40%, transparent 100%);
                    animation: border-worm-walk var(--animation-duration) linear infinite;
                    z-index: 0; /* Ensure it's behind the content */
                    opacity: 0.7; /* Make it slightly transparent */
                }

                /* Disable animation for border light effect when .no-animation is present */
                .folder-card.no-animation .border-light-effect {
                    animation: none !important;
                    background: none !important; /* Remove the gradient background */
                }

                @keyframes border-worm-walk {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }


                .card-overlay {
                    position: relative; /* Ensure overlay is above the border light */
                    z-index: 1; /* Ensure content is on top of the border light */
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.4);
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    padding: 1.5rem;
                    color: white;
                    transition: background-color 0.3s ease-in-out;
                }
                /* Only apply hover effects if animation is enabled */
                .folder-card:not(.no-animation):hover .card-overlay {
                    background-color: rgba(0, 0, 0, 0.6);
                }
                .folder-name {
                    font-size: 1.5rem;
                    font-weight: 600;
                    margin-bottom: 0.5rem;
                    text-shadow: 1px 1px 3px rgba(0,0,0,0.8);
                    z-index: 1;
                    margin-top: 1.5rem;
                    color: white;
                }
                .app-type {
                    font-size: 0.8rem;
                    font-weight: 500;
                    padding: 0.15rem 0.6rem;
                    border-radius: 0.4rem;
                    margin-bottom: 0.5rem;
                    z-index: 1;
                    background-color: rgba(255, 255, 255, 0.2);
                    color: white;
                }
                .status-indicator {
                    font-size: 0.9rem;
                    font-weight: 500;
                    padding: 0.25rem 0.75rem;
                    border-radius: 0.5rem;
                    margin-bottom: 0.5rem;
                    z-index: 1;
                }
                .status-running {
                    background-color: rgba(46, 204, 113, 0.4);
                    color: white;
                }
                .status-stopped {
                    background-color: rgba(231, 76, 60, 0.4);
                    color: white;
                }
                .port-display {
                    font-size: 0.85rem;
                    margin-bottom: 1rem;
                    text-shadow: 1px 1px 3px rgba(0,0,0,0.8);
                    z-index: 1;
                    color: white;
                }
                .category-display { /* New style for category text */
                    font-size: 0.9rem;
                    font-weight: 600;
                    color: #a78bfa; /* A nice purple color */
                    text-shadow: 1px 1px 3px rgba(0,0,0,0.8);
                    margin-top: 0.5rem;
                    margin-bottom: 0.5rem;
                    z-index: 1;
                }
                .btn {
                    padding: 0.75rem 1.5rem;
                    border-radius: 0.75rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s ease-in-out;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    z-index: 1;
                    color: white;
                    background-color: var(--primary-color);
                    border: 1px solid var(--secondary-color);
                }
                .btn:hover {
                    background-color: var(--secondary-color);
                    transform: translateY(-2px);
                    box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
                }
                .btn-start {
                    background-color: #28a745; /* Green */
                    border-color: #218838;
                }
                .btn-start:hover {
                    background-color: #218838;
                }
                .btn-stop {
                    background-color: #dc3545; /* Red */
                    border-color: #c82333;
                }
                .btn-stop:hover {
                    background-color: #c82333;
                }
                .btn-open-url {
                    background-color: #007bff; /* Blue */
                    border-color: #0069d9;
                }
                .btn-open-url:hover {
                    background-color: #0069d9;
                }
                .btn-create-project { /* New style for create project button */
                    background-color: #28a745; /* Green */
                    border-color: #218838;
                }
                .btn-create-project:hover {
                    background-color: #218838;
                }
                .btn:disabled {
                    opacity: 0.4;
                    cursor: not-allowed;
                    box-shadow: none;
                }
                .search-input {
                    width: 100%;
                    padding: 0.75rem 1rem;
                    border: 1px solid var(--border-color);
                    border-radius: 0.75rem;
                    margin-bottom: 2rem;
                    font-size: 1rem;
                    color: var(--text-light);
                    background-color: #2d3748; /* Darker gray for input */
                    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.05);
                    transition: border-color 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
                }
                .search-input:focus {
                    outline: none;
                    border-color: var(--primary-color);
                    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2);
                }
                .message-box {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background-color: #4CAF50;
                    color: white;
                    padding: 15px 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
                    z-index: 1000;
                    opacity: 0;
                    transition: opacity 0.5s ease-in-out, transform 0.5s ease-in-out;
                    transform: translateY(-20px);
                }
                .message-box.show {
                    opacity: 1;
                    transform: translateY(0);
                }
                .message-box.error {
                    background-color: #f44336;
                }

                /* Styles for when cover is NOT shown */
                .folder-card.no-cover {
                    background-image: none !important;
                    background-color: var(--card-bg) !important;
                    min-height: auto !important;
                    overflow: hidden !important; /* Keep overflow hidden for border effect */
                    padding: 1.5rem !important;
                }
                .folder-card.no-cover .card-overlay {
                    position: relative;
                    background-color: transparent !important;
                    color: inherit !important;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    width: auto;
                    height: auto;
                    padding: 0;
                }
                .folder-card.no-cover .folder-name,
                .folder-card.no-cover .port-display,
                .folder-card.no-cover .category-display { /* Added category-display */
                    color: white !important;
                    text-shadow: 1px 1px 3px rgba(0,0,0,0.8);
                }
                .folder-card.no-cover .app-type {
                    background-color: rgba(255, 255, 255, 0.2) !important;
                    color: white !important;
                }
                .folder-card.no-cover .status-indicator {
                    background-color: rgba(255, 255, 255, 0.2) !important;
                    color: white !important;
                }

                /* Styles for the icons */
                .download-icon, .install-script-icon, .upload-icon, .edit-icon { /* Added .edit-icon */
                    position: absolute;
                    font-size: 1.5rem;
                    color: white;
                    cursor: pointer;
                    z-index: 2; /* Ensure icons are above overlay */
                    text-shadow: 1px 1px 3px rgba(0,0,0,0.8);
                    transition: color 0.2s ease-in-out;
                }
                .download-icon {
                    top: 10px;
                    right: 40px;
                }
                .install-script-icon {
                    top: 10px;
                    right: 10px;
                }
                .upload-icon {
                    top: 10px;
                    left: 10px;
                }
                .edit-icon { /* New style for the edit icon */
                    bottom: 10px;
                    left: 10px;
                }
                .download-icon:hover, .install-script-icon:hover, .upload-icon:hover, .edit-icon:hover { /* Added .edit-icon */
                    color: var(--primary-color);
                }
                .download-icon.installing, .install-script-icon.running {
                    animation: spin 1s linear infinite;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }

                /* Modal Specific Styles (General) */
                .modal-overlay {
                    position: fixed;
                    inset: 0;
                    background-color: rgba(0, 0, 0, 0.75);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 50;
                    opacity: 0;
                    visibility: hidden;
                    transition: opacity 0.3s ease-in-out, visibility 0.3s ease-in-out;
                }
                .modal-overlay.show {
                    opacity: 1;
                    visibility: visible;
                }
                .modal-content {
                    background-color: #374151; /* Gray 700 */
                    padding: 2rem;
                    border-radius: 1rem;
                    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
                    width: 90%;
                    max-width: 700px; /* Increased max-width for more space */
                    position: relative;
                    border: 1px solid #4b5563; /* Gray 600 */
                    transform: translateY(20px);
                    transition: transform 0.3s ease-in-out;
                    color: white;
                    max-height: 90vh; /* Allow scrolling for modal content */
                    overflow-y: auto; /* Enable vertical scrolling */
                }
                .modal-overlay.show .modal-content {
                    transform: translateY(0);
                }
                .modal-close-btn {
                    position: absolute;
                    top: 1rem;
                    right: 1rem;
                    font-size: 2rem;
                    color: #9ca3af; /* Gray 400 */
                    cursor: pointer;
                    transition: color 0.2s;
                }
                .modal-close-btn:hover {
                    color: white;
                }
                .modal-input, .modal-textarea {
                    width: 100%;
                    padding: 0.75rem;
                    border-radius: 0.5rem;
                    border: 1px solid #4b5563; /* Gray 600 */
                    background-color: #1f2937; /* Gray 800 */
                    color: white;
                    font-size: 1rem;
                    margin-top: 0.5rem;
                    margin-bottom: 1rem;
                }
                .modal-textarea {
                    min-height: 150px; /* Make textareas larger */
                    resize: vertical;
                }
                .modal-label {
                    display: block;
                    font-weight: 600;
                    color: #d1d5db; /* Gray 300 */
                    margin-bottom: 0.25rem;
                }

                /* Media Queries for Mobile Responsiveness */
                @media (max-width: 767px) {
                    body {
                        padding: 0.5rem; /* Even less padding on very small screens */
                    }

                    .container {
                        padding: 1rem; /* Reduced container padding */
                        margin: 0.5rem auto; /* Reduced container margin */
                    }

                    .h1 {
                        font-size: 2.5rem; /* Adjust main title size */
                    }

                    /* Adjust button group for smaller screens */
                    .flex.justify-center.space-x-4.mb-6 {
                        flex-direction: column;
                        align-items: center;
                        gap: 0.75rem; /* Add gap for vertical spacing */
                        margin-bottom: 1rem; /* Adjust margin */
                    }

                    .btn {
                        width: 100%; /* Make buttons full width on small screens */
                        max-width: 280px; /* Limit max width for buttons */
                        padding: 0.6rem 1.2rem; /* Slightly smaller button padding */
                        font-size: 0.9rem; /* Slightly smaller button font */
                    }

                    .search-input {
                        margin-bottom: 1rem; /* Adjust margin */
                        padding: 0.6rem 0.8rem; /* Smaller padding for search input */
                        font-size: 0.9rem; /* Smaller font for search input */
                    }

                    .folder-card {
                        padding: 1rem; /* Adjust card padding for smaller screens */
                    }

                    .folder-name {
                        font-size: 1.25rem; /* Slightly smaller font for folder names */
                        margin-top: 1rem; /* Adjust margin */
                    }

                    .app-type {
                        font-size: 0.7rem; /* Smaller text for app type */
                        padding: 0.1rem 0.4rem;
                    }

                    .status-indicator {
                        font-size: 0.8rem; /* Smaller text for status */
                        padding: 0.2rem 0.6rem;
                    }

                    .port-display, .category-display {
                        font-size: 0.75rem; /* Smaller text for details */
                        margin-bottom: 0.75rem; /* Adjust margin */
                    }

                    /* Adjust icon positions on smaller cards if they overlap */
                    .download-icon, .install-script-icon {
                        top: 8px;
                        right: 35px;
                        font-size: 1.3rem;
                    }
                    .install-script-icon {
                        right: 8px;
                    }
                    .upload-icon {
                        top: 8px;
                        left: 8px;
                        font-size: 1.3rem;
                    }
                    .edit-icon {
                        bottom: 8px;
                        left: 8px;
                        font-size: 1.3rem;
                    }

                    /* Modal adjustments for mobile */
                    .modal-content {
                        padding: 1.5rem; /* Adjust modal padding */
                        margin: 0.5rem; /* Add some margin to prevent sticking to edges */
                        width: calc(100% - 1rem); /* Full width minus margin */
                        max-width: none; /* Remove max-width constraint for mobile */
                    }

                    .modal-close-btn {
                        font-size: 1.75rem; /* Smaller close button */
                        top: 0.75rem;
                        right: 0.75rem;
                    }

                    .modal-input, .modal-textarea {
                        font-size: 0.9rem; /* Smaller font for modal inputs */
                        padding: 0.6rem; /* Smaller padding for modal inputs */
                    }

                    .modal-textarea {
                        min-height: 120px; /* Adjust min-height for mobile textareas */
                    }

                    /* Ensure grid layout adapts to 1 column on small screens */
                    #folderCards {
                        grid-template-columns: 1fr;
                    }
                }
            </style>
        </head>
        <body>
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

                    <div class="mb-4">
                        <label for="appPyCodeTextarea" class="modal-label">app.py Code:</label>
                        <textarea id="appPyCodeTextarea" class="modal-textarea" placeholder="Write your Python Flask/FastAPI code here..."></textarea>
                    </div>

                    <div class="mb-4">
                        <label for="requirementsTxtTextarea" class="modal-label">requirements.txt Code (Optional):</label>
                        <textarea id="requirementsTxtTextarea" class="modal-textarea" placeholder="List Python packages here, e.g., flask&#10;requests"></textarea>
                    </div>

                    <div class="mb-4">
                        <label for="installScriptTextarea" class="modal-label">install.sh Code (Optional):</label>
                        <textarea id="installScriptTextarea" class="modal-textarea" placeholder="Write your shell script here, e.g., npm install&#10;pip install -r requirements.txt"></textarea>
                    </div>

                    <div class="mb-6">
                        <label for="indexHtmlCodeTextarea" class="modal-label">index.html Code (for templates/index.html):</label>
                        <textarea id="indexHtmlCodeTextarea" class="modal-textarea" placeholder="Write your HTML code for the main template here..."></textarea>
                    </div>

                    <!-- New: Image Upload for Create Project -->
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

                    <div class="mb-4">
                        <label for="editAppPyCodeTextarea" class="modal-label">app.py Code:</label>
                        <textarea id="editAppPyCodeTextarea" class="modal-textarea" placeholder="Edit your Python Flask/FastAPI code here..."></textarea>
                    </div>

                    <div class="mb-4">
                        <label for="editRequirementsTxtTextarea" class="modal-label">requirements.txt Code (Optional):</label>
                        <textarea id="editRequirementsTxtTextarea" class="modal-textarea" placeholder="Edit Python packages here, e.g., flask&#10;requests"></textarea>
                    </div>

                    <div class="mb-4">
                        <label for="editInstallScriptTextarea" class="modal-label">install.sh Code (Optional):</label>
                        <textarea id="editInstallScriptTextarea" class="modal-textarea" placeholder="Edit your shell script here, e.g., npm install&#10;pip install -r requirements.txt"></textarea>
                    </div>

                    <div class="mb-6">
                        <label for="editIndexHtmlCodeTextarea" class="modal-label">index.html Code (for templates/index.html):</label>
                        <textarea id="editIndexHtmlCodeTextarea" class="modal-textarea" placeholder="Edit your HTML code for the main template here..."></textarea>
                    </div>

                    <!-- New: Image Upload for Edit Folder -->
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


            <script>
                const WEB_SERVER_PORT = <?php echo WEB_SERVER_PORT; ?>; // Pass PHP constant to JS
                const folderCardsContainer = document.getElementById('folderCards');
                const searchInput = document.getElementById('searchFolders');
                const messageBox = document.getElementById('messageBox');
                const settingsBtn = document.getElementById('settingsBtn'); // NEW: Settings button
                const stopAllAppsBtn = document.getElementById('stopAllAppsBtn');
                const createProjectBtn = document.getElementById('createProjectBtn');

                // Image Upload Modal elements (for individual card upload)
                const imageUploadModal = document.getElementById('imageUploadModal');
                const closeModalBtn = document.getElementById('closeModalBtn');
                const modalFolderNameSpan = document.getElementById('modalFolderName');
                const imageInput = document.getElementById('imageInput'); // For individual card upload
                const imagePreview = document.getElementById('imagePreview'); // For individual card upload
                const imagePreviewPlaceholder = document.getElementById('imagePreviewPlaceholder'); // For individual card upload
                const uploadImageBtn = document.getElementById('uploadImageBtn'); // For individual card upload

                // NEW: Settings Modal elements
                const settingsModal = document.getElementById('settingsModal');
                const closeSettingsModalBtn = document.getElementById('closeSettingsModalBtn');
                const showCoverCheckbox = document.getElementById('showCoverCheckbox');
                const enableCardAnimationCheckbox = document.getElementById('enableCardAnimationCheckbox');
                const saveSettingsBtn = document.getElementById('saveSettingsBtn');
                const backToLauncherBtn = document.getElementById('backToLauncherBtn');

                // Create Project Modal elements
                const createProjectModal = document.getElementById('createProjectModal');
                const closeCreateProjectModalBtn = document.getElementById('closeCreateProjectModalBtn');
                const projectNameInput = document.getElementById('projectNameInput');
                const appPyCodeTextarea = document.getElementById('appPyCodeTextarea');
                const indexHtmlCodeTextarea = document.getElementById('indexHtmlCodeTextarea');
                const categoryInput = document.getElementById('categoryInput');
                const requirementsTxtTextarea = document.getElementById('requirementsTxtTextarea');
                const installScriptTextarea = document.getElementById('installScriptTextarea');
                const saveProjectBtn = document.getElementById('saveProjectBtn');
                // New elements for Create Project Modal's image upload
                const createImageInput = document.getElementById('createImageInput');
                const createImagePreview = document.getElementById('createImagePreview');
                const createImagePreviewPlaceholder = document.getElementById('createImagePreviewPlaceholder');

                // NEW: Edit Folder Modal elements
                const editFolderModal = document.getElementById('editFolderModal');
                const closeEditFolderModalBtn = document.getElementById('closeEditFolderModalBtn');
                const editModalFolderNameSpan = document.getElementById('editModalFolderName');
                const editAppPyCodeTextarea = document.getElementById('editAppPyCodeTextarea');
                const editIndexHtmlCodeTextarea = document.getElementById('editIndexHtmlCodeTextarea');
                const editRequirementsTxtTextarea = document.getElementById('editRequirementsTxtTextarea');
                const editInstallScriptTextarea = document.getElementById('editInstallScriptTextarea');
                const editCategoryTxtInput = document.getElementById('editCategoryTxtInput');
                const saveFolderContentBtn = document.getElementById('saveFolderContentBtn');
                // New elements for Edit Folder Modal's image upload
                const editImageInput = document.getElementById('editImageInput');
                const editImagePreview = document.getElementById('editImagePreview');
                const editImagePreviewPlaceholder = document.getElementById('editImagePreviewPlaceholder');


                let allFolders = [];
                let currentSearchTerm = '';
                let showCoverImages = true;
                let enableCardAnimation = <?php echo $enableCardAnimationJs; ?>; // Pass new setting from PHP
                const renderedCards = new Map(); // Map to store references to rendered card elements by folder name

                let currentFolderForUpload = null; // To store the folder name for the current upload operation (for the dedicated upload modal)
                let currentFolderForEdit = null; // NEW: To store the folder name for the current edit operation


                /**
                 * Displays a message box with a given message and type (success or error).
                 * @param {string} message - The message to display.
                 * @param {string} [type='success'] - The type of message ('success' or 'error').
                 */
                function showMessage(message, type = 'success') {
                    messageBox.textContent = message;
                    messageBox.className = 'message-box show';
                    if (type === 'error') {
                        messageBox.classList.add('error');
                    } else {
                        messageBox.classList.remove('error');
                    }
                    setTimeout(() => {
                        messageBox.classList.remove('show');
                    }, 3000);
                }

                /**
                 * Fetches settings from the server and updates the showCoverImages flag.
                 * Then triggers fetching and displaying folders.
                 */
                async function fetchSettings() {
                    try {
                        const response = await fetch('index.php?action=get_settings');
                        const settings = await response.json();
                        showCoverImages = settings.showCover;
                        enableCardAnimation = settings.enableCardAnimation; // Update new setting
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
                 * Generates a random integer within a specified range.
                 * @param {number} min - The minimum value (inclusive).
                 * @param {number} max - The maximum value (inclusive).
                 * @returns {number} A random integer.
                 */
                function getRandomInt(min, max) {
                    min = Math.ceil(min);
                    max = Math.floor(max);
                    return Math.floor(Math.random() * (max - min + 1)) + min;
                }

                /**
                 * Generates a random float within a specified range.
                 * @param {number} min - The minimum value (inclusive).
                 * @param {number} max - The maximum value (exclusive).
                 * @returns {number} A random float.
                 */
                function getRandomFloat(min, max) {
                    return Math.random() * (max - min) + min;
                }

                /**
                 * Returns a random color from a predefined list.
                 * @returns {string} A hex color string.
                 */
                function getRandomColor() {
                    const colors = [
                        '#00ff00', // green
                        '#00ffff', // cyan
                        '#ff00ff', // magenta
                        '#ffff00', // yellow
                        '#00aaff', // light blue
                        '#ffaa00', // orange
                        '#ff00aa', // pink
                    ];
                    return colors[getRandomInt(0, colors.length - 1)];
                }

                /**
                 * Creates a new folder card HTML element.
                 * @param {object} folder - The folder data.
                 * @returns {HTMLElement} The created card element.
                 */
                function createFolderCard(folder) {
                    const card = document.createElement('div');
                    card.className = 'folder-card';
                    card.dataset.folderName = folder.name; // Store folder name on the card element

                    const baseUrl = window.location.origin + window.location.pathname.substring(0, window.location.pathname.lastIndexOf('/') + 1);
                    const imagePath = `${baseUrl}scripts/${folder.name}/cover.png`;

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

                    // Add/remove no-animation class based on setting
                    if (!enableCardAnimation) {
                        card.classList.add('no-animation');
                    } else {
                        card.classList.remove('no-animation');
                    }

                    // Create the border light effect element
                    const borderLightEffect = document.createElement('div');
                    borderLightEffect.className = 'border-light-effect';

                    // Apply random animation properties only if animation is enabled
                    if (enableCardAnimation) {
                        const randomDuration = getRandomFloat(8, 15); // 8 to 15 seconds for animation
                        const randomInitialAngle = getRandomInt(0, 360); // Random starting angle
                        const randomLightColor = getRandomColor(); // Random light color

                        borderLightEffect.style.setProperty('--animation-duration', `${randomDuration}s`);
                        borderLightEffect.style.setProperty('--initial-angle', `${randomInitialAngle}deg`);
                        borderLightEffect.style.setProperty('--light-color', randomLightColor);
                    }

                    card.prepend(borderLightEffect); // Add it as the first child so it's behind the overlay

                    // Initial content, will be updated by updateFolderCardContent
                    card.innerHTML += `
                        <div class="card-overlay">
                            <i class="fas fa-image upload-icon" data-folder="${folder.name}" title="Upload Cover Image"></i>
                            ${folder.has_requirements_file ? `<i class="fas fa-download download-icon" data-folder="${folder.name}" title="Install Requirements"></i>` : ''}
                            ${folder.has_install_script ? `<i class="fas fa-wrench install-script-icon" data-folder="${folder.name}" title="Run Install Script"></i>` : ''}
                            <i class="fas fa-edit edit-icon" data-folder="${folder.name}" title="Edit Folder Content"></i> <!-- NEW: Edit Icon -->
                            <div class="folder-name">${folder.name}</div>
                            <div class="app-type">${folder.type.toUpperCase()}</div>
                            ${folder.has_category_file && folder.category_text ? `<div class="category-display">${folder.category_text}</div>` : ''}
                            <div class="status-indicator"></div>
                            <div class="port-display"></div>
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
                    const buttonsContainer = cardElement.querySelector('.card-buttons');
                    const downloadIcon = cardElement.querySelector('.download-icon');
                    const installScriptIcon = cardElement.querySelector('.install-script-icon');
                    const uploadIcon = cardElement.querySelector('.upload-icon');
                    const editIcon = cardElement.querySelector('.edit-icon'); // NEW: Get edit icon

                    // Update status
                    const statusClass = folder.is_running ? 'status-running' : 'status-stopped';
                    const statusText = folder.is_running ? 'Running' : 'Stopped';
                    statusIndicator.className = `status-indicator ${statusClass}`;
                    statusIndicator.textContent = statusText;

                    // Update port display
                    portDisplay.textContent = folder.port ? `Port: ${folder.port}` : '';
                    portDisplay.style.display = (folder.type === 'python' && folder.port) ? 'block' : 'none';

                    // Update category display
                    if (categoryDisplay) {
                        categoryDisplay.textContent = folder.category_text || '';
                        categoryDisplay.style.display = folder.has_category_file && folder.category_text ? 'block' : 'none';
                    }

                    // Update buttons
                    buttonsContainer.innerHTML = ''; // Clear existing buttons
                    const baseUrl = window.location.origin + window.location.pathname.substring(0, window.location.pathname.lastIndexOf('/') + 1);
                    const phpAppUrl = `${baseUrl}scripts/${folder.name}/index.php`;

                    if (folder.type === 'python') {
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

                        if (folder.is_running && folder.port) {
                            const openUrlBtn = document.createElement('button');
                            openUrlBtn.className = 'btn btn-open-url';
                            openUrlBtn.textContent = 'Open URL';
                            openUrlBtn.onclick = () => window.open(`http://127.0.0.1:${folder.port}`, '_blank');
                            buttonsContainer.appendChild(openUrlBtn);
                        }
                    } else if (folder.type === 'php') {
                        const openUrlBtn = document.createElement('button');
                        openUrlBtn.className = 'btn btn-open-url';
                        openUrlBtn.textContent = 'Open URL';
                        openUrlBtn.onclick = () => window.open(phpAppUrl, '_blank');
                        buttonsContainer.appendChild(openUrlBtn);
                    }

                    // Update icon visibility and event listeners
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
                            openImageUploadModal(folder.name); // This uses the dedicated image upload modal
                        };
                    }
                    // NEW: Add event listener for the edit icon
                    if (editIcon) {
                        editIcon.onclick = (event) => {
                            event.stopPropagation();
                            openEditFolderModal(folder.name);
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

                    // Remove cards that are no longer in the data
                    existingCardNames.forEach(name => {
                        if (!currentFolderNames.has(name)) {
                            const cardToRemove = renderedCards.get(name);
                            if (cardToRemove) {
                                cardToRemove.remove();
                                renderedCards.delete(name);
                            }
                        }
                    });

                    // Add or update cards
                    foldersToRender.forEach(folder => {
                        let cardElement = renderedCards.get(folder.name);
                        if (!cardElement) {
                            // Create new card if it doesn't exist
                            cardElement = createFolderCard(folder);
                            folderCardsContainer.appendChild(cardElement);
                            renderedCards.set(folder.name, cardElement);
                        }
                        // Update content for existing or newly created card
                        updateFolderCardContent(cardElement, folder);

                        // Update background image based on settings
                        const baseUrl = window.location.origin + window.location.pathname.substring(0, window.location.pathname.lastIndexOf('/') + 1);
                        // Add a timestamp to the image URL to bust cache when uploaded
                        const imagePath = `${baseUrl}scripts/${folder.name}/cover.png?t=${new Date().getTime()}`;
                        
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

                        // Update animation class based on setting
                        const borderLightEffect = cardElement.querySelector('.border-light-effect');
                        if (borderLightEffect) { // Ensure element exists before manipulating
                            if (!enableCardAnimation) {
                                cardElement.classList.add('no-animation');
                                borderLightEffect.style.animation = 'none';
                                borderLightEffect.style.background = 'none';
                            } else {
                                cardElement.classList.remove('no-animation');
                                // Re-apply random animation properties if animation is enabled
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
                    buttonElement.disabled = true; // Disable button immediately
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
                            fetchAndDisplayFolders(); // Re-fetch to update status
                        } else {
                            showMessage(result.message, 'error');
                        }
                    } catch (error) {
                        console.error('Error starting app:', error);
                        showMessage('An error occurred while trying to start the app.', 'error');
                    } finally {
                        // The button will be re-enabled by fetchAndDisplayFolders refreshing the card state,
                        // but ensure it's re-enabled if an error prevents that.
                        fetchAndDisplayFolders();
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
                        (folder.category_text && folder.category_text.toLowerCase().includes(searchTerm))
                    );
                    renderFolders(filteredFolders);
                }

                // Image Upload Modal Functions (for the dedicated upload modal)
                /**
                 * Opens the image upload modal for a specific folder.
                 * @param {string} folderName - The name of the folder to upload an image for.
                 */
                function openImageUploadModal(folderName) {
                    currentFolderForUpload = folderName;
                    modalFolderNameSpan.textContent = folderName;
                    imagePreview.src = '#';
                    imagePreview.classList.add('hidden');
                    imagePreviewPlaceholder.classList.remove('hidden');
                    imageInput.value = ''; // Clear file input
                    imageUploadModal.classList.remove('hidden');
                    imageUploadModal.classList.add('show');
                }

                /**
                 * Closes the image upload modal.
                 */
                function closeImageUploadModal() {
                    imageUploadModal.classList.remove('show');
                    imageUploadModal.classList.add('hidden');
                    currentFolderForUpload = null;
                }

                /**
                 * Handles the change event for the image input, displaying a preview.
                 * @param {Event} event - The input change event.
                 * @param {HTMLImageElement} previewElement - The <img> element for preview.
                 * @param {HTMLElement} placeholderElement - The placeholder element.
                 */
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

                /**
                 * Handles the upload of the selected image to the server for a given folder.
                 * @param {string} folderName - The name of the folder to upload the image for.
                 * @param {HTMLInputElement} fileInput - The file input element.
                 * @param {HTMLButtonElement} buttonElement - The button element that triggered the upload.
                 * @returns {Promise<boolean>} True if upload was successful, false otherwise.
                 */
                async function uploadImageForProject(folderName, fileInput, buttonElement) {
                    const file = fileInput.files[0];
                    if (!file) {
                        // No file selected, consider it a success if no image was intended to be uploaded
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

                // Existing uploadImageBtn listener (for the dedicated upload modal)
                uploadImageBtn.addEventListener('click', async () => {
                    if (currentFolderForUpload) {
                        const success = await uploadImageForProject(currentFolderForUpload, imageInput, uploadImageBtn);
                        if (success) {
                            fetchAndDisplayFolders(); // Refresh cards to show new cover image
                            closeImageUploadModal();
                        }
                    }
                });


                // NEW: Settings Modal Functions
                /**
                 * Opens the settings modal.
                 */
                function openSettingsModal() {
                    // Load current settings into the checkboxes when opening the modal
                    loadSettingsForModal();
                    settingsModal.classList.remove('hidden');
                    settingsModal.classList.add('show');
                }

                /**
                 * Closes the settings modal.
                 */
                function closeSettingsModal() {
                    settingsModal.classList.remove('show');
                    settingsModal.classList.add('hidden');
                }

                /**
                 * Loads settings specifically for the settings modal.
                 */
                async function loadSettingsForModal() {
                    try {
                        const response = await fetch('index.php?action=get_settings');
                        const settings = await response.json();
                        showCoverCheckbox.checked = settings.showCover;
                        enableCardAnimationCheckbox.checked = settings.enableCardAnimation;
                    } catch (error) {
                        console.error('Error loading settings for modal:', error);
                        showMessage('Failed to load settings into modal.', 'error');
                    }
                }

                /**
                 * Saves settings from the settings modal.
                 */
                async function saveSettingsFromModal() {
                    const settings = {
                        showCover: showCoverCheckbox.checked,
                        enableCardAnimation: enableCardAnimationCheckbox.checked
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
                            // Update global flags and re-render folders to apply changes immediately
                            showCoverImages = settings.showCover;
                            enableCardAnimation = settings.enableCardAnimation;
                            filterAndRenderFolders();
                            closeSettingsModal(); // Close modal after saving
                        } else {
                            showMessage(result.message, 'error');
                        }
                    } catch (error) {
                        console.error('Error saving settings:', error);
                        showMessage('An error occurred while trying to save settings.', 'error');
                    }
                }


                // Create Project Modal Functions
                /**
                 * Opens the create project modal.
                 */
                function openCreateProjectModal() {
                    projectNameInput.value = '';
                    appPyCodeTextarea.value = '';
                    indexHtmlCodeTextarea.value = '';
                    categoryInput.value = '';
                    requirementsTxtTextarea.value = '';
                    installScriptTextarea.value = '';
                    // Reset image input and preview for create project modal
                    createImageInput.value = '';
                    createImagePreview.src = '#';
                    createImagePreview.classList.add('hidden');
                    createImagePreviewPlaceholder.classList.remove('hidden');

                    createProjectModal.classList.remove('hidden');
                    createProjectModal.classList.add('show');
                }

                /**
                 * Closes the create project modal.
                 */
                function closeCreateProjectModal() {
                    createProjectModal.classList.remove('show');
                    createProjectModal.classList.add('hidden');
                }

                /**
                 * Handles saving the new project.
                 */
                async function saveProject() {
                    const projectName = projectNameInput.value.trim();
                    const appPyCode = appPyCodeTextarea.value;
                    const indexHtmlCode = indexHtmlCodeTextarea.value;
                    const categoryName = categoryInput.value.trim();
                    const requirementsTxtCode = requirementsTxtTextarea.value;
                    const installScriptCode = installScriptTextarea.value;

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
                                install_script_code: installScriptCode
                            })
                        });
                        const result = await response.json();

                        if (response.ok && result.status === 'success') {
                            showMessage(result.message);
                            // If project creation is successful, attempt to upload the image
                            const uploadSuccess = await uploadImageForProject(projectName, createImageInput, saveProjectBtn);
                            if (uploadSuccess) {
                                closeCreateProjectModal();
                                fetchAndDisplayFolders();
                            } else {
                                // If image upload failed, still close modal and refresh, but keep error message
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

                // NEW: Edit Folder Modal Functions
                /**
                 * Opens the edit folder modal for a specific folder.
                 * @param {string} folderName - The name of the folder to edit.
                 */
                async function openEditFolderModal(folderName) {
                    currentFolderForEdit = folderName;
                    editModalFolderNameSpan.textContent = folderName;

                    // Show loading state or clear previous content
                    editAppPyCodeTextarea.value = 'Loading...';
                    editIndexHtmlCodeTextarea.value = 'Loading...';
                    editRequirementsTxtTextarea.value = 'Loading...';
                    editInstallScriptTextarea.value = 'Loading...';
                    editCategoryTxtInput.value = 'Loading...';
                    saveFolderContentBtn.disabled = true;

                    // Reset image input and preview for edit folder modal
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

                            // Load existing cover image if it exists
                            const baseUrl = window.location.origin + window.location.pathname.substring(0, window.location.pathname.lastIndexOf('/') + 1);
                            const imagePath = `${baseUrl}scripts/${folderName}/cover.png?t=${new Date().getTime()}`; // Add timestamp to bust cache
                            
                            // Check if image exists by trying to load it
                            const img = new Image();
                            img.onload = () => {
                                editImagePreview.src = imagePath;
                                editImagePreview.classList.remove('hidden');
                                editImagePreviewPlaceholder.classList.add('hidden');
                            };
                            img.onerror = () => {
                                // Image does not exist or failed to load, show placeholder
                                editImagePreview.src = '#';
                                editImagePreview.classList.add('hidden');
                                editImagePreviewPlaceholder.classList.remove('hidden');
                            };
                            img.src = imagePath; // Attempt to load the image
                        } else {
                            showMessage(result.message, 'error');
                            // Clear fields if loading failed
                            editAppPyCodeTextarea.value = '';
                            editIndexHtmlCodeTextarea.value = '';
                            editRequirementsTxtTextarea.value = '';
                            editInstallScriptTextarea.value = '';
                            editCategoryTxtInput.value = '';
                        }
                    } catch (error) {
                        console.error('Error fetching folder content:', error);
                        showMessage('An error occurred while loading folder content.', 'error');
                        // Clear fields on network error
                        editAppPyCodeTextarea.value = '';
                        editIndexHtmlCodeTextarea.value = '';
                        editRequirementsTxtTextarea.value = '';
                        editInstallScriptTextarea.value = '';
                        editCategoryTxtInput.value = '';
                    } finally {
                        saveFolderContentBtn.disabled = false;
                        editFolderModal.classList.remove('hidden');
                        editFolderModal.classList.add('show');
                    }
                }

                /**
                 * Closes the edit folder modal.
                 */
                function closeEditFolderModal() {
                    editFolderModal.classList.remove('show');
                    editFolderModal.classList.add('hidden');
                    currentFolderForEdit = null;
                }

                /**
                 * Handles saving the edited folder content.
                 */
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
                        category_txt: editCategoryTxtInput.value
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
                            // If content save is successful, attempt to upload the image
                            const uploadSuccess = await uploadImageForProject(currentFolderForEdit, editImageInput, saveFolderContentBtn);
                            if (uploadSuccess) {
                                closeEditFolderModal();
                                fetchAndDisplayFolders(); // Refresh folder list to reflect changes (e.g., category, new cover)
                            } else {
                                // If image upload failed, still close modal and refresh, but keep error message
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


                // Event Listeners
                searchInput.addEventListener('input', (event) => {
                    currentSearchTerm = event.target.value;
                    filterAndRenderFolders();
                });

                stopAllAppsBtn.addEventListener('click', stopAllApps);
                createProjectBtn.addEventListener('click', openCreateProjectModal);

                // Settings Modal event listeners
                settingsBtn.addEventListener('click', openSettingsModal);
                closeSettingsModalBtn.addEventListener('click', closeSettingsModal);
                saveSettingsBtn.addEventListener('click', saveSettingsFromModal);
                backToLauncherBtn.addEventListener('click', closeSettingsModal);

                // Image Upload Modal event listeners (for dedicated upload modal)
                closeModalBtn.addEventListener('click', closeImageUploadModal);
                imageInput.addEventListener('change', (event) => handleImageSelect(event, imagePreview, imagePreviewPlaceholder));
                // uploadImageBtn listener is defined above, outside this block, using the refactored uploadImageForProject

                // Create Project Modal event listeners
                closeCreateProjectModalBtn.addEventListener('click', closeCreateProjectModal);
                saveProjectBtn.addEventListener('click', saveProject);
                createImageInput.addEventListener('change', (event) => handleImageSelect(event, createImagePreview, createImagePreviewPlaceholder));


                // NEW: Edit Folder Modal event listeners
                closeEditFolderModalBtn.addEventListener('click', closeEditFolderModal);
                saveFolderContentBtn.addEventListener('click', saveFolderContent);
                editImageInput.addEventListener('change', (event) => handleImageSelect(event, editImagePreview, editImagePreviewPlaceholder));


                // Initial fetch and polling for updates
                document.addEventListener('DOMContentLoaded', fetchSettings);
                setInterval(fetchAndDisplayFolders, 5000); // Poll every 5 seconds for real-time status
            </script>
        </body>
        </html>
        <?php
        break;
}
?>
