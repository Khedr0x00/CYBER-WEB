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
file_outputs = {}
file_processes = {} # To keep track of running file processes
file_queues = {} # To store queues for real-time output

# Load examples from file_examples.txt
def load_examples(filename="file_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming file_examples.txt is in the same directory as app.py
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
    """Renders the main File Analyzer GUI HTML page."""
    return render_template('index.html')

# New endpoint to serve File examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the File examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the 'file' command based on form data."""
    data = request.json
    command_parts = ["file"]

    # Target File/Path
    target_entry = data.get('target_entry', '').strip()
    if not target_entry:
        return jsonify({'command': 'file'}), 200 # Return just 'file' if no target

    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value)))

    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Basic Options Tab
    add_checkbox_arg("-b", data.get('brief_mode_var'))
    add_checkbox_arg("-c", data.get('compile_magic_var'))
    add_checkbox_arg("-C", data.get('compile_magic_var_C')) # For -C, not -c
    add_checkbox_arg("-z", data.get('compressed_var'))
    add_checkbox_arg("-L", data.get('follow_symlinks_var'))
    add_checkbox_arg("-k", data.get('keep_going_var'))
    add_checkbox_arg("-i", data.get('mime_type_var'))
    add_checkbox_arg("-s", data.get('special_files_var'))
    add_checkbox_arg("-u", data.get('uncompile_magic_var'))
    add_checkbox_arg("-v", data.get('version_var'))
    add_checkbox_arg("-h", data.get('help_var'))

    # Advanced Options Tab
    add_arg("-F", data.get('separator_entry'))
    add_arg("-f", data.get('file_list_entry'))
    add_arg("-m", data.get('magic_file_entry'))
    add_checkbox_arg("-p", data.get('preserve_path_var'))
    add_checkbox_arg("--raw", data.get('raw_output_var'))
    add_checkbox_arg("--dereference", data.get('dereference_var'))
    add_checkbox_arg("--no-dereference", data.get('no_dereference_var'))
    add_checkbox_arg("--apple", data.get('apple_output_var'))
    add_checkbox_arg("--preserve-date", data.get('preserve_date_var'))
    add_checkbox_arg("--extension", data.get('extension_var'))
    add_checkbox_arg("--mime-type", data.get('mime_type_only_var'))
    add_checkbox_arg("--mime-encoding", data.get('mime_encoding_only_var'))

    # Exclude Tests
    exclude_tests = data.get('exclude_tests_entry', [])
    for test in exclude_tests:
        if test:
            command_parts.append("--exclude")
            command_parts.append(shlex.quote(test))

    # Add the target file/path at the end, unless it's a compile/uncompile command
    if not data.get('compile_magic_var_C') and not data.get('uncompile_magic_var') and target_entry:
        command_parts.append(shlex.quote(target_entry))
    elif (data.get('compile_magic_var_C') or data.get('uncompile_magic_var')) and not target_entry:
        # If compiling/uncompiling, target_entry is the magic file, it's already added with -m
        # If no magic file is specified, the command will be just 'file -C' or 'file -u'
        pass # No target file needed if -m is used or if no target for C/u

    generated_cmd = " ".join(command_parts)
    return jsonify({'command': generated_cmd})


@app.route('/run_file', methods=['POST'])
def run_file():
    """
    Executes the 'file' command received from the frontend.
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
    if any(cmd in command_str for cmd in ['rm ', 'sudo ', 'reboot', 'shutdown', 'init ', 'mv ', 'cp ', 'dd ']):
        return jsonify({'status': 'error', 'message': 'Potentially dangerous command detected. Operation aborted.'}), 403

    # Use shlex.split to safely split the command string into a list
    try:
        command = shlex.split(command_str)
    except ValueError as e:
        return jsonify({'status': 'error', 'message': f'Error parsing command: {e}'}), 400

    # Ensure 'file' is the command being run
    if command[0] != 'file':
        return jsonify({'status': 'error', 'message': 'Only "file" commands are allowed.'}), 403

    # Check if 'file' executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"'{command[0]}' executable not found on the server. Please ensure 'file' is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this execution's real-time output
    output_queue = queue.Queue()
    file_queues[scan_id] = output_queue
    file_outputs[scan_id] = "" # Initialize full output storage

    def _run_file_thread(cmd, q, scan_id_val):
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
            file_processes[scan_id_val] = process

            for line in iter(process.stdout.readline, ''):
                q.put(line) # Put each line into the queue
                full_output_buffer.append(line) # Also append to buffer for final output

            process.wait()
            return_code = process.returncode

            final_status_line = f"\nCommand finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            file_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure 'file' is installed and in your system's PATH.\nSTATUS: Error\n"
            q.put(error_msg)
            file_outputs[scan_id_val] = error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}\nSTATUS: Error\n"
            q.put(error_msg)
            file_outputs[scan_id_val] = error_msg
        finally:
            if scan_id_val in file_processes:
                del file_processes[scan_id_val]
            # Signal end of output by putting a special marker
            q.put("---COMMAND_COMPLETE---")


    # Start the 'file' process in a separate thread
    thread = threading.Thread(target=_run_file_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'File analysis started.'})

@app.route('/get_scan_output/<scan_id>', methods=['GET'])
def get_scan_output(scan_id):
    """
    Polls for real-time 'file' command output.
    Returns new lines from the queue or the final output if command is complete.
    """
    output_queue = file_queues.get(scan_id)
    if not output_queue:
        # If queue is not found, check if the command completed and its final output is stored
        final_output = file_outputs.get(scan_id)
        if final_output: # If it's a regular command that completed
            return jsonify({'status': 'completed', 'output': final_output})
        return jsonify({'status': 'not_found', 'message': 'Command ID not found or expired.'}), 404

    new_output_lines = []
    command_finished = False
    install_success = False
    install_failure = False

    try:
        while True:
            # Get items from queue without blocking
            line = output_queue.get_nowait()
            if line == "---COMMAND_COMPLETE---":
                command_finished = True
                break
            elif line == "---INSTALL_COMPLETE_SUCCESS---":
                install_success = True
                command_finished = True # Treat installation completion as a command completion for frontend
                break
            elif line == "---INSTALL_COMPLETE_FAILURE---":
                install_failure = True
                command_finished = True # Treat installation completion as a command completion for frontend
                break
            new_output_lines.append(line)
    except queue.Empty:
        pass # No more lines in queue for now

    current_output_segment = "".join(new_output_lines)

    if command_finished:
        # Command or installation is truly complete, clean up the queue
        del file_queues[scan_id]
        status_to_return = 'completed'
        if install_success:
            status_to_return = 'success'
        elif install_failure:
            status_to_return = 'error'
        
        # Ensure the final output includes all accumulated output
        final_output_content = file_outputs.get(scan_id, "Command/Installation completed, but output not fully captured.")
        return jsonify({'status': status_to_return, 'output': final_output_content})
    else:
        # Command/Installation is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})


@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the provided content to a file on the server and allows download."""
    data = request.json
    content = data.get('content')
    filename = data.get('filename', f'file_output_{uuid.uuid4()}.txt')

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

@app.route('/install_file', methods=['POST'])
def install_file():
    """
    Attempts to install 'file' utility on the server (Linux/Termux only).
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
        file_queues[scan_id] = output_queue
        file_outputs[scan_id] = "" # Initialize full output storage for this ID

        def _install_thread(q, current_scan_id, p_type):
            temp_buffer_thread = [] # Local buffer for the thread
            try:
                if p_type == 'termux':
                    update_command = shlex.split("pkg update -y")
                    install_command = shlex.split("pkg install file -y")
                    q.put("Detected Termux. Using 'pkg' for installation.\n")
                elif p_type == 'linux':
                    update_command = shlex.split("sudo apt update -y")
                    install_command = shlex.split("sudo apt install file -y")
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

                # Then, install file
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
                file_outputs[current_scan_id] = "".join(temp_buffer_thread)

            except subprocess.CalledProcessError as e:
                error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}"
                q.put(error_output)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                file_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_output
            except FileNotFoundError as e:
                error_msg = f"Error: Command not found ({e}). Ensure 'sudo'/'apt'/'pkg' is installed and in PATH.\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                file_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_msg
            except Exception as e:
                error_msg = f"An unexpected error occurred during installation: {str(e)}\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                file_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_msg

        # Start the installation in a separate thread
        install_thread = threading.Thread(target=_install_thread, args=(output_queue, scan_id, platform_type))
        install_thread.daemon = True
        install_thread.start()

        return jsonify({
            'status': 'running',
            'scan_id': scan_id, # Return the unique ID for polling
            'message': f'File utility installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'File utility installation via this interface is only supported on Linux/Termux systems.',
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
    
    print(f"File Analyzer sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)
