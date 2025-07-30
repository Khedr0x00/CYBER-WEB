<?php
// Set error reporting for development
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// Define base directories
$scriptsBaseDir = __DIR__ . DIRECTORY_SEPARATOR . 'scripts';
$pidsDir = __DIR__ . DIRECTORY_SEPARATOR . 'pids';
$nextPortFile = __DIR__ . DIRECTORY_SEPARATOR . 'next_port.txt';

// Define the web server's port for PHP app URLs.
// This is set to 8000 to match 'php -S localhost:8000'.
const WEB_SERVER_PORT = 8000; 

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

/**
 * Helper function to get the next available port and increment the counter.
 * @param string $file The path to the file storing the next port.
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
        // Attempt to kill the process group first for better cleanup of child processes
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
            // Try common Termux Python paths if 'which python' fails
            $termuxPythonPaths = [
                '/data/data/com.termux/files/usr/bin/python',
                '/data/data/com.termux/files/usr/bin/python3'
            ];
            foreach ($termuxPythonPaths as $path) {
                if (file_exists($path) && is_executable($path)) {
                    $pythonPath = $path;
                    error_log("findPythonExecutable (Unix): Found Termux Python at {$pythonPath}");
                    break;
                }
            }
            if (!$pythonPath) {
                error_log("findPythonExecutable (Unix): Python not found using 'which python' or common Termux paths.");
            }
        }
    }
    return $pythonPath;
}

// Find python executable once at the start
$pythonExecutable = findPythonExecutable();


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

                $isPythonApp = file_exists($pythonAppFilePath);
                $isPhpApp = file_exists($phpAppFilePath);

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
                        'port' => $port
                    ];
                } elseif ($isPhpApp) {
                    // PHP apps are always "running" as they are served by the web server
                    // The URL will be relative to the web server's document root
                    // Use WEB_SERVER_PORT to construct the URL for PHP apps
                    $phpAppUrl = "http://localhost:" . WEB_SERVER_PORT . '/' . basename(__DIR__) . '/scripts/' . $folderName . '/index.php';

                    $folders[] = [
                        'name' => $folderName,
                        'type' => 'php',
                        'is_running' => true, // PHP apps are always considered running if their index.php exists
                        'url' => $phpAppUrl // Provide the direct URL for PHP apps
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
            $fullCommand = "cd /D " . escapeshellarg($folderPath) . " && start /B " . $command . " > " . escapeshellarg($logFile) . " 2>&1";
        } else {
            $fullCommand = "cd " . escapeshellarg($folderPath) . " && nohup " . $command . " > " . escapeshellarg($logFile) . " 2>&1 &";
        }

        error_log("start_app: Attempting to execute command: {$fullCommand}");
        exec($fullCommand, $output, $return_var);
        error_log("start_app: Command execution returned: {$return_var}. Output: " . implode("\n", $output));

        sleep(3); // Wait 3 seconds for the app to start

        $currentPidAfterStart = getPidByPort($port);
        $isActuallyRunning = ($currentPidAfterStart && isProcessRunning($currentPidAfterStart));

        if ($return_var === 0 && $isActuallyRunning) {
            file_put_contents($pidFile, json_encode(['port' => $port]));
            error_log("start_app: App in {$folderName} successfully started on port {$port} with PID {$currentPidAfterStart}.");
            echo json_encode(['status' => 'success', 'message' => "App in {$folderName} started on port {$port}.", 'url' => $appUrl]);
        } else {
            $errorMessage = "Failed to start app in {$folderName}.";
            if (!$isActuallyRunning) {
                $errorMessage .= " Process not detected running after start attempt.";
            }
            $errorMessage .= " Command: {$fullCommand} Return Var: {$return_var} Output: " . implode("\n", $output) . ". Check {$logFile} for details.";
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
            // Use @ to suppress warnings from file_get_contents if the server is not reachable
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

    default:
        // Serve the HTML page with embedded CSS and JS
        header('Content-Type: text/html');
        ?>
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>PHP Python App Launcher</title>
            <!-- Tailwind CSS CDN -->
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
            <style>
                /* Embedded style.css content */
                body {
                    font-family: 'Inter', sans-serif;
                    background-color: #f0f2f5;
                    display: flex;
                    justify-content: center;
                    align-items: flex-start;
                    min-height: 100vh;
                    padding: 2rem;
                }
                .container {
                    background-color: #ffffff;
                    border-radius: 1rem;
                    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                    padding: 2.5rem;
                    width: 100%;
                    max-width: 900px;
                }
                .folder-card {
                    background-color: #f7f9fc;
                    border: 1px solid #e2e8f0;
                    border-radius: 0.75rem;
                    padding: 1.5rem;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    align-items: center;
                    text-align: center;
                    transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
                }
                .folder-card:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.15);
                }
                .folder-name {
                    font-size: 1.5rem;
                    font-weight: 600;
                    color: #2d3748;
                    margin-bottom: 0.5rem;
                }
                .app-type {
                    font-size: 0.8rem;
                    font-weight: 500;
                    padding: 0.15rem 0.6rem;
                    border-radius: 0.4rem;
                    margin-bottom: 0.5rem;
                    background-color: #bfdbfe; /* Blue for Python */
                    color: #1e40af;
                }
                .app-type.php {
                    background-color: #dbeafe; /* Lighter blue for PHP */
                    color: #1c3b7a;
                }
                .status-indicator {
                    font-size: 0.9rem;
                    font-weight: 500;
                    padding: 0.25rem 0.75rem;
                    border-radius: 0.5rem;
                    margin-bottom: 0.5rem;
                }
                .status-running {
                    background-color: #d1fae5;
                    color: #065f46;
                }
                .status-stopped {
                    background-color: #fee2e2;
                    color: #991b1b;
                }
                .port-display {
                    font-size: 0.85rem;
                    color: #6b7280;
                    margin-bottom: 1rem;
                }
                .btn {
                    padding: 0.75rem 1.5rem;
                    border-radius: 0.75rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s ease-in-out;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }
                .btn-start {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                }
                .btn-start:hover {
                    background-color: #45a049;
                    transform: translateY(-2px);
                    box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
                }
                .btn-stop {
                    background-color: #f44336;
                    color: white;
                    border: none;
                }
                .btn-stop:hover {
                    background-color: #da190b;
                    transform: translateY(-2px);
                    box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
                }
                .btn-open-url {
                    background-color: #3b82f6;
                    color: white;
                    border: none;
                }
                .btn-open-url:hover {
                    background-color: #2563eb;
                    transform: translateY(-2px);
                    box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
                }
                .btn:disabled {
                    opacity: 0.6;
                    cursor: not-allowed;
                    box-shadow: none;
                }
                .search-input {
                    width: 100%;
                    padding: 0.75rem 1rem;
                    border: 1px solid #cbd5e0;
                    border-radius: 0.75rem;
                    margin-bottom: 2rem;
                    font-size: 1rem;
                    color: #4a5568;
                    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.05);
                    transition: border-color 0.2s ease-in-out, box-shadow 0 0 0 3px rgba(99, 102, 241, 0.2);
                }
                .search-input:focus {
                    outline: none;
                    border-color: #6366f1;
                    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
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
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="text-4xl font-bold text-center text-gray-800 mb-8">Python & PHP App Launcher</h1>

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

            <script>
                const WEB_SERVER_PORT = <?php echo WEB_SERVER_PORT; ?>; // Pass PHP constant to JS
                const folderCardsContainer = document.getElementById('folderCards');
                const searchInput = document.getElementById('searchFolders');
                const messageBox = document.getElementById('messageBox');

                let allFolders = [];

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

                async function fetchAndDisplayFolders() {
                    try {
                        const response = await fetch('index.php?action=list_folders');
                        const folders = await response.json();
                        allFolders = folders;
                        renderFolders(allFolders);
                    } catch (error) {
                        console.error('Error fetching folders:', error);
                        showMessage('Failed to load folders. Please check the server and PHP error logs.', 'error');
                    }
                }

                function renderFolders(foldersToRender) {
                    folderCardsContainer.innerHTML = '';
                    if (foldersToRender.length === 0) {
                        folderCardsContainer.innerHTML = '<p class="text-center text-gray-600 col-span-full">No applications found or matching your search.</p>';
                        return;
                    }

                    foldersToRender.forEach(folder => {
                        const card = document.createElement('div');
                        card.className = 'folder-card';

                        const statusClass = folder.is_running ? 'status-running' : 'status-stopped';
                        const statusText = folder.is_running ? 'Running' : 'Stopped';
                        const portText = folder.port ? `Port: ${folder.port}` : '';
                        
                        // Determine the base URL for PHP apps, assuming index.php is in the same directory as this dashboard
                        // Construct the URL using localhost and the defined WEB_SERVER_PORT
                        const phpAppUrl = `http://localhost:${WEB_SERVER_PORT}/scripts/${folder.name}/index.php`;


                        card.innerHTML = `
                            <div class="folder-name">${folder.name}</div>
                            <div class="app-type ${folder.type}">${folder.type.toUpperCase()}</div>
                            <div class="status-indicator ${statusClass}">${statusText}</div>
                            ${folder.type === 'python' && folder.port ? `<div class="port-display">${portText}</div>` : ''}
                            <div class="flex space-x-2 mt-auto">
                                ${folder.type === 'python' ? `
                                    <button class="btn btn-start" data-folder="${folder.name}" ${folder.is_running ? 'disabled' : ''}>Start</button>
                                    <button class="btn btn-stop" data-folder="${folder.name}" ${!folder.is_running ? 'disabled' : ''}>Stop</button>
                                ` : ''}
                                ${folder.type === 'python' && folder.is_running && folder.port ?
                                    `<button class="btn btn-open-url" onclick="window.open('http://127.0.0.1:${folder.port}', '_blank')">Open URL</button>`
                                : ''}
                                ${folder.type === 'php' ?
                                    `<button class="btn btn-open-url" onclick="window.open('${phpAppUrl}', '_blank')">Open URL</button>`
                                : ''}
                            </div>
                        `;
                        folderCardsContainer.appendChild(card);
                    });

                    addEventListenersToButtons();
                }

                function addEventListenersToButtons() {
                    document.querySelectorAll('.btn-start').forEach(button => {
                        button.onclick = () => startApp(button.dataset.folder);
                    });
                    document.querySelectorAll('.btn-stop').forEach(button => {
                        button.onclick = () => stopApp(button.dataset.folder);
                    });
                }

                async function startApp(folderName) {
                    try {
                        const response = await fetch('index.php?action=start_app', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ folder_name: folderName })
                        });
                        const result = await response.json();
                        if (response.ok) {
                            showMessage(result.message);
                            fetchAndDisplayFolders(); // Refresh to update status and show Open URL button
                            if (result.url) {
                                // Open the URL in a new tab if provided by the backend
                                window.open(result.url, '_blank');
                            }
                        } else {
                            showMessage(result.message, 'error');
                        }
                    } catch (error) {
                        console.error('Error starting app:', error);
                        showMessage('An error occurred while trying to start the app.', 'error');
                    }
                }

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
                            fetchAndDisplayFolders(); // Refresh to update status
                        } else {
                            showMessage(result.message, 'error');
                        }
                    } catch (error) {
                        console.error('Error stopping app:', error);
                        showMessage('An error occurred while trying to stop the app.', 'error');
                    }
                }

                searchInput.addEventListener('input', (event) => {
                    const searchTerm = event.target.value.toLowerCase();
                    const filteredFolders = allFolders.filter(folder =>
                        folder.name.toLowerCase().includes(searchTerm)
                    );
                    renderFolders(filteredFolders);
                });

                document.addEventListener('DOMContentLoaded', fetchAndDisplayFolders);
                setInterval(fetchAndDisplayFolders, 2000); // Poll every 2 seconds for real-time status
            </script>
        </body>
        </html>
        <?php
        break;
}
?>
