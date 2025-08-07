<?php
// upload.php
// This script receives uploaded screenshot files (e.g., .webp images)
// and organizes them into unique folders based on the provided PC ID.
// It also receives and saves PC information as JSON.

header('Content-Type: application/json');

// Define the base directory for uploaded files.
// Ensure this directory exists and is writable by your web server.
$baseUploadDirectory = 'uploads/';

// Get raw POST data for JSON parsing
$input = file_get_contents('php://input');
$data = json_decode($input, true); // Decode JSON data if present

$pcId = null;
// Determine PC ID from POST (for file upload) or JSON (for info upload)
if (isset($_POST['pc_id']) && !empty($_POST['pc_id'])) {
    $pcId = $_POST['pc_id'];
} elseif (isset($data['pc_id']) && !empty($data['pc_id'])) {
    $pcId = $data['pc_id'];
}

if (!$pcId) {
    echo json_encode(['success' => false, 'message' => 'PC ID not provided.']);
    error_log("Error: PC ID not provided in upload request.");
    exit();
}

$uploadDirectory = $baseUploadDirectory . $pcId . '/';

// Check if the PC-specific directory exists, if not, create it
if (!is_dir($uploadDirectory)) {
    // 0777 grants full permissions (for testing; use more restrictive permissions in production)
    // true creates nested directories if needed
    if (!mkdir($uploadDirectory, 0777, true)) {
        echo json_encode(['success' => false, 'message' => "Failed to create PC directory: " . $uploadDirectory]);
        error_log("Failed to create PC directory: " . $uploadDirectory);
        exit();
    }
}

$responseMessages = [];
$overallSuccess = true;

// Handle file upload (screenshot)
if (isset($_FILES['profile_zip'])) {
    $file = $_FILES['profile_zip'];
    $fileName = basename($file['name']);
    $destination = $uploadDirectory . $fileName;

    if ($file['error'] === UPLOAD_ERR_OK) {
        if (move_uploaded_file($file['tmp_name'], $destination)) {
            $responseMessages[] = "File '$fileName' uploaded successfully.";
        } else {
            $responseMessages[] = "An error occurred while moving file '$fileName'.";
            error_log("Error moving file: " . $file['tmp_name'] . " to " . $destination);
            $overallSuccess = false;
        }
    } else {
        $responseMessages[] = "Upload error for file '$fileName': " . $file['error'];
        error_log("Upload error: " . $file['error'] . " for file " . $fileName);
        $overallSuccess = false;
    }
}

// Handle PC info upload (JSON data)
if (isset($data['pc_info'])) {
    $pcInfoFileName = 'pc_info.json';
    $pcInfoDestination = $uploadDirectory . $pcInfoFileName;
    if (file_put_contents($pcInfoDestination, json_encode($data['pc_info'], JSON_PRETTY_PRINT))) {
        $responseMessages[] = "PC info saved successfully to '$pcInfoFileName'.";
    } else {
        $responseMessages[] = "Failed to save PC info to '$pcInfoFileName'.";
        error_log("Error saving PC info to " . $pcInfoDestination);
        $overallSuccess = false;
    }
}

if (empty($responseMessages)) {
    echo json_encode(['success' => false, 'message' => 'No file or PC info received.']);
} else {
    echo json_encode(['success' => $overallSuccess, 'messages' => $responseMessages]);
}
?>
