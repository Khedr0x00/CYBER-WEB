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
scan_outputs = {}
scan_processes = {} # To keep track of running Gospider processes
scan_queues = {} # To store queues for real-time output

# Load examples from gospider_examples.txt
def load_examples(filename="gospider_examples.txt"):
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

ALL_EXAMPLES = load_examples()

@app.route('/')
def index():
    """Renders the main Gospider GUI HTML page."""
    return render_template('index.html')

# New endpoint to serve Gospider examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the Gospider examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the Gospider command based on form data."""
    data = request.json
    command_parts = ["gospider"]

    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value)))

    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Target & Basic Options
    if data.get('target_url_entry'):
        command_parts.append(shlex.quote(data['target_url_entry']))
    
    add_arg("-c", data.get('concurrency_entry'))
    add_arg("-d", data.get('depth_entry'))
    add_arg("-t", data.get('delay_entry'))
    add_arg("-U", data.get('user_agent_entry'))
    add_arg("-H", data.get('headers_entry'))
    add_arg("-C", data.get('cookie_entry'))
    add_arg("-p", data.get('proxy_entry'))
    add_arg("-b", data.get('blacklist_entry'))
    add_arg("-w", data.get('whitelist_entry'))
    add_checkbox_arg("--subs", data.get('subdomains_var'))
    add_arg("-x", data.get('include_extensions_entry'))
    add_arg("-X", data.get('exclude_extensions_entry'))
    add_checkbox_arg("-v", data.get('verbose_var'))
    add_checkbox_arg("--sitemap", data.get('sitemap_var'))
    add_checkbox_arg("--robots", data.get('robots_var'))
    add_checkbox_arg("--json", data.get('json_output_var'))
    add_checkbox_arg("--no-redirect", data.get('no_redirect_var'))
    add_checkbox_arg("--include-unreachable", data.get('include_unreachable_var'))
    add_checkbox_arg("--debug", data.get('debug_var'))
    add_arg("--user-agent-file", data.get('user_agent_file_entry'))
    add_arg("--threads", data.get('threads_entry')) # Alias for -c
    add_arg("--timeout", data.get('timeout_entry'))
    add_arg("--output", data.get('output_file_entry'))
    add_checkbox_arg("--no-plus", data.get('no_plus_var'))
    add_checkbox_arg("--no-crawl", data.get('no_crawl_var'))
    add_checkbox_arg("--no-sitemap-crawl", data.get('no_sitemap_crawl_var'))
    add_checkbox_arg("--no-robots-crawl", data.get('no_robots_crawl_var'))
    add_checkbox_arg("--burp", data.get('burp_output_var'))
    add_checkbox_arg("--cookie-file", data.get('cookie_file_var'))
    add_arg("--random-agent", data.get('random_agent_var'))
    add_arg("--proxy-file", data.get('proxy_file_entry'))

    # Advanced Options
    add_arg("--blacklist-file", data.get('blacklist_file_entry'))
    add_arg("--whitelist-file", data.get('whitelist_file_entry'))
    add_arg("--endpoint-file", data.get('endpoint_file_entry'))
    add_arg("--url-file", data.get('url_file_entry'))
    add_arg("--header-file", data.get('header_file_entry'))
    add_arg("--module", data.get('module_entry'))
    add_arg("--module-args", data.get('module_args_entry'))
    add_checkbox_arg("--include-pattern", data.get('include_pattern_var'))
    add_checkbox_arg("--exclude-pattern", data.get('exclude_pattern_var'))
    add_arg("--match-regex", data.get('match_regex_entry'))
    add_arg("--exclude-regex", data.get('exclude_regex_entry'))
    add_checkbox_arg("--raw", data.get('raw_output_var'))
    add_checkbox_arg("--no-color", data.get('no_color_var'))
    add_checkbox_arg("--follow-redirects", data.get('follow_redirects_var'))
    add_arg("--max-redirects", data.get('max_redirects_entry'))
    add_arg("--rate-limit", data.get('rate_limit_entry'))
    add_arg("--delay-between-requests", data.get('delay_between_requests_entry'))
    add_arg("--random-delay", data.get('random_delay_entry'))
    add_arg("--force-ssl", data.get('force_ssl_var'))
    add_arg("--skip-ssl-verify", data.get('skip_ssl_verify_var'))
    add_arg("--cookie-string", data.get('cookie_string_entry'))
    add_arg("--data", data.get('post_data_entry'))
    add_arg("--method", data.get('http_method_entry'))
    add_arg("--userpass", data.get('userpass_entry'))
    add_arg("--auth-header", data.get('auth_header_entry'))
    add_arg("--header-string", data.get('header_string_entry'))
    add_arg("--body-file", data.get('body_file_entry'))
    add_arg("--form-file", data.get('form_file_entry'))
    add_arg("--form-data", data.get('form_data_entry'))
    add_arg("--data-urlencode", data.get('data_urlencode_entry'))
    add_arg("--data-binary", data.get('data_binary_entry'))
    add_arg("--data-raw", data.get('data_raw_entry'))
    add_arg("--data-urlencode-file", data.get('data_urlencode_file_entry'))
    add_arg("--data-binary-file", data.get('data_binary_file_entry'))
    add_arg("--data-raw-file", data.get('data_raw_file_entry'))
    add_arg("--content-type", data.get('content_type_entry'))
    add_arg("--user-agent-random", data.get('user_agent_random_var'))

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

@app.route('/run_gospider', methods=['POST'])
def run_gospider():
    """
    Executes the Gospider command received from the frontend.
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

    # Ensure gospider is the command being run
    if command[0] != 'gospider':
        return jsonify({'status': 'error', 'message': 'Only Gospider commands are allowed.'}), 403

    # Check if gospider executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"Gospider executable '{command[0]}' not found on the server. Please ensure Gospider is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this scan's real-time output
    output_queue = queue.Queue()
    scan_queues[scan_id] = output_queue
    scan_outputs[scan_id] = "" # Initialize full output storage

    def _run_gospider_thread(cmd, q, scan_id_val):
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

            final_status_line = f"\nGospider finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            scan_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure Gospider is installed and in your system's PATH.\nSTATUS: Error\n"
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


    # Start the Gospider process in a separate thread
    thread = threading.Thread(target=_run_gospider_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'Gospider scan started.'})

# Modified get_scan_output to handle 'gospider_install' ID
@app.route('/get_scan_output/<scan_id>', methods=['GET'])
def get_scan_output(scan_id):
    """
    Polls for real-time Gospider scan output.
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
    filename = data.get('filename', f'gospider_output_{uuid.uuid4()}.txt')

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

@app.route('/install_gospider', methods=['POST'])
def install_gospider():
    """
    Attempts to install Gospider on the server (Linux/Termux only).
    Requires Go to be installed.
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
                # Check for Go installation first
                if shutil.which("go") is None:
                    q.put("Go programming language not found. Gospider requires Go to be installed.\n")
                    q.put("Please install Go first (e.g., 'sudo apt install golang' on Debian/Ubuntu, or 'pkg install golang' on Termux).\n")
                    q.put("---INSTALL_COMPLETE_FAILURE---")
                    scan_outputs[current_scan_id] = "".join(temp_buffer_thread) + "Go not found."
                    return

                install_command = shlex.split("go install github.com/jaeles-project/gospider@latest")
                q.put(f"Executing: {' '.join(install_command)}\n")
                
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
                    q.put(f"Gospider installation command failed with exit code {install_process.returncode}\n")
                    raise subprocess.CalledProcessError(install_process.returncode, install_command, "".join(temp_buffer_thread), "")
                
                # Signal success and store final output
                q.put("---INSTALL_COMPLETE_SUCCESS---")
                scan_outputs[current_scan_id] = "".join(temp_buffer_thread)

            except subprocess.CalledProcessError as e:
                error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}"
                q.put(error_output)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                scan_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_output
            except FileNotFoundError as e:
                error_msg = f"Error: Command not found ({e}). Ensure 'go' is installed and in PATH.\n"
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
            'message': f'Gospider installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Gospider installation via this interface is only supported on Linux/Termux systems.',
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
    shutdown_server()
    return 'Server shutting down...', 200

if __name__ == '__main__':
    port = 5000 # Default port
    if '--port' in sys.argv:
        try:
            port_index = sys.argv.index('--port') + 1
            port = int(sys.argv[port_index])
        except (ValueError, IndexError):
            print("Warning: Invalid or missing port argument for sub-app. Using default port.")
    
    print(f"Gospider sub-app is starting on port {port}...")
    app.run(debug=True, host='0.0.0.0', port=port)

