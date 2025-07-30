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

app = Flask(__name__)

# Directory to store temporary files (e.g., uploaded target lists, scan outputs)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# In-memory storage for scan outputs (for demonstration).
# In a real-world app, consider a more persistent and scalable solution (e.g., database, cloud storage).
scan_outputs = {}
scan_processes = {} # To keep track of running WPScan processes
scan_queues = {} # To store queues for real-time output

# Load examples from wpscan_examples.txt
def load_examples(filename="wpscan_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming wpscan_examples.txt is in the same directory as app.py
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

ALL_EXAMPLES = load_examples()

@app.route('/')
def index():
    """Renders the main WPScan GUI HTML page."""
    # The examples are now loaded via a separate API call in the frontend,
    # so no need to pass them directly to render_template here.
    return render_template('index.html')

# New endpoint to serve WPScan examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the WPScan examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the WPScan command based on form data."""
    data = request.json
    command_parts = ["wpscan"]

    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value)))

    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Target Tab
    if data.get('target_url_entry'):
        command_parts.append(f"--url {shlex.quote(data['target_url_entry'])}")
    add_checkbox_arg("--random-agent", data.get('random_agent_var'))
    add_arg("--user-agent", data.get('user_agent_entry'))
    add_arg("--proxy", data.get('proxy_entry'))
    add_arg("--proxy-auth", data.get('proxy_auth_entry'))
    add_arg("--cookie", data.get('cookie_entry'))
    add_arg("--cookie-string", data.get('cookie_string_entry'))
    
    headers = data.get('headers_entry', '').strip()
    if headers:
        for header_line in headers.split('\n'):
            header_line = header_line.strip()
            if header_line:
                command_parts.append("--headers")
                command_parts.append(shlex.quote(header_line))

    add_checkbox_arg("--ignore-main-redirect", data.get('ignore_main_redirect_var'))
    add_checkbox_arg("--follow-redirects", data.get('follow_redirects_var'))
    add_checkbox_arg("--force", data.get('force_var'))

    # Enumeration Tab
    enumerate_options = []
    if data.get('enumerate_users_var'): enumerate_options.append("u")
    if data.get('enumerate_plugins_var'): enumerate_options.append("p")
    if data.get('enumerate_themes_var'): enumerate_options.append("t")
    if data.get('enumerate_timthumb_var'): enumerate_options.append("tt")
    if data.get('enumerate_media_var'): enumerate_options.append("m")
    if data.get('enumerate_config_backups_var'): enumerate_options.append("cb")
    if data.get('enumerate_db_exports_var'): enumerate_options.append("dbe")
    if data.get('enumerate_uploads_var'): enumerate_options.append("uploads")
    
    enumerate_profile = data.get('enumerate_profile_select')
    if enumerate_profile == 'v': enumerate_options.append("v")
    elif enumerate_profile == 'vp': enumerate_options.append("vp")
    elif enumerate_profile == 'vt': enumerate_options.append("vt")
    elif enumerate_profile == 'ap': enumerate_options.append("ap")
    elif enumerate_profile == 'at': enumerate_options.append("at")
    elif enumerate_profile == 'e': enumerate_options.append("e")

    if enumerate_options:
        command_parts.append(f"--enumerate {','.join(enumerate_options)}")

    add_arg("--exclude-content-based", data.get('exclude_content_based_entry'))
    add_arg("--exclude-status-code", data.get('exclude_status_code_entry'))

    # Vulnerability Detection Tab
    if data.get('api_token_entry'):
        command_parts.append(f"--api-token {shlex.quote(data['api_token_entry'])}")
    add_checkbox_arg("--wp-version-detection", data.get('wp_version_detection_var'))
    add_checkbox_arg("--plugins-detection", data.get('plugins_detection_var'))
    add_checkbox_arg("--themes-detection", data.get('themes_detection_var'))
    add_checkbox_arg("--latest-versions", data.get('latest_versions_var'))

    # Bruteforce Tab
    add_arg("--passwords", data.get('passwords_entry'))
    add_arg("--passwords-file", data.get('passwords_file_entry'))
    add_arg("--usernames", data.get('usernames_entry'))
    add_arg("--usernames-file", data.get('usernames_file_entry'))

    # Timing/Performance Tab
    add_arg("--request-timeout", data.get('request_timeout_entry'))
    add_arg("--connect-timeout", data.get('connect_timeout_entry'))
    add_arg("--max-threads", data.get('max_threads_entry'))
    add_arg("--batch-size", data.get('batch_size_entry'))
    add_arg("--throttle", data.get('throttle_entry'))

    # Output Tab
    add_arg("--log-file", data.get('log_file_entry'))
    add_arg("--format", data.get('format_select'))
    add_checkbox_arg("--no-color", data.get('no_color_var'))
    add_checkbox_arg("--no-banner", data.get('no_banner_var'))
    add_checkbox_arg("--no-progress-bar", data.get('no_progress_bar_var'))
    add_checkbox_arg("--verbose", data.get('verbose_var'))
    add_checkbox_arg("--debug", data.get('debug_var'))

    # Advanced Tab
    add_arg("--url-detection", data.get('url_detection_select'))
    add_arg("--scope", data.get('scope_entry'))
    add_arg("--exclude-pattern", data.get('exclude_pattern_entry'))
    add_arg("--include-pattern", data.get('include_pattern_entry'))
    add_arg("--max-scan-duration", data.get('max_scan_duration_entry'))
    add_arg("--max-scan-retries", data.get('max_scan_retries_entry'))
    add_arg("--scan-timeout", data.get('scan_timeout_entry'))
    add_arg("--user-agent-file", data.get('user_agent_file_entry'))
    add_arg("--random-user-agent", data.get('random_user_agent_var'))
    add_arg("--plugins-file", data.get('plugins_file_entry'))
    add_arg("--themes-file", data.get('themes_file_entry'))
    add_arg("--ignore-vulnerable-regex", data.get('ignore_vulnerable_regex_entry'))
    add_arg("--ignore-vulnerable-slug", data.get('ignore_vulnerable_slug_entry'))
    add_arg("--ignore-vulnerable-version", data.get('ignore_vulnerable_version_entry'))
    add_arg("--ignore-vulnerable-status", data.get('ignore_vulnerable_status_entry'))
    add_arg("--ignore-vulnerable-type", data.get('ignore_vulnerable_type_entry'))
    add_arg("--ignore-vulnerable-severity", data.get('ignore_vulnerable_severity_entry'))
    add_arg("--ignore-vulnerable-cvss", data.get('ignore_vulnerable_cvss_entry'))
    add_arg("--ignore-vulnerable-references", data.get('ignore_vulnerable_references_entry'))
    add_arg("--ignore-vulnerable-patch", data.get('ignore_vulnerable_patch_entry'))
    add_arg("--ignore-vulnerable-fix", data.get('ignore_vulnerable_fix_entry'))
    add_arg("--ignore-vulnerable-date", data.get('ignore_vulnerable_date_entry'))
    add_arg("--ignore-vulnerable-tags", data.get('ignore_vulnerable_tags_entry'))
    add_arg("--ignore-vulnerable-notes", data.get('ignore_vulnerable_notes_entry'))
    add_arg("--ignore-vulnerable-description", data.get('ignore_vulnerable_description_entry'))
    add_arg("--ignore-vulnerable-title", data.get('ignore_vulnerable_title_entry'))
    add_arg("--ignore-vulnerable-cve", data.get('ignore_vulnerable_cve_entry'))
    add_arg("--ignore-vulnerable-exploit", data.get('ignore_vulnerable_exploit_entry'))
    add_arg("--ignore-vulnerable-disclosure", data.get('ignore_vulnerable_disclosure_entry'))
    add_arg("--ignore-vulnerable-references-url", data.get('ignore_vulnerable_references_url_entry'))
    add_arg("--ignore-vulnerable-references-type", data.get('ignore_vulnerable_references_type_entry'))
    add_arg("--ignore-vulnerable-references-id", data.get('ignore_vulnerable_references_id_entry'))
    add_arg("--ignore-vulnerable-references-title", data.get('ignore_vulnerable_references_title_entry'))
    add_arg("--ignore-vulnerable-references-date", data.get('ignore_vulnerable_references_date_entry'))
    add_arg("--ignore-vulnerable-references-tags", data.get('ignore_vulnerable_references_tags_entry'))
    add_arg("--ignore-vulnerable-references-notes", data.get('ignore_vulnerable_references_notes_entry'))
    add_arg("--ignore-vulnerable-references-description", data.get('ignore_vulnerable_references_description_entry'))
    add_arg("--ignore-vulnerable-references-cve", data.get('ignore_vulnerable_references_cve_entry'))
    add_arg("--ignore-vulnerable-references-exploit", data.get('ignore_vulnerable_references_exploit_entry'))
    add_arg("--ignore-vulnerable-references-disclosure", data.get('ignore_vulnerable_references_disclosure_entry'))
    
    additional_args = data.get('additional_args_entry', '').strip()
    if additional_args:
        try:
            split_args = shlex.split(additional_args)
            command_parts.extend(split_args)
        except ValueError:
            # Fallback if shlex can't parse, just add as a single string (less safe)
            command_parts.append(shlex.quote(additional_args))

    generated_cmd = " ".join(command_parts)
    return jsonify({'command': generated_cmd})

@app.route('/run_wpscan', methods=['POST'])
def run_wpscan():
    """
    Executes the WPScan command received from the frontend.
    IMPORTANT: Running arbitrary commands from user input on a web server is a severe security risk.
    This implementation is for demonstration and should NOT be used in a production environment
    without extensive security measures, input validation, and sandboxing.
    """
    data = request.json
    command_str = data.get('command')
    scan_id = str(uuid.uuid4()) # Unique ID for this scan

    if not command_str:
        return jsonify({'status': 'error', 'message': 'No command provided.'}), 400

    # Basic check to prevent common dangerous commands. This is NOT exhaustive.
    if any(cmd in command_str for cmd in ['rm ', 'sudo ', 'reboot', 'shutdown', 'init ']):
        return jsonify({'status': 'error', 'message': 'Potentially dangerous command detected. Operation aborted.'}), 403

    # Use shlex.split to safely split the command string into a list
    try:
        command = shlex.split(command_str)
    except ValueError as e:
        return jsonify({'status': 'error', 'message': f'Error parsing command: {e}'}), 400

    # Ensure wpscan is the command being run
    if command[0] != 'wpscan':
        return jsonify({'status': 'error', 'message': 'Only WPScan commands are allowed.'}), 403

    # Check if wpscan executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"WPScan executable '{command[0]}' not found on the server. Please ensure WPScan is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this scan's real-time output
    output_queue = queue.Queue()
    scan_queues[scan_id] = output_queue
    scan_outputs[scan_id] = "" # Initialize full output storage

    def _run_wpscan_thread(cmd, q, scan_id_val):
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
            scan_processes[scan_id_val] = process

            for line in iter(process.stdout.readline, ''):
                q.put(line) # Put each line into the queue
                full_output_buffer.append(line) # Also append to buffer for final output

            process.wait()
            return_code = process.returncode

            final_status_line = f"\nWPScan finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            scan_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure WPScan is installed and in your system's PATH.\nSTATUS: Error\n"
            q.put(error_msg)
            scan_outputs[scan_id_val] = error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}\nSTATUS: Error\n"
            q.put(error_msg)
            scan_outputs[scan_id_val] = error_msg
        finally:
            if scan_id_val in scan_processes:
                del scan_processes[scan_id_val]
            # Signal end of output by putting a special marker
            q.put("---SCAN_COMPLETE---")


    # Start the WPScan process in a separate thread
    thread = threading.Thread(target=_run_wpscan_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'WPScan scan started.'})

@app.route('/get_scan_output/<scan_id>', methods=['GET'])
def get_scan_output(scan_id):
    """
    Polls for real-time WPScan scan output.
    Returns new lines from the queue or the final output if scan is complete.
    """
    output_queue = scan_queues.get(scan_id)
    if not output_queue:
        # If queue is not found, check if the scan completed and its final output is stored
        final_output = scan_outputs.get(scan_id)
        final_status = scan_outputs.get(scan_id + "_status") # Check for installation status
        if final_output and final_status:
            return jsonify({'status': final_status, 'output': final_output})
        elif final_output: # If it's a regular scan that completed
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
        del scan_queues[scan_id]
        status_to_return = 'completed'
        if install_success:
            status_to_return = 'success'
        elif install_failure:
            status_to_return = 'error'
        
        # Ensure the final output includes all accumulated output
        final_output_content = scan_outputs.get(scan_id, "Scan/Installation completed, but output not fully captured.")
        return jsonify({'status': status_to_return, 'output': final_output_content})
    else:
        # Scan/Installation is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})


@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the provided content to a file on the server and allows download."""
    data = request.json
    content = data.get('content')
    filename = data.get('filename', f'wpscan_output_{uuid.uuid4()}.txt')

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

@app.route('/install_wpscan', methods=['POST'])
def install_wpscan():
    """
    Attempts to install WPScan on the server (Linux/Termux only).
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
        scan_queues[scan_id] = output_queue
        scan_outputs[scan_id] = "" # Initialize full output storage for this ID

        def _install_thread(q, current_scan_id, p_type):
            temp_buffer_thread = [] # Local buffer for the thread
            try:
                if p_type == 'termux':
                    # WPScan on Termux often requires Ruby first
                    update_command = shlex.split("pkg update -y")
                    install_ruby_command = shlex.split("pkg install ruby -y")
                    install_wpscan_command = shlex.split("gem install wpscan")
                    q.put("Detected Termux. Using 'pkg' and 'gem' for installation.\n")
                    commands_to_run = [update_command, install_ruby_command, install_wpscan_command]
                elif p_type == 'linux':
                    # WPScan on Linux is typically installed via gem after ruby, or directly via apt if available
                    update_command = shlex.split("sudo apt update -y")
                    install_ruby_command = shlex.split("sudo apt install ruby ruby-dev build-essential -y")
                    install_wpscan_command = shlex.split("sudo gem install wpscan")
                    q.put("Detected Linux. Using 'sudo apt' and 'sudo gem' for installation.\n")
                    commands_to_run = [update_command, install_ruby_command, install_wpscan_command]
                else:
                    q.put("Error: Unsupported platform type for installation.\n")
                    q.put("---INSTALL_COMPLETE_FAILURE---")
                    return

                for cmd in commands_to_run:
                    q.put(f"Executing: {' '.join(cmd)}\n")
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    for line in iter(process.stdout.readline, ''):
                        q.put(line)
                        temp_buffer_thread.append(line)
                    process.wait()
                    if process.returncode != 0:
                        q.put(f"Command failed with exit code {process.returncode}\n")
                        raise subprocess.CalledProcessError(process.returncode, cmd, "".join(temp_buffer_thread), "")
                
                # Signal success and store final output
                q.put("---INSTALL_COMPLETE_SUCCESS---")
                scan_outputs[current_scan_id] = "".join(temp_buffer_thread)

            except subprocess.CalledProcessError as e:
                error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}"
                q.put(error_output)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                scan_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_output
            except FileNotFoundError as e:
                error_msg = f"Error: Command not found ({e}). Ensure 'sudo'/'apt'/'pkg'/'gem' is installed and in PATH.\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                scan_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_msg
            except Exception as e:
                error_msg = f"An unexpected error occurred during installation: {str(e)}\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                scan_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_msg

        # Start the installation in a separate thread
        install_thread = threading.Thread(target=_install_thread, args=(output_queue, scan_id, platform_type))
        install_thread.daemon = True
        install_thread.start()

        return jsonify({
            'status': 'running',
            'scan_id': scan_id, # Return the unique ID for polling
            'message': f'WPScan installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'WPScan installation via this interface is only supported on Linux/Termux systems.',
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
    # Default port if no argument is provided (e.g., if run directly)
    port = 5000 # This will be overridden by the PHP dashboard

    # Check for a --port argument passed from the PHP dashboard
    if '--port' in sys.argv:
        try:
            # Get the index of '--port' and then the next argument (which is the port number)
            port_index = sys.argv.index('--port') + 1
            port = int(sys.argv[port_index])
        except (ValueError, IndexError):
            print("Warning: Invalid or missing port argument for sub-app. Using default port.")
    
    print(f"WPScan sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)
