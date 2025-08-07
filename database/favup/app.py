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

# In-memory storage for scan outputs.
scan_outputs = {}
scan_processes = {} # To keep track of running fav-up processes
scan_queues = {} # To store queues for real-time output

# Load examples from favup_examples.txt
def load_examples(filename="favup_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming favup_examples.txt is in the same directory as favup_app.py
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Examples file '{filename}' not found. Please ensure it's in the same directory as favup_app.py.")
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
    """Renders the main Fav-Up GUI HTML page."""
    return render_template('favup_index.html')

# New endpoint to serve Fav-Up examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the Fav-Up examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the favUp.py command based on form data."""
    data = request.json
    command_parts = ["python3", "favUp.py"] # Assuming favUp.py is in the same directory or accessible via PATH

    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value)))

    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Main Options Tab
    add_arg("-u", data.get('target_url_entry'))
    add_arg("-w", data.get('wordlist_file_entry'))
    add_arg("-o", data.get('output_file_entry'))
    add_checkbox_arg("-s", data.get('silent_mode_var'))
    add_checkbox_arg("-p", data.get('print_valid_var'))
    add_checkbox_arg("-v", data.get('verbose_var'))

    # Advanced Options Tab
    add_arg("-c", data.get('cookies_entry'))
    
    headers = data.get('headers_entry', '').strip()
    if headers:
        # Split headers by newline and add each as a separate -H argument
        for header_line in headers.split('\n'):
            header_line = header_line.strip()
            if header_line:
                command_parts.append("-H")
                command_parts.append(shlex.quote(header_line))

    add_arg("--proxy", data.get('proxy_url_entry'))
    add_arg("--timeout", data.get('timeout_entry'))
    add_arg("--retries", data.get('retries_entry'))
    add_arg("--threads", data.get('threads_entry'))
    add_arg("--user-agent", data.get('user_agent_entry'))

    generated_cmd = " ".join(command_parts)
    return jsonify({'command': generated_cmd})

@app.route('/run_favup', methods=['POST'])
def run_favup():
    """
    Executes the favUp.py command received from the frontend.
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

    # Ensure favUp.py is the script being run
    if len(command) < 2 or command[0] != 'python3' or not command[1].endswith('favUp.py'):
        return jsonify({'status': 'error', 'message': 'Only favUp.py commands are allowed.'}), 403

    # Check if python3 executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"Python3 executable '{command[0]}' not found on the server. Please ensure Python3 is installed and accessible in the system's PATH."}), 500
    
    # Check if favUp.py script exists
    favup_script_path = command[1]
    if not os.path.exists(favup_script_path):
        return jsonify({'status': 'error', 'message': f"favUp.py script not found at '{favup_script_path}'. Please ensure it is in the correct directory or provide a full path."}), 500


    # Create a new queue for this scan's real-time output
    output_queue = queue.Queue()
    scan_queues[scan_id] = output_queue
    scan_outputs[scan_id] = "" # Initialize full output storage

    def _run_favup_thread(cmd, q, scan_id_val):
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

            final_status_line = f"\nFav-Up finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            scan_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure Python3 is installed and in your system's PATH.\nSTATUS: Error\n"
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


    # Start the Fav-Up process in a separate thread
    thread = threading.Thread(target=_run_favup_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'Fav-Up scan started.'})

@app.route('/get_scan_output/<scan_id>', methods=['GET'])
def get_scan_output(scan_id):
    """
    Polls for real-time Fav-Up scan output.
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
    filename = data.get('filename', f'favup_output_{uuid.uuid4()}.txt')

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

@app.route('/install_favup', methods=['POST'])
def install_favup():
    """
    Provides installation instructions for fav-up based on the platform.
    This function does NOT execute installation commands directly for security reasons,
    but provides the necessary steps to the user.
    """
    data = request.json
    platform_type = data.get('platform') # 'linux', 'termux', or 'windows'

    install_info = {
        'status': 'info',
        'message': '',
        'output': ''
    }

    if platform_type == 'linux' or platform_type == 'termux':
        os_name = "Termux" if platform_type == 'termux' else "Linux"
        install_info['message'] = f"To install Fav-Up on {os_name}, please follow these steps in your terminal:"
        install_info['output'] = f"""
1. Ensure Git and Python3 are installed:
   - For Linux (Debian/Ubuntu): sudo apt update && sudo apt install git python3 python3-pip
   - For Termux: pkg update && pkg install git python python-pip

2. Clone the Fav-Up repository:
   git clone https://github.com/pielco11/fav-up.git

3. Navigate into the Fav-Up directory:
   cd fav-up

4. Install required Python packages:
   pip3 install -r requirements.txt

5. You can then run Fav-Up using:
   python3 favUp.py -h
"""
    elif platform_type == 'windows':
        install_info['message'] = "To install Fav-Up on Windows, please follow these steps:"
        install_info['output'] = """
1. Ensure Python3 is installed on your system. You can download it from:
   https://www.python.org/downloads/

2. Ensure Git is installed. You can download it from:
   https://git-scm.com/downloads

3. Open your command prompt (CMD) or PowerShell.

4. Clone the Fav-Up repository:
   git clone https://github.com/pielco11/fav-up.git

5. Navigate into the Fav-Up directory:
   cd fav-up

6. Install required Python packages:
   pip install -r requirements.txt

7. You can then run Fav-Up using:
   python favUp.py -h
"""
    else:
        install_info['status'] = 'error'
        install_info['message'] = f"Fav-Up installation information is not available for your operating system ({sys.platform})."
        install_info['output'] = "Please refer to the official Fav-Up GitHub repository for manual installation instructions: https://github.com/pielco11/fav-up"

    return jsonify(install_info)

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
    
    print(f"Fav-Up sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)
