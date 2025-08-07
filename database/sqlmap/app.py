import os
import subprocess
import shlex
import json
from flask import Flask, request, jsonify, send_file, render_template
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
scan_processes = {} # To keep track of running sqlmap processes
scan_queues = {} # To store queues for real-time output

# Load examples from sqlmap_examples.txt
def load_examples(filename="sqlmap_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming sqlmap_examples.txt is in the same directory as app.py
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
    """Renders the main sqlmap GUI HTML page."""
    return render_template('index.html')

# New endpoint to serve sqlmap examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the sqlmap examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the sqlmap command based on form data."""
    data = request.json
    command_parts = ["sqlmap"]

    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value)))

    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Target Options
    add_arg("-u", data.get('target_url_entry'))
    add_arg("-r", data.get('request_file_entry'))
    add_arg("--data", data.get('data_entry'))
    add_arg("--cookie", data.get('cookie_entry'))
    add_arg("--headers", data.get('headers_entry'))
    add_arg("--user-agent", data.get('user_agent_entry'))
    add_arg("--referer", data.get('referer_entry'))
    add_arg("--auth", data.get('auth_entry'))
    add_arg("--proxy", data.get('proxy_entry'))
    add_checkbox_arg("--tor", data.get('tor_var'))
    add_arg("--tor-type", data.get('tor_type_entry'))
    add_arg("--tor-port", data.get('tor_port_entry'))
    add_checkbox_arg("--random-agent", data.get('random_agent_var'))
    add_checkbox_arg("--batch", data.get('batch_var'))
    add_checkbox_arg("--force-ssl", data.get('force_ssl_var'))
    add_arg("--sitemap", data.get('sitemap_url_entry'))
    add_arg("--google-dork", data.get('google_dork_entry'))
    add_arg("--forms", data.get('forms_var'))
    add_arg("--crawl", data.get('crawl_entry'))

    # Injection Options
    add_arg("-p", data.get('parameter_entry'))
    add_arg("--techniques", data.get('techniques_entry'))
    add_arg("--dbms", data.get('dbms_entry'))
    add_arg("--prefix", data.get('prefix_entry'))
    add_arg("--suffix", data.get('suffix_entry'))
    add_arg("--tamper", data.get('tamper_scripts_entry'))

    # Detection Options
    add_arg("--level", data.get('level_entry'))
    add_arg("--risk", data.get('risk_entry'))
    add_checkbox_arg("-f", data.get('fingerprint_var'))

    # Enumeration Options
    add_checkbox_arg("--current-user", data.get('current_user_var'))
    add_checkbox_arg("--current-db", data.get('current_db_var'))
    add_checkbox_arg("--users", data.get('users_var'))
    add_checkbox_arg("--dbs", data.get('dbs_var'))
    add_arg("-D", data.get('db_name_entry'))
    add_checkbox_arg("--tables", data.get('tables_var'))
    add_arg("-T", data.get('table_name_entry'))
    add_checkbox_arg("--columns", data.get('columns_var'))
    add_arg("-C", data.get('column_name_entry'))
    add_checkbox_arg("--dump", data.get('dump_var'))
    add_checkbox_arg("--dump-all", data.get('dump_all_var'))
    add_checkbox_arg("--schema", data.get('schema_var'))
    add_checkbox_arg("--passwords", data.get('passwords_var'))
    add_checkbox_arg("--privileges", data.get('privileges_var'))
    add_checkbox_arg("--roles", data.get('roles_var'))
    add_checkbox_arg("--db-config", data.get('db_config_var'))
    add_checkbox_arg("--db-system", data.get('db_system_var'))
    add_checkbox_arg("--all", data.get('all_enum_var'))

    # Access Options
    add_checkbox_arg("--os-shell", data.get('os_shell_var'))
    add_checkbox_arg("--os-pwn", data.get('os_pwn_var'))
    add_arg("--file-read", data.get('file_read_entry'))
    add_arg("--file-write", data.get('file_write_entry'))
    add_arg("--file-dest", data.get('file_dest_entry'))
    add_arg("--file-upload", data.get('file_upload_entry'))

    # Optimization Options
    add_arg("--threads", data.get('threads_entry'))
    add_arg("--delay", data.get('delay_entry'))
    add_arg("--timeout", data.get('timeout_entry'))
    add_arg("--retries", data.get('retries_entry'))
    add_checkbox_arg("--traffic-dump", data.get('traffic_dump_var'))

    # WAF Bypass Options
    add_checkbox_arg("--identify-waf", data.get('identify_waf_var'))
    add_checkbox_arg("--skip-waf", data.get('skip_waf_var'))

    # General/Miscellaneous Options
    add_arg("-v", data.get('verbose_entry'))
    add_arg("-o", data.get('output_dir_entry'))
    add_checkbox_arg("--flush-session", data.get('flush_session_var'))
    add_checkbox_arg("--save", data.get('save_var'))
    add_checkbox_arg("--beep", data.get('beep_var'))
    add_checkbox_arg("--disable-coloring", data.get('disable_coloring_var'))
    add_checkbox_arg("--no-banner", data.get('no_banner_var'))
    add_arg("--dns-server", data.get('dns_server_entry'))

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

@app.route('/run_sqlmap', methods=['POST'])
def run_sqlmap():
    """
    Executes the sqlmap command received from the frontend.
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

    # Ensure sqlmap is the command being run
    if command[0] != 'sqlmap':
        return jsonify({'status': 'error', 'message': 'Only sqlmap commands are allowed.'}), 403

    # Check if sqlmap executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"sqlmap executable '{command[0]}' not found on the server. Please ensure sqlmap is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this scan's real-time output
    output_queue = queue.Queue()
    scan_queues[scan_id] = output_queue
    scan_outputs[scan_id] = "" # Initialize full output storage

    def _run_sqlmap_thread(cmd, q, scan_id_val):
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

            final_status_line = f"\nsqlmap finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            scan_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure sqlmap is installed and in your system's PATH.\nSTATUS: Error\n"
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


    # Start the sqlmap process in a separate thread
    thread = threading.Thread(target=_run_sqlmap_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'sqlmap scan started.'})

@app.route('/get_scan_output/<scan_id>', methods=['GET'])
def get_scan_output(scan_id):
    """
    Polls for real-time sqlmap scan output.
    Returns new lines from the queue or the final output if scan is complete.
    """
    output_queue = scan_queues.get(scan_id)
    if not output_queue:
        # If queue is not found, check if the scan completed and its final output is stored
        if scan_id in scan_outputs:
            return jsonify({'status': 'completed', 'output': scan_outputs[scan_id]})
        return jsonify({'status': 'not_found', 'message': 'Scan ID not found or expired.'}), 404

    new_output_lines = []
    scan_finished = False
    try:
        while True:
            # Get items from queue without blocking
            line = output_queue.get_nowait()
            if line == "---SCAN_COMPLETE---":
                scan_finished = True
                break
            new_output_lines.append(line)
    except queue.Empty:
        pass # No more lines in queue for now

    current_output_segment = "".join(new_output_lines)

    if scan_finished:
        # Scan is truly complete, clean up the queue
        del scan_queues[scan_id]
        return jsonify({'status': 'completed', 'output': scan_outputs.get(scan_id, "Scan completed, but output not fully captured.")})
    else:
        # Scan is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})


@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the provided content to a file on the server and allows download."""
    data = request.json
    content = data.get('content')
    filename = data.get('filename', f'sqlmap_output_{uuid.uuid4()}.txt')

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

@app.route('/install_sqlmap', methods=['POST'])
def install_sqlmap():
    """
    Provides instructions for installing sqlmap.
    sqlmap is typically installed via pip or by cloning its GitHub repository.
    Direct automatic installation via apt/yum is less common or requires specific repos.
    """
    platform = sys.platform
    message = ""
    output = ""

    if platform.startswith('linux'):
        message = """
        sqlmap is not typically installed via a simple 'apt install' like Nmap.
        <br><br>
        You can install it using pip (Python package installer):
        <br><code>pip install sqlmap</code>
        <br><br>
        Or, for the latest version, clone it from GitHub:
        <br><code>git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git sqlmap-dev</code>
        <br>Then navigate into the directory: <code>cd sqlmap-dev</code>
        <br>And run it using: <code>python sqlmap.py -h</code>
        <br><br>
        Please ensure you have Python and pip/git installed.
        """
        output = "Please refer to the instructions for manual installation on Linux."
    elif platform.startswith('win'):
        message = """
        sqlmap is a Python application.
        <br><br>
        Please ensure you have Python installed on Windows.
        <br><br>
        You can download sqlmap from its official GitHub repository:
        <br><a href=\"https://github.com/sqlmapproject/sqlmap/releases\" target=\"_blank\" class=\"text-blue-400 hover:underline\">Download sqlmap for Windows</a>
        <br><br>
        Extract the zip file and run sqlmap from the command prompt using:
        <br><code>python sqlmap.py -h</code> (from within the sqlmap directory)
        """
        output = "Please refer to the instructions for manual installation on Windows."
    else:
        message = f"sqlmap installation is not automatically supported for your operating system ({platform}). Please install sqlmap manually."
        output = "Operating system not recognized for automatic installation instructions."

    return jsonify({
        'status': 'info',
        'message': message,
        'output': output,
        'isHtml': True # Indicate that the message is HTML
    }), 200

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
    
    print(f"sqlmap sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)
