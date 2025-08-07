# app.py
from flask import Flask, render_template, request, Response, stream_with_context
import subprocess
import os
import socket
import time
import threading
import argparse
import platform # Import platform for OS detection
import sys # Import sys for platform check

app = Flask(__name__)

# Global variable to store installation status and output
installation_status = "idle"
installation_output = []
installation_url = ""
installation_lock = threading.Lock()
current_server_os = "Unknown" # To store the OS type detected on the server
last_attempted_install_os_type = "Unknown" # New: Stores the OS type of the last installation attempt

def get_local_ip():
    """
    Attempts to get the local IP address of the machine.
    This method tries to connect to an external server (Google DNS)
    to determine the local IP used for outbound connections,
    which is often the most reliable way to get a non-loopback IP.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception:
        # Fallback to hostname resolution if the above fails
        try:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            if ip_address == "127.0.0.1":
                # If it's still loopback, try to find a non-loopback interface
                # This is a more complex fallback, might not work in all scenarios
                try:
                    import netifaces
                    for iface in netifaces.interfaces():
                        addrs = netifaces.ifaddresses(iface)
                        if netifaces.AF_INET in addrs:
                            for link in addrs[netifaces.AF_INET]:
                                if 'addr' in link and not link['addr'].startswith('127.'):
                                    return link['addr']
                except ImportError:
                    pass # netifaces not installed, continue without it
            return ip_address
        except Exception as e:
            return f"Could not determine IP: {e}"

def get_server_os_type_internal():
    """
    Detects the operating system type of the server where this script is running.
    Returns 'Windows', 'Linux', 'Termux', or 'Unknown'.
    """
    system = platform.system()
    if system == 'Windows':
        return 'Windows'
    elif system == 'Linux':
        # Check for Termux specific environment or paths
        if os.environ.get('ANDROID_ROOT') or os.path.exists('/data/data/com.termux/files/usr/bin/pkg'):
            return 'Termux'
        else:
            return 'Linux'
    return 'Unknown'

def run_command(command, output_list):
    """
    Executes a shell command and streams its output to a list.
    """
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1  # Line-buffered output
    )
    for line in iter(process.stdout.readline, ''):
        output_list.append(line.strip())
        print(line.strip()) # Also print to console for debugging
    process.wait()
    return process.returncode

def install_dvwa_background_task(target_os_type):
    """
    Background task to perform DVWA installation based on the specified target_os_type.
    Updates global variables for status and output.
    """
    global installation_status, installation_output, installation_url, last_attempted_install_os_type

    with installation_lock:
        installation_status = "running"
        installation_output = []
        installation_url = ""
        # last_attempted_install_os_type is already set in install_dvwa()

    output_list = []
    local_ip = get_local_ip()
    os_type_of_server = get_server_os_type_internal() # Get actual OS of the server

    output_list.append(f"Starting DVWA installation for {target_os_type} on {local_ip}...")
    output_list.append("--------------------------------------------------")

    success = True
    dvwa_base_path = ""
    commands = []

    if target_os_type == 'Linux':
        dvwa_base_path = "/var/www/html/dvwa"
        commands = [
            "sudo apt update -y",
            "sudo apt install -y apache2 mariadb-server php libapache2-mod-php php-mysqli php-gd git",
            "sudo systemctl start apache2",
            "sudo systemctl enable apache2",
            "sudo systemctl start mariadb",
            "sudo systemctl enable mariadb",
            f"sudo git clone https://github.com/ethicalhack3r/DVWA.git {dvwa_base_path}",
            f"sudo cp {dvwa_base_path}/config/config.inc.php.dist {dvwa_base_path}/config/config.inc.php",
            # Configure DVWA database
            "sudo mysql -u root -e \"CREATE DATABASE dvwa;\"",
            "sudo mysql -u root -e \"CREATE USER 'dvwa'@'localhost' IDENTIFIED BY 'password';\"", # IMPORTANT: Change 'password' in a real setup!
            "sudo mysql -u root -e \"GRANT ALL ON dvwa.* TO 'dvwa'@'localhost';\"",
            "sudo mysql -u root -e \"FLUSH PRIVILEGES;\"",
            # Update DVWA config file with database credentials
            f"sudo sed -i 's/$_DVWA\\[\\'db_user\\'\\] = \\'root\\';/$_DVWA\\[\\'db_user\\'\\] = \\'dvwa\\';/g' {dvwa_base_path}/config/config.inc.php",
            f"sudo sed -i 's/$_DVWA\\[\\'db_password\\'\\] = \\'\\';/$_DVWA\\[\\'db_password\\'\\] = \\'password\\';/g' {dvwa_base_path}/config/config.inc.php",
            # Set permissions for DVWA folders
            f"sudo chmod -R 777 {dvwa_base_path}/hackable/uploads",
            f"sudo chmod -R 777 {dvwa_base_path}/external/phpids/0.6/lib/IDS/tmp",
            f"sudo chmod -R 777 {dvwa_base_path}/config",
            # Restart Apache to apply changes
            "sudo systemctl restart apache2"
        ]
        output_list.append("This process requires sudo privileges and may take some time.")
        output_list.append("Please ensure your system has internet access.")

    elif target_os_type == 'Termux':
        # Termux webroot is typically /data/data/com.termux/files/usr/share/apache2/default-site/htdocs
        dvwa_base_path = "/data/data/com.termux/files/usr/share/apache2/default-site/htdocs/dvwa"
        commands = [
            "pkg update -y && pkg upgrade -y",
            "pkg install -y apache2 mariadb php php-apache php-mysqli php-gd git",
            # Start services (Termux specific)
            "apachectl start",
            "mysqld_safe --bind-address=127.0.0.1 &", # Run MariaDB in background
            f"git clone https://github.com/ethicalhack3r/DVWA.git {dvwa_base_path}",
            f"cp {dvwa_base_path}/config/config.inc.php.dist {dvwa_base_path}/config/config.inc.php",
            # Configure DVWA database (Termux MariaDB might not need sudo mysql)
            "mysql -u root -e \"CREATE DATABASE dvwa;\"",
            "mysql -u root -e \"CREATE USER 'dvwa'@'localhost' IDENTIFIED BY 'password';\"",
            "mysql -u root -e \"GRANT ALL ON dvwa.* TO 'dvwa'@'localhost';\"",
            "mysql -u root -e \"FLUSH PRIVILEGES;\"",
            # Update DVWA config file with database credentials
            f"sed -i 's/$_DVWA\\[\\'db_user\\'\\] = \\'root\\';/$_DVWA\\[\\'db_user\\'\\] = \\'dvwa\\';/g' {dvwa_base_path}/config/config.inc.php",
            f"sed -i 's/$_DVWA\\[\\'db_password\\'\\] = \\'\\';/$_DVWA\\[\\'db_password\\'\\] = \\'password\\';/g' {dvwa_base_path}/config/config.inc.php",
            # Set permissions for DVWA folders
            f"chmod -R 777 {dvwa_base_path}/hackable/uploads",
            f"chmod -R 777 {dvwa_base_path}/external/phpids/0.6/lib/IDS/tmp",
            f"chmod -R 777 {dvwa_base_path}/config",
            # Restart Apache (Termux specific)
            "apachectl restart"
        ]
        output_list.append("This process will use Termux package manager (pkg) and specific Termux paths.")
        output_list.append("Ensure you have granted storage permissions to Termux if necessary.")

    elif target_os_type == 'Windows':
        output_list.append("Automated installation for Windows is not directly supported via this script.")
        output_list.append("Please follow these manual steps:")
        output_list.append("1. Download and install XAMPP from https://www.apachefriends.org/index.html")
        output_list.append("2. Start Apache and MySQL services in XAMPP Control Panel.")
        output_list.append("3. Download DVWA from https://github.com/ethicalhack3r/DVWA/archive/master.zip")
        output_list.append("4. Extract the DVWA ZIP file and rename the folder to 'dvwa'.")
        output_list.append("5. Move the 'dvwa' folder to your XAMPP's htdocs directory (e.g., C:\\xampp\\htdocs\\).")
        output_list.append("6. Navigate to C:\\xampp\\htdocs\\dvwa\\config\\ and rename 'config.inc.php.dist' to 'config.inc.php'.")
        output_list.append("7. Edit 'config.inc.php' and set the database user to 'root' and leave the password empty (or set 'dvwa'/'password' if you create that user in phpMyAdmin).")
        output_list.append("8. Access DVWA in your browser at http://localhost/dvwa/setup.php")
        output_list.append("9. Click 'Create/Reset Database' to finalize setup.")
        output_list.append("Default credentials: admin / password (after database reset).")
        success = True # Mark as successful as instructions are provided
        dvwa_base_path = "C:/xampp/htdocs/dvwa" # Placeholder for URL construction

    elif target_os_type == 'Docker':
        output_list.append("Attempting to install DVWA using Docker.")
        output_list.append("This requires Docker to be installed and running on your system.")
        output_list.append("If Docker is not installed, the process will likely fail.")
        output_list.append("--------------------------------------------------")

        # Determine if sudo is needed for docker commands based on server OS
        docker_prefix = "sudo " if os_type_of_server == 'Linux' else ""

        # Check if docker is installed and daemon is running
        check_docker_cmd = f"{docker_prefix}docker info"
        output_list.append(f"\nChecking Docker status: {check_docker_cmd}")
        ret_code = run_command(check_docker_cmd, output_list)
        if ret_code != 0:
            output_list.append("Docker daemon is not running or Docker is not installed/configured correctly.")
            output_list.append("Please install Docker Desktop (Windows/macOS) or Docker Engine (Linux) and ensure it's running.")
            if os_type_of_server == 'Linux':
                output_list.append("For Linux, you might need to add your user to the 'docker' group: 'sudo usermod -aG docker $USER' and then re-login.")
            success = False
        else:
            # Stop any existing dvwa_container
            stop_existing_container = f"{docker_prefix}docker stop dvwa_container"
            output_list.append(f"\nAttempting to stop any existing DVWA container: {stop_existing_container}")
            run_command(stop_existing_container, output_list) # Don't check return code, it might not exist

            # Remove any existing dvwa_container
            remove_existing_container = f"{docker_prefix}docker rm dvwa_container"
            output_list.append(f"\nAttempting to remove any existing DVWA container: {remove_existing_container}")
            run_command(remove_existing_container, output_list) # Don't check return code, it might not exist

            commands = [
                f"{docker_prefix}docker pull vulnerables/web-dvwa",
                f"{docker_prefix}docker run -d --rm -p 80:80 --name dvwa_container vulnerables/web-dvwa"
            ]
            for cmd in commands:
                output_list.append(f"\nExecuting: {cmd}")
                ret_code = run_command(cmd, output_list)
                if ret_code != 0:
                    output_list.append(f"Command failed with exit code {ret_code}. Docker installation failed.")
                    success = False
                    break
        if success:
            installation_url = f"http://{local_ip}/dvwa/setup.php" # Docker runs on host port 80
            output_list.append("DVWA Docker container started successfully.")
            output_list.append("Please wait a few moments for the container to initialize.")
            output_list.append("Then navigate to the URL and click 'Create/Reset Database' to finalize setup.")
            output_list.append("Default credentials: admin / password")
            output_list.append("If port 80 is already in use, you might need to stop the conflicting service (e.g., Apache) or run Docker with a different port mapping (e.g., -p 8080:80).")

    else:
        output_list.append("Unsupported operating system detected. Cannot proceed with installation.")
        success = False

    if target_os_type in ['Linux', 'Termux', 'Docker']: # Docker also uses shell commands
        for cmd in commands:
            if not success: # Stop if a previous command failed
                break
            output_list.append(f"\nExecuting: {cmd}")
            ret_code = run_command(cmd, output_list)
            if ret_code != 0:
                output_list.append(f"Command failed with exit code {ret_code}.")
                success = False
                break

    with installation_lock:
        if success:
            installation_status = "completed"
            if target_os_type == 'Windows':
                installation_url = "http://localhost/dvwa/setup.php (Manual Setup Required)"
            elif target_os_type == 'Termux':
                # Termux Apache usually runs on port 8080 by default
                installation_url = f"http://{local_ip}:8080/dvwa/setup.php"
            elif target_os_type == 'Docker':
                installation_url = f"http://{local_ip}/dvwa/setup.php" # Docker maps to host port 80
            else: # Linux
                installation_url = f"http://{local_ip}/dvwa/setup.php"

            output_list.append("\n--------------------------------------------------")
            output_list.append("DVWA installation process completed!")
            output_list.append(f"Access DVWA at: {installation_url}")
            output_list.append("Default credentials: admin / password")
            output_list.append("Please navigate to the URL and click 'Create/Reset Database' to finalize setup.")
            output_list.append("Remember to change the default password after logging in.")
        else:
            installation_status = "failed"
            output_list.append("\n--------------------------------------------------")
            output_list.append("DVWA installation failed. Please check the output for errors.")
        installation_output.extend(output_list) # Append the collected output to the global list

@app.route('/')
def index():
    """
    Renders the main HTML page.
    """
    return render_template('index.html')

@app.route('/install_dvwa', methods=['POST'])
def install_dvwa():
    """
    Initiates the DVWA installation process in a background thread.
    Expects 'os_type' in the request body.
    Returns an immediate response to the client.
    """
    global installation_status, last_attempted_install_os_type

    target_os_type = request.json.get('os_type', 'Unknown')
    if target_os_type not in ['Windows', 'Linux', 'Termux', 'Docker']:
        return Response("Invalid OS type specified.", status=400, mimetype='text/plain')

    with installation_lock:
        if installation_status == "running":
            return Response("Installation already in progress.", status=409, mimetype='text/plain')
        installation_status = "starting" # Set status to starting before thread starts
        last_attempted_install_os_type = target_os_type # Set this here

    # Start the installation in a new thread, passing the target_os_type
    thread = threading.Thread(target=install_dvwa_background_task, args=(target_os_type,))
    thread.daemon = True # Allow the main program to exit even if thread is running
    thread.start()

    return Response("Installation started. Check /stream_output for progress.", status=202, mimetype='text/plain')

@app.route('/stream_output')
def stream_output():
    """
    Streams the installation output to the client.
    """
    def generate():
        global installation_output, installation_status
        last_index = 0
        while installation_status in ["starting", "running"]:
            with installation_lock:
                if len(installation_output) > last_index:
                    for i in range(last_index, len(installation_output)):
                        yield f"data:{installation_output[i]}\n\n"
                    last_index = len(installation_output)
            time.sleep(1) # Wait a bit before checking for new output

        # After installation is complete (success or failure), send final output
        with installation_lock:
            for i in range(last_index, len(installation_output)):
                yield f"data:{installation_output[i]}\n\n"
            yield f"data:INSTALLATION_STATUS:{installation_status}\n\n"
            if installation_status == "completed":
                yield f"data:DVWA_URL:{installation_url}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/get_status')
def get_status():
    """
    Returns the current installation status, URL, and last attempted OS type.
    """
    with installation_lock:
        return {
            "status": installation_status,
            "url": installation_url,
            "output_length": len(installation_output),
            "last_attempted_os_type": last_attempted_install_os_type # Use the new global variable
        }

@app.route('/get_server_os')
def get_server_os():
    """
    Returns the detected OS type of the server.
    """
    global current_server_os
    current_server_os = get_server_os_type_internal() # Update the global variable
    return {"os_type": current_server_os}

if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="DVWA Installer Flask App")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the Flask app on")
    args = parser.parse_args()

    # Ensure the templates directory exists for Flask to find index.html
    os.makedirs('templates', exist_ok=True)

    # Create the index.html file
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DVWA Installer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f0f4f8;
            color: #334155;
        }
        .container {
            max-width: 900px;
            margin: 4rem auto;
            padding: 2rem;
            background-color: #ffffff;
            border-radius: 1rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        }
        .btn {
            background-image: linear-gradient(to right, #6366f1 0%, #8b5cf6 100%);
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 0.75rem;
            font-weight: 600;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3);
            cursor: pointer;
            border: none;
            outline: none;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 15px rgba(99, 102, 241, 0.4);
        }
        .btn:active {
            transform: translateY(0);
            box-shadow: 0 2px 5px rgba(99, 102, 241, 0.2);
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            box-shadow: none;
        }
        .output-box {
            background-color: #1e293b;
            color: #e2e8f0;
            padding: 1.5rem;
            border-radius: 0.75rem;
            font-family: 'monospace';
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #334155;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
        }
        .status-message {
            padding: 0.75rem 1.25rem;
            border-radius: 0.5rem;
            font-weight: 600;
            margin-top: 1rem;
            text-align: center;
        }
        .status-running {
            background-color: #bfdbfe;
            color: #1e40af;
        }
        .status-completed {
            background-color: #d1fae5;
            color: #065f46;
        }
        .status-failed {
            background-color: #fee2e2;
            color: #991b1b;
        }
        .hidden {
            display: none;
        }
    </style>
</head>
<body class="antialiased">
    <div class="container">
        <h1 class="text-4xl font-bold text-center mb-8 text-gray-800">DVWA Installer</h1>

        <div class="flex justify-center space-x-4 mb-8">
            <button id="installLinuxButton" class="btn" data-os-type="Linux">
                <span id="buttonTextLinux">Install DVWA (Linux)</span>
            </button>
            <button id="installWindowsButton" class="btn" data-os-type="Windows">
                <span id="buttonTextWindows">Install DVWA (Windows)</span>
            </button>
            <button id="installTermuxButton" class="btn" data-os-type="Termux">
                <span id="buttonTextTermux">Install DVWA (Termux)</span>
            </button>
            <button id="installDockerButton" class="btn" data-os-type="Docker">
                <span id="buttonTextDocker">Install DVWA (Docker)</span>
            </button>
        </div>

        <div id="statusMessage" class="status-message hidden"></div>

        <div class="mt-8">
            <h2 class="text-2xl font-semibold mb-4 text-gray-700">Installation Output:</h2>
            <div id="output" class="output-box">
                Waiting for installation to start...
            </div>
        </div>

        <div id="dvwaUrlContainer" class="mt-8 hidden">
            <h2 class="text-2xl font-semibold mb-4 text-gray-700">DVWA URL:</h2>
            <p id="dvwaUrl" class="text-lg text-blue-600 font-medium break-words"></p>
            <p class="text-sm text-gray-500 mt-2">
                Default credentials: <span class="font-bold">admin</span> / <span class="font-bold">password</span>.
                Please navigate to the URL and click 'Create/Reset Database' to finalize setup.
                Remember to change the default password after logging in.
            </p>
        </div>
    </div>

    <script>
        const installLinuxButton = document.getElementById('installLinuxButton');
        const installWindowsButton = document.getElementById('installWindowsButton');
        const installTermuxButton = document.getElementById('installTermuxButton');
        const installDockerButton = document.getElementById('installDockerButton'); // New Docker button
        const outputDiv = document.getElementById('output');
        const statusMessageDiv = document.getElementById('statusMessage');
        const dvwaUrlContainer = document.getElementById('dvwaUrlContainer');
        const dvwaUrlP = document.getElementById('dvwaUrl');

        let eventSource = null;
        let isInstalling = false;
        let currentOS = 'Unknown'; // To store the detected server OS

        function updateButtonStates(status, lastAttemptedOsType = '') {
            const buttons = [
                { btn: installLinuxButton, os: 'Linux' },
                { btn: installWindowsButton, os: 'Windows' },
                { btn: installTermuxButton, os: 'Termux' },
                { btn: installDockerButton, os: 'Docker' }
            ];

            buttons.forEach(({ btn, os }) => {
                const buttonTextSpan = btn.querySelector('span');
                if (status === 'starting' || status === 'running') {
                    btn.disabled = true;
                    if (buttonTextSpan) buttonTextSpan.textContent = 'Installing...';
                } else {
                    // Enable/disable based on detected OS and specific installation type
                    if (os === 'Linux') {
                        btn.disabled = (currentOS !== 'Linux');
                    } else if (os === 'Windows') {
                        btn.disabled = (currentOS !== 'Windows');
                    } else if (os === 'Termux') {
                        btn.disabled = (currentOS !== 'Termux');
                    } else if (os === 'Docker') { // Docker button logic
                        btn.disabled = (currentOS !== 'Linux' && currentOS !== 'Windows'); // Docker is primarily for Linux/Windows
                    } else {
                        btn.disabled = true; // Unknown OS
                    }

                    if (buttonTextSpan) buttonTextSpan.textContent = `Install DVWA (${os})`;
                }
            });

            // If installation is completed or failed, specifically re-enable the button that was clicked
            if (status === 'completed' || status === 'failed') {
                const targetButton = buttons.find(b => b.os === lastAttemptedOsType)?.btn;
                if (targetButton) {
                    targetButton.disabled = false;
                    const buttonTextSpan = targetButton.querySelector('span');
                    if (buttonTextSpan) {
                        buttonTextSpan.textContent = (status === 'completed' ? `Install DVWA (${lastAttemptedOsType}) Again` : `Retry Installation (${lastAttemptedOsType})`);
                    }
                }
            }
        }


        function updateStatusDisplay(status, url = '', lastAttemptedOsType = '') {
            statusMessageDiv.classList.remove('hidden', 'status-running', 'status-completed', 'status-failed');
            dvwaUrlContainer.classList.add('hidden');
            dvwaUrlP.textContent = '';

            updateButtonStates(status, lastAttemptedOsType); // Update button states based on installation status

            if (status === 'starting' || status === 'running') {
                statusMessageDiv.textContent = 'Installation in progress... This may take a few minutes.';
                statusMessageDiv.classList.add('status-running');
            } else if (status === 'completed') {
                statusMessageDiv.textContent = 'Installation completed successfully!';
                statusMessageDiv.classList.add('status-completed');
                if (url) {
                    dvwaUrlContainer.classList.remove('hidden');
                    dvwaUrlP.innerHTML = `<a href="${url}" target="_blank" class="text-blue-600 hover:underline">${url}</a>`;
                }
            } else if (status === 'failed') {
                statusMessageDiv.textContent = 'Installation failed. Check output for details.';
                statusMessageDiv.classList.add('status-failed');
            } else { // idle
                statusMessageDiv.classList.add('hidden');
            }
        }

        function startInstallation(osTypeToInstall) {
            if (isInstalling) return;

            isInstalling = true;
            outputDiv.textContent = 'Initiating installation...';
            updateStatusDisplay('starting', osTypeToInstall); // Pass osTypeToInstall here

            // Clear previous output
            outputDiv.innerHTML = '';

            fetch('/install_dvwa', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ os_type: osTypeToInstall }) // Pass the selected OS type
            })
                .then(response => {
                    if (response.status === 202) {
                        console.log('Installation request accepted.');
                        // Start streaming output
                        if (eventSource) {
                            eventSource.close();
                        }
                        eventSource = new EventSource('/stream_output');
                        eventSource.onmessage = function(event) {
                            if (event.data.startsWith('INSTALLATION_STATUS:')) {
                                const status = event.data.split(':')[1];
                                updateStatusDisplay(status, osTypeToInstall); // Pass osTypeToInstall here
                                if (status !== 'running' && status !== 'starting') {
                                    eventSource.close();
                                    isInstalling = false;
                                }
                            } else if (event.data.startsWith('DVWA_URL:')) {
                                const url = event.data.split(':')[1];
                                updateStatusDisplay('completed', url, osTypeToInstall); // Pass osTypeToInstall here
                            } else {
                                const p = document.createElement('p');
                                p.textContent = event.data;
                                outputDiv.appendChild(p);
                                outputDiv.scrollTop = outputDiv.scrollHeight; // Scroll to bottom
                            }
                        };
                        eventSource.onerror = function(err) {
                            console.error('EventSource failed:', err);
                            outputDiv.innerHTML += '<p class="text-red-400">Error streaming output. Check console.</p>';
                            updateStatusDisplay('failed', osTypeToInstall); // Pass osTypeToInstall here
                            if (eventSource) eventSource.close();
                            isInstalling = false;
                        };
                    } else if (response.status === 409) {
                        outputDiv.textContent = 'Installation is already in progress.';
                        updateStatusDisplay('running', osTypeToInstall); // Pass osTypeToInstall here
                        isInstalling = true; // Ensure flag is set if already running
                    } else {
                        response.text().then(text => {
                            outputDiv.textContent = `Error: ${response.status} - ${text}`;
                            updateStatusDisplay('failed', osTypeToInstall); // Pass osTypeToInstall here
                            isInstalling = false;
                        });
                    }
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                    outputDiv.textContent = `Failed to start installation: ${error}`;
                    updateStatusDisplay('failed', osTypeToInstall); // Pass osTypeToInstall here
                    isInstalling = false;
                });
        }

        // Add event listeners for the buttons, passing their data-os-type
        installLinuxButton.addEventListener('click', () => startInstallation(installLinuxButton.dataset.osType));
        installWindowsButton.addEventListener('click', () => startInstallation(installWindowsButton.dataset.osType));
        installTermuxButton.addEventListener('click', () => startInstallation(installTermuxButton.dataset.osType));
        installDockerButton.addEventListener('click', () => startInstallation(installDockerButton.dataset.osType)); // New event listener

        // Function to detect server OS and show appropriate button
        async function initializeInstaller() {
            try {
                const osResponse = await fetch('/get_server_os');
                const osData = await osResponse.json();
                currentOS = osData.os_type;
                console.log('Server OS detected:', currentOS);

                // No longer hiding buttons, just updating their states
                // updateButtonStates('idle'); // This will be called after fetching status

                // Then, check installation status
                const statusResponse = await fetch('/get_status');
                const statusData = await statusResponse.json();
                updateStatusDisplay(statusData.status, statusData.url, statusData.last_attempted_os_type); // Pass last_attempted_os_type

                if (statusData.status === 'running' || statusData.status === 'starting') {
                    isInstalling = true;
                    // Re-attach event source to continue streaming
                    if (eventSource) {
                        eventSource.close();
                    }
                    eventSource = new EventSource('/stream_output');
                    eventSource.onmessage = function(event) {
                        if (event.data.startsWith('INSTALLATION_STATUS:')) {
                            const status = event.data.split(':')[1];
                            updateStatusDisplay(status, statusData.url, statusData.last_attempted_os_type); // Pass last_attempted_os_type
                            if (status !== 'running' && status !== 'starting') {
                                eventSource.close();
                                isInstalling = false;
                            }
                        } else if (event.data.startsWith('DVWA_URL:')) {
                            const url = event.data.split(':')[1];
                            updateStatusDisplay('completed', url, statusData.last_attempted_os_type); // Pass last_attempted_os_type
                        } else {
                            const p = document.createElement('p');
                            p.textContent = event.data;
                            outputDiv.appendChild(p);
                            outputDiv.scrollTop = outputDiv.scrollHeight;
                        }
                    };
                    eventSource.onerror = function(err) {
                        console.error('EventSource failed during re-attachment:', err);
                        outputDiv.innerHTML += '<p class="text-red-400">Error streaming output. Check console.</p>';
                        updateStatusDisplay('failed', statusData.url, statusData.last_attempted_os_type); // Pass last_attempted_os_type
                        if (eventSource) eventSource.close();
                        isInstalling = false;
                    };
                }
            } catch (error) {
                console.error('Failed to initialize installer:', error);
                outputDiv.textContent = 'Failed to load initial status or detect server OS.';
            }
        }

        document.addEventListener('DOMContentLoaded', initializeInstaller);
    </script>
</body>
</html>
"""
    with open('templates/index.html', 'w') as f:
        f.write(html_content)

    app.run(host='0.0.0.0', port=args.port, debug=False) # Use the port from arguments
