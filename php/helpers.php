<?php
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

/**
 * Recursively deletes a directory and its contents.
 * @param string $dir The directory to delete.
 * @return bool True on success, false on failure.
 */
function rrmdir($dir) {
    if (!file_exists($dir)) {
        return true;
    }
    if (!is_dir($dir)) {
        return unlink($dir);
    }
    foreach (scandir($dir) as $item) {
        if ($item == '.' || $item == '..') {
            continue;
        }
        if (!rrmdir($dir . DIRECTORY_SEPARATOR . $item)) {
            return false;
        }
    }
    return rmdir($dir);
}
?>
