<?php
// Include config to access SETTINGS_FILE constant
require_once __DIR__ . DIRECTORY_SEPARATOR . 'config.php';

/**
 * Function to read settings from settings.json.
 * @return array The settings array.
 */
function getSettings() {
    if (file_exists(SETTINGS_FILE)) {
        $settings = json_decode(file_get_contents(SETTINGS_FILE), true);
        // Ensure default values if settings are missing
        return array_merge(['showCover' => true, 'enableCardAnimation' => true, 'openInIframe' => false, 'showFullUrl' => false, 'enableTaskbar' => false], $settings ?: []);
    }
    // Default settings if file doesn't exist
    return ['showCover' => true, 'enableCardAnimation' => true, 'openInIframe' => false, 'showFullUrl' => false, 'enableTaskbar' => false];
}

/**
 * Function to save settings to settings.json.
 * @param array $settings The settings array to save.
 * @return bool True on success, false on failure.
 */
function saveSettings($settings) {
    return file_put_contents(SETTINGS_FILE, json_encode($settings, JSON_PRETTY_PRINT));
}
?>
