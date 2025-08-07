<?php
// Define base directories
$databaseBaseDir = __DIR__ . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR . 'database';
$pidsDir = __DIR__ . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR . 'pids';
$nextPortFile = __DIR__ . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR . 'next_port.txt';
const SETTINGS_FILE = __DIR__ . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR . 'settings.json';
const NOTES_FILE_NAME = 'notes.txt';
const SCREEN_FILE_NAME = 'screen.txt'; // Constant for screen.txt file name

// Define the web server's port for PHP app URLs.
// IMPORTANT: Adjust this to your actual Apache/XAMPP port.
// You stated your server is on Port 8080.
const WEB_SERVER_PORT = 8080;
?>
