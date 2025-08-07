# app.py
# This Flask application provides a web-based GUI for Aircrack-ng,
# and also includes functionality for managing XSS payload files.

# Import gevent and patch standard library for asynchronous I/O
# This helps resolve potential recursion or threading issues with Flask-SocketIO.
from gevent import monkey
monkey.patch_all()

import os
import sys
import subprocess
import threading
import queue
import shlex
import json
import time
import logging # Import logging for better error handling

from flask import Flask, request, jsonify, render_template, send_file
from flask_socketio import SocketIO, emit

# Configure logging for debugging
# Changed to DEBUG level to see more detailed messages
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Flask app
app = Flask(__name__)
# Configure SocketIO for WebSocket communication
# cors_allowed_origins="*" allows connections from any origin, which is useful for development.
# In production, you should restrict this to your specific frontend origin.
socketio = SocketIO(app, cors_allowed_origins="*")

# Queue to hold output from the Aircrack-ng process
output_queue = queue.Queue()
# Global variable to hold the Aircrack-ng subprocess
aircrack_process = None
# Flag to indicate if the process is running
is_process_running = False
# Path for saving logs temporarily
LOG_FILE_PATH = "aircrack_output.log"

# Directory for storing payload files
PAYLOAD_DIR = "database" # This will be your "database folder"

# Ensure the payload directory exists
if not os.path.exists(PAYLOAD_DIR):
    os.makedirs(PAYLOAD_DIR)
    logging.info(f"Created payload directory: {PAYLOAD_DIR}")

# --- Helper Functions ---

def _run_aircrack_thread(command_parts):
    """
    Runs the aircrack-ng command in a separate thread and streams its output
    to a queue.
    """
    global aircrack_process, is_process_running

    try:
        # Check if aircrack-ng is available in PATH
        import shutil
        if shutil.which(command_parts[0]) is None:
            error_message = f"Error: '{command_parts[0]}' not found in system PATH. Please ensure aircrack-ng is installed and accessible."
            output_queue.put(error_message + "\n")
            output_queue.put("STATUS: Error\n")
            socketio.emit('process_status', {'status': 'error', 'message': error_message})
            is_process_running = False
            return

        logging.info(f"Executing command: {' '.join(command_parts)}")
        # Start the subprocess
        aircrack_process = subprocess.Popen(
            command_parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line-buffered output
            universal_newlines=True
        )
        is_process_running = True
        output_queue.put("Aircrack-ng process started.\n")
        socketio.emit('process_status', {'status': 'running', 'message': 'Aircrack-ng is running...'})

        # Function to read output from a pipe and put it into the queue
        def read_pipe_to_queue(pipe, q):
            for line in iter(pipe.readline, ''):
                q.put(line)
            pipe.close()

        # Start threads to read stdout and stderr concurrently
        stdout_thread = threading.Thread(target=read_pipe_to_queue, args=(aircrack_process.stdout, output_queue))
        stderr_thread = threading.Thread(target=read_pipe_to_queue, args=(aircrack_process.stderr, output_queue))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        # Wait for the process to finish
        aircrack_process.wait()
        return_code = aircrack_process.returncode
        output_queue.put(f"\nAircrack-ng finished with exit code: {return_code}\n")
        final_status = 'Completed' if return_code == 0 else 'Failed'
        output_queue.put(f"STATUS: {final_status}\n")
        socketio.emit('process_status', {'status': final_status.lower(), 'message': f'Aircrack-ng {final_status}'})

    except FileNotFoundError:
        error_message = "Error: aircrack-ng command not found. Make sure aircrack-ng is installed and in your system's PATH."
        output_queue.put(error_message + "\n")
        output_queue.put("STATUS: Error\n")
        socketio.emit('process_status', {'status': 'error', 'message': error_message})
        logging.error(error_message)
    except Exception as e:
        error_message = f"An unexpected error occurred during Aircrack-ng execution: {e}"
        output_queue.put(error_message + "\n")
        output_queue.put("STATUS: Error\n")
        socketio.emit('process_status', {'status': 'error', 'message': error_message})
        logging.error(error_message, exc_info=True)
    finally:
        is_process_running = False
        aircrack_process = None # Clear the process reference

def stream_output_to_clients():
    """
    Continuously checks the output queue and emits new lines via SocketIO.
    """
    while True:
        try:
            line = output_queue.get(timeout=0.1) # Wait briefly for new output
            socketio.emit('stream_output', {'data': line})
        except queue.Empty:
            pass
        time.sleep(0.01) # Small delay to prevent busy-waiting

# Start the output streaming thread when the app starts
output_streaming_thread = threading.Thread(target=stream_output_to_clients)
output_streaming_thread.daemon = True
output_streaming_thread.start()

# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main HTML page for the Aircrack-ng GUI."""
    return render_template('index.html')

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """
    Generates an aircrack-ng command string based on the provided form data.
    """
    data = request.json
    command_parts = ["aircrack-ng"]

    # Helper to add arguments if value is not empty
    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value))) # Quote values to handle spaces

    # Helper to add checkbox arguments
    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Helper to add dropdown arguments
    def add_dropdown_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            # Extract only the number for attack mode if it's in "X (Description)" format
            if arg_name == "-a":
                mode_num = str(value).split(' ')[0]
                command_parts.append(mode_num)
            else:
                command_parts.append(shlex.quote(str(value)))

    # Input/Target Tab
    capture_files_str = data.get('capture_file_entry', '').strip()
    if not capture_files_str:
        return jsonify({'command': "Error: Input Capture File(s) are required.", 'status': 'error'}), 400

    add_arg("-b", data.get('bssid_entry'))
    add_arg("-e", data.get('essid_entry'))
    add_arg("-c", data.get('client_mac_entry')) # Added client MAC for target
    add_arg("-i", data.get('interface_entry')) # Added interface for live capture (though aircrack-ng usually uses cap files)

    # Attack Options Tab
    add_dropdown_arg("-a", data.get('attack_mode_var'))
    add_arg("-w", data.get('wordlist_entry'))
    add_arg("-p", data.get('single_password_entry'))
    add_arg("-E", data.get('passphrase_entry'))
    add_arg("-x", data.get('ptw_acks_entry'))
    add_checkbox_arg("-N", data.get('no_dictionary_var'))
    add_checkbox_arg("-P", data.get('no_ptw_var'))
    add_checkbox_arg("-J", data.get('pmkid_attack_var'))
    add_checkbox_arg("-M", data.get('no_pmkid_var'))
    add_arg("-K", data.get('key_index_entry')) # Added WEP key index
    add_arg("-d", data.get('delay_entry')) # Added delay for dictionary attack
    add_arg("-r", data.get('replay_file_entry')) # Added replay file

    # Filtering Tab
    add_arg("-b", data.get('filter_bssid_entry'))
    add_arg("-c", data.get('filter_client_mac_entry'))
    add_arg("-e", data.get('filter_essid_entry'))
    add_arg("-C", data.get('filter_channel_entry'))
    add_arg("-F", data.get('filter_fcs_entry')) # Added FCS filter
    add_checkbox_arg("-k", data.get('keep_ivs_var')) # Added keep IVs

    # Performance Tab
    add_arg("-t", data.get('threads_entry'))
    add_arg("-C", data.get('cpu_affinity_entry'))
    add_arg("-B", data.get('batch_size_entry'))
    add_checkbox_arg("--show-progress", data.get('show_progress_var'))
    add_arg("--gpu", data.get('gpu_device_entry')) # Added GPU device selection
    add_arg("--opencl", data.get('opencl_device_entry')) # Added OpenCL device selection

    # Output Tab
    add_arg("-o", data.get('output_file_entry'))
    add_checkbox_arg("-v", data.get('verbose_var'))
    add_checkbox_arg("-q", data.get('quiet_var'))
    add_checkbox_arg("--no-color", data.get('no_color_var'))
    add_arg("-L", data.get('log_file_entry')) # Added log file
    add_checkbox_arg("-s", data.get('show_summary_var')) # Added show summary
    add_checkbox_arg("-u", data.get('show_unencrypted_var')) # Added show unencrypted

    # Advanced Tab
    add_checkbox_arg("-D", data.get('debug_var'))
    add_arg("--help", data.get('show_help_var')) # Added help option
    add_arg("--version", data.get('show_version_var')) # Added version option
    add_arg("--ivs", data.get('ivs_file_entry')) # Added IVS file
    add_arg("--cap-file", data.get('cap_file_entry')) # Added CAP file (redundant with main input, but good for clarity)

    # Additional Arguments
    additional_args = data.get('additional_args_entry', '').strip()
    if additional_args:
        try:
            split_args = shlex.split(additional_args)
            command_parts.extend(split_args)
        except ValueError as e:
            # If shlex fails to parse, it's likely malformed input.
            # Return an error to the user instead of potentially creating a bad command.
            return jsonify({'command': f"Error parsing additional arguments: {e}", 'status': 'error'}), 400

    # Input Capture File(s) are always the last arguments
    files = shlex.split(capture_files_str)
    for f in files:
        command_parts.append(shlex.quote(f))

    generated_cmd = " ".join(command_parts)
    return jsonify({'command': generated_cmd, 'status': 'success'})

@app.route('/run_aircrack', methods=['POST'])
def run_aircrack():
    """
    Receives the command string from the frontend and executes it.
    """
    global aircrack_process, is_process_running

    if is_process_running:
        return jsonify({'status': 'warning', 'message': 'Aircrack-ng is already running.'}), 409

    data = request.json
    command_str = data.get('command', '').strip()

    if not command_str or command_str.startswith("Error:"):
        return jsonify({'status': 'error', 'message': 'Invalid or empty command to execute.'}), 400

    # Clear previous output
    with open(LOG_FILE_PATH, 'w') as f:
        f.write("")
    while not output_queue.empty():
        try:
            output_queue.get_nowait()
        except queue.Empty:
            break # Ensure we don't block if queue becomes empty between checks

    # Use shlex.split to correctly handle quoted arguments for subprocess
    try:
        command = shlex.split(command_str)
    except ValueError as e:
        return jsonify({'status': 'error', 'message': f'Error parsing command: {e}'}), 400

    # Run aircrack-ng in a separate thread
    threading.Thread(target=_run_aircrack_thread, args=(command,), daemon=True).start()

    return jsonify({'status': 'success', 'message': 'Aircrack-ng execution started.'})

@app.route('/save_output', methods=['POST'])
def save_output():
    """
    Saves the current content of the log box to a text file and provides it for download.
    """
    data = request.json
    output_content = data.get('content', '')

    if not output_content.strip():
        return jsonify({'status': 'info', 'message': 'No output to save.'}), 200

    try:
        # Save to a temporary file
        temp_file_path = "aircrack_output_download.txt"
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(output_content)

        # Send the file for download
        return send_file(temp_file_path, as_attachment=True, download_name="aircrack_output.txt", mimetype='text/plain')
    except Exception as e:
        logging.error(f"Failed to save output: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Failed to save output: {e}'}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    Endpoint for graceful shutdown of the Flask application.
    This is called by the PHP controller when stopping the app.
    """
    global aircrack_process, is_process_running

    # Terminate any running aircrack-ng process
    if aircrack_process and aircrack_process.poll() is None:
        try:
            aircrack_process.terminate()
            aircrack_process.wait(timeout=5) # Give it some time to terminate
            if aircrack_process.poll() is None:
                aircrack_process.kill() # Force kill if not terminated
            logging.info("Aircrack-ng process terminated during shutdown.")
        except Exception as e:
            app.logger.error(f"Error terminating aircrack-ng process during shutdown: {e}")
        finally:
            is_process_running = False
            aircrack_process = None

    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        # This means the app is not running with Werkzeug server (e.g., Gunicorn, uWSGI)
        # In a production environment, you'd handle shutdown differently.
        # For this context, we'll just log and return.
        logging.warning("Not running with the Werkzeug Server. Cannot perform graceful shutdown via func().")
        return jsonify({'status': 'warning', 'message': 'Server not running with Werkzeug, cannot gracefully shut down.'}), 200

    func()
    logging.info("Server shutting down...")
    return jsonify({'status': 'success', 'message': 'Server shutting down...'}), 200

# --- New File Management Routes for XSS Payloads ---

@app.route('/search_files', methods=['POST'])
def search_files():
    """
    Searches for .txt files in the PAYLOAD_DIR based on a search term.
    """
    data = request.json
    search_term = data.get('searchTerm', '').lower()
    found_files = []
    try:
        for filename in os.listdir(PAYLOAD_DIR):
            if filename.endswith('.txt') and search_term in filename.lower():
                found_files.append(filename)
        found_files.sort() # Sort alphabetically
        return jsonify(found_files)
    except Exception as e:
        logging.error(f"Error searching files in {PAYLOAD_DIR}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to search files: {e}'}), 500

@app.route('/load_file', methods=['POST'])
def load_file():
    """
    Loads the content of a specified file from the PAYLOAD_DIR.
    """
    data = request.json
    filename = data.get('filename')
    file_path = os.path.join(PAYLOAD_DIR, filename)

    logging.debug(f"Attempting to load file: {filename}")
    logging.debug(f"Constructed file path: {file_path}")
    logging.debug(f"Does file exist at path? {os.path.exists(file_path)}")
    logging.debug(f"Is path within PAYLOAD_DIR? {os.path.abspath(file_path).startswith(os.path.abspath(PAYLOAD_DIR))}")


    if not filename or not os.path.exists(file_path) or not os.path.abspath(file_path).startswith(os.path.abspath(PAYLOAD_DIR)):
        logging.warning(f"Attempted to load non-existent or invalid file: {filename} (Path: {file_path})")
        return jsonify({'error': 'File not found or invalid path.'}), 404

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logging.debug(f"Successfully loaded file: {filename}")
        return jsonify({'filename': filename, 'content': content})
    except Exception as e:
        logging.error(f"Error loading file {filename} from {file_path}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to load file: {e}'}), 500

@app.route('/save_payload', methods=['POST'])
def save_payload():
    """
    Saves content to a specified file in the PAYLOAD_DIR.
    """
    data = request.json
    filename = data.get('filename')
    content = data.get('content', '')

    if not filename:
        return jsonify({'message': 'Filename is required.', 'status': 'error'}), 400

    # Ensure filename ends with .txt
    if not filename.endswith('.txt'):
        filename += '.txt'

    file_path = os.path.join(PAYLOAD_DIR, filename)

    # Security check: Prevent path traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(PAYLOAD_DIR)):
        logging.warning(f"Attempted path traversal detected: {filename}")
        return jsonify({'message': 'Invalid filename or path.', 'status': 'error'}), 400

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"Payload saved to {file_path}")
        return jsonify({'message': f'Payload "{filename}" saved successfully!', 'status': 'success'})
    except Exception as e:
        logging.error(f"Error saving payload to {file_path}: {e}", exc_info=True)
        return jsonify({'message': f'Failed to save payload: {e}', 'status': 'error'}), 500

# --- SocketIO Event Handlers ---

@socketio.on('connect')
def handle_connect():
    """Handles new client connections."""
    logging.info('Client connected')
    # When a new client connects, send the current status of the aircrack process
    if is_process_running:
        emit('process_status', {'status': 'running', 'message': 'Aircrack-ng is running...'})
    else:
        emit('process_status', {'status': 'ready', 'message': 'Ready'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handles client disconnections."""
    logging.info('Client disconnected')

# --- Main execution ---

if __name__ == '__main__':
    # Get port from command line arguments if running directly (e.g., from PHP)
    port = 5000 # Default port
    if '--port' in sys.argv:
        try:
            port_index = sys.argv.index('--port') + 1
            port = int(sys.argv[port_index])
        except (ValueError, IndexError):
            logging.warning("Invalid port argument. Using default port 5000.")

    # Run the Flask app with SocketIO
    # use_reloader=False is important when running with subprocesses and threads
    # because the reloader can cause processes to be spawned multiple times.
    # allow_unsafe_werkzeug=True is needed for the shutdown function to work in development.
    try:
        logging.info(f"Starting Flask SocketIO server on port {port}...")
        socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        logging.critical(f"Failed to start Flask SocketIO server: {e}", exc_info=True)
        # You might want to add a mechanism to report this error back to the PHP script
        # or a more persistent log file if this is a common issue.
