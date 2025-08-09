<?php

// Path to the settings JSON file
$settings_file = 'settings.json';

// Initialize a message variable for user feedback
$message = '';
$message_class = '';

// Check if the form was submitted
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Check if the base_url was submitted
    if (isset($_POST['base_url'])) {
        $new_base_url = $_POST['base_url'];

        // Read the current settings from the file
        if (file_exists($settings_file)) {
            $json_data = file_get_contents($settings_file);
            $settings = json_decode($json_data, true);

            // Update the base_url in the array
            $settings['base_url'] = $new_base_url;

            // Encode the array back to JSON format
            $updated_json_data = json_encode($settings, JSON_PRETTY_PRINT);

            // Write the updated data back to the file
            if (file_put_contents($settings_file, $updated_json_data)) {
                $message = 'Settings saved successfully!';
                $message_class = 'success';
            } else {
                $message = 'Error: Could not write to the settings file. Check file permissions.';
                $message_class = 'error';
            }
        } else {
            $message = 'Error: settings.json file not found.';
            $message_class = 'error';
        }
    }
}

// Read the settings from the file to display in the form
$base_url = '';
if (file_exists($settings_file)) {
    $json_data = file_get_contents($settings_file);
    $settings = json_decode($json_data, true);
    if (isset($settings['base_url'])) {
        $base_url = $settings['base_url'];
    }
}

?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Website Settings</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: #121212; /* Dark background */
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            color: #e0e0e0; /* Light text color */
        }
        .settings-container {
            background-color: #1e1e1e; /* Darker container background */
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4); /* Deeper shadow for contrast */
            width: 100%;
            max-width: 400px;
            box-sizing: border-box;
        }
        h1 {
            text-align: center;
            color: #e0e0e0; /* Light heading text */
            margin-bottom: 1.5rem;
        }
        .form-group {
            margin-bottom: 1rem;
        }
        label {
            display: block;
            margin-bottom: 0.5rem;
            color: #e0e0e0; /* Light label text */
            font-weight: 600;
        }
        input[type="text"] {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #444; /* Darker border */
            background-color: #2b2b2b; /* Dark input background */
            color: #fff; /* White text in input */
            border-radius: 8px;
            box-sizing: border-box;
            font-size: 1rem;
            transition: border-color 0.2s ease;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #007bff;
            box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.4);
        }
        .btn-save {
            width: 100%;
            padding: 0.75rem;
            background-color: #007bff;
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s ease;
        }
        .btn-save:hover {
            background-color: #0056b3;
        }
        .message {
            text-align: center;
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 8px;
            font-weight: 600;
        }
        .message.success {
            background-color: #214d2e; /* Darker success background */
            color: #a3e9b1; /* Lighter success text */
            border: 1px solid #376f44;
        }
        .message.error {
            background-color: #6d2f32; /* Darker error background */
            color: #f7a7a7; /* Lighter error text */
            border: 1px solid #994c50;
        }
    </style>
</head>
<body>
    <div class="settings-container">
        <h1>Website Settings</h1>
        <?php if (!empty($message)): ?>
            <div class="message <?php echo $message_class; ?>"><?php echo $message; ?></div>
        <?php endif; ?>
        <form method="POST" action="">
            <div class="form-group">
                <label for="base_url">Base URL</label>
                <input type="text" id="base_url" name="base_url" value="<?php echo htmlspecialchars($base_url); ?>">
            </div>
            <button type="submit" class="btn-save">Save Settings</button>
        </form>
    </div>
</body>
</html>
