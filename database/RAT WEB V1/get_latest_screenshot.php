<?php
// get_latest_screenshot.php
// This script returns the filename of the latest screenshot for a given PC ID as JSON.

header('Content-Type: application/json');

$baseUploadDirectory = 'uploads/';

if (!isset($_GET['pc_id']) || empty($_GET['pc_id'])) {
    echo json_encode(['success' => false, 'message' => 'PC ID not provided.']);
    exit();
}

$pcId = $_GET['pc_id'];
$pcUploadDir = $baseUploadDirectory . $pcId . '/';

if (!is_dir($pcUploadDir)) {
    echo json_encode(['success' => false, 'message' => 'PC directory not found.']);
    exit();
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

if ($latestFile) {
    echo json_encode(['success' => true, 'filename' => basename($latestFile)]);
} else {
    echo json_encode(['success' => false, 'message' => 'No screenshots found for this PC.']);
}
?>
