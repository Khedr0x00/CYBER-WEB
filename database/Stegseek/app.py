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

# Directory to store temporary files (e.g., uploaded images, wordlists, scan outputs)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# In-memory storage for tool outputs and processes
tool_outputs = {}
tool_processes = {} # To keep track of running Stegseek processes
tool_queues = {} # To store queues for real-time output

# Load examples from stegseek_examples.txt
def load_examples(filename="stegseek_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming stegseek_examples.txt is in the same directory as app.py
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
    """Renders the main Stegseek GUI HTML page."""
    return render_template('index.html')

# Endpoint to serve Stegseek examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the Stegseek examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/upload_file', methods=['POST'])
def upload_file():
    """Handles file uploads (image or wordlist)."""
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400

    if file:
        filename = os.path.join(UPLOAD_FOLDER, file.filename)
        try:
            file.save(filename)
            return jsonify({'status': 'success', 'message': 'File uploaded successfully', 'filename': file.filename}), 200
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Failed to upload file: {e}'}), 500
    return jsonify({'status': 'error', 'message': 'Unknown error during upload'}), 500


@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the Stegseek command based on form data."""
    data = request.json
    command_parts = ["stegseek"]

    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            # For file paths, we assume they are in the UPLOAD_FOLDER
            if arg_name in ['-w', '-f', '-p']: # -w for wordlist, -f for image, -p for password file (if implemented)
                # Ensure the path is correct for the backend execution
                if value and not value.startswith(UPLOAD_FOLDER):
                    command_parts.append(shlex.quote(os.path.join(UPLOAD_FOLDER, value)))
                else:
                    command_parts.append(shlex.quote(str(value)))
            else:
                command_parts.append(shlex.quote(str(value)))

    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Main Options
    if data.get('image_file_entry'):
        # Image file is the primary argument, usually not prefixed with -f or --file
        # But stegseek also accepts -f for file. Let's use the direct argument.
        # If the user uploads, the filename will be stored in UPLOAD_FOLDER
        image_path = data['image_file_entry']
        if image_path and not image_path.startswith(UPLOAD_FOLDER):
            command_parts.append(shlex.quote(os.path.join(UPLOAD_FOLDER, image_path)))
        else:
            command_parts.append(shlex.quote(image_path))

    add_checkbox_arg("-x", data.get('extract_var'))
    add_arg("-p", data.get('password_entry'))
    add_arg("-w", data.get('wordlist_file_entry'))
    add_arg("-o", data.get('output_file_entry'))
    add_checkbox_arg("-c", data.get('check_var'))
    add_checkbox_arg("-v", data.get('verbose_var'))
    add_checkbox_arg("--stdout", data.get('stdout_var'))
    add_checkbox_arg("--no-output-file", data.get('no_output_file_var'))
    add_checkbox_arg("--force", data.get('force_overwrite_var'))
    add_checkbox_arg("--keep-password", data.get('keep_password_var'))
    add_checkbox_arg("--no-progress", data.get('no_progress_var'))
    add_arg("--cpu-cores", data.get('cpu_cores_entry'))
    add_arg("--threads", data.get('threads_entry')) # Alias for --cpu-cores
    add_checkbox_arg("--show-password", data.get('show_password_var'))
    add_arg("--algorithm", data.get('algorithm_entry'))
    add_arg("--offset", data.get('offset_entry'))
    add_arg("--length", data.get('length_entry'))
    add_arg("--jpeg-quality", data.get('jpeg_quality_entry'))
    add_checkbox_arg("--debug", data.get('debug_var'))
    add_checkbox_arg("--quiet", data.get('quiet_var'))
    add_checkbox_arg("--version", data.get('version_var'))
    add_checkbox_arg("--help", data.get('help_var'))

    # Additional Arguments
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

@app.route('/run_stegseek', methods=['POST'])
def run_stegseek():
    """
    Executes the Stegseek command received from the frontend.
    IMPORTANT: Running arbitrary commands from user input on a web server is a severe security risk.
    This implementation is for demonstration and should NOT be used in a production environment
    without extensive security measures, input validation, and sandboxing.
    """
    data = request.json
    command_str = data.get('command')
    scan_id = str(uuid.uuid4()) # Unique ID for this operation

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

    # Ensure stegseek is the command being run
    if command[0] != 'stegseek':
        return jsonify({'status': 'error', 'message': 'Only Stegseek commands are allowed.'}), 403

    # Check if stegseek executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"Stegseek executable '{command[0]}' not found on the server. Please ensure Stegseek is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this operation's real-time output
    output_queue = queue.Queue()
    tool_queues[scan_id] = output_queue
    tool_outputs[scan_id] = "" # Initialize full output storage

    def _run_stegseek_thread(cmd, q, scan_id_val):
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
            tool_processes[scan_id_val] = process

            for line in iter(process.stdout.readline, ''):
                q.put(line) # Put each line into the queue
                full_output_buffer.append(line) # Also append to buffer for final output

            process.wait()
            return_code = process.returncode

            final_status_line = f"\nStegseek finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            tool_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure Stegseek is installed and in your system's PATH.\nSTATUS: Error\n"
            q.put(error_msg)
            tool_outputs[scan_id_val] = error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}\nSTATUS: Error\n"
            q.put(error_msg)
            tool_outputs[scan_id_val] = error_msg
        finally:
            if scan_id_val in tool_processes:
                del tool_processes[scan_id_val]
            # Signal end of output by putting a special marker
            q.put("---TOOL_COMPLETE---")


    # Start the Stegseek process in a separate thread
    thread = threading.Thread(target=_run_stegseek_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'Stegseek operation started.'})

@app.route('/get_tool_output/<scan_id>', methods=['GET'])
def get_tool_output(scan_id):
    """
    Polls for real-time Stegseek output.
    Returns new lines from the queue or the final output if operation is complete.
    """
    output_queue = tool_queues.get(scan_id)
    if not output_queue:
        # If queue is not found, check if the operation completed and its final output is stored
        final_output = tool_outputs.get(scan_id)
        if final_output:
            return jsonify({'status': 'completed', 'output': final_output})
        return jsonify({'status': 'not_found', 'message': 'Operation ID not found or expired.'}), 404

    new_output_lines = []
    tool_finished = False
    install_success = False
    install_failure = False

    try:
        while True:
            # Get items from queue without blocking
            line = output_queue.get_nowait()
            if line == "---TOOL_COMPLETE---":
                tool_finished = True
                break
            elif line == "---INSTALL_COMPLETE_SUCCESS---":
                install_success = True
                tool_finished = True # Treat installation completion as a tool completion for frontend
                break
            elif line == "---INSTALL_COMPLETE_FAILURE---":
                install_failure = True
                tool_finished = True # Treat installation completion as a tool completion for frontend
                break
            new_output_lines.append(line)
    except queue.Empty:
        pass # No more lines in queue for now

    current_output_segment = "".join(new_output_lines)

    if tool_finished:
        # Tool operation or installation is truly complete, clean up the queue
        del tool_queues[scan_id]
        status_to_return = 'completed'
        if install_success:
            status_to_return = 'success'
        elif install_failure:
            status_to_return = 'error'
        
        # Ensure the final output includes all accumulated output
        final_output_content = tool_outputs.get(scan_id, "Operation/Installation completed, but output not fully captured.")
        return jsonify({'status': status_to_return, 'output': final_output_content})
    else:
        # Tool operation/Installation is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})


@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the provided content to a file on the server and allows download."""
    data = request.json
    content = data.get('content')
    filename = data.get('filename', f'stegseek_output_{uuid.uuid4()}.txt')

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

@app.route('/install_stegseek', methods=['POST'])
def install_stegseek():
    """
    Attempts to install Stegseek on the server (Linux/Termux only).
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
        tool_queues[scan_id] = output_queue
        tool_outputs[scan_id] = "" # Initialize full output storage for this ID

        def _install_thread(q, current_scan_id, p_type):
            temp_buffer_thread = [] # Local buffer for the thread
            try:
                if p_type == 'termux':
                    update_command = shlex.split("pkg update -y")
                    install_command = shlex.split("pkg install stegseek -y")
                    q.put("Detected Termux. Using 'pkg' for installation.\n")
                elif p_type == 'linux':
                    update_command = shlex.split("sudo apt update -y")
                    install_command = shlex.split("sudo apt install stegseek -y")
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

                # Then, install stegseek
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
                tool_outputs[current_scan_id] = "".join(temp_buffer_thread)

            except subprocess.CalledProcessError as e:
                error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}"
                q.put(error_output)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                tool_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_output
            except FileNotFoundError as e:
                error_msg = f"Error: Command not found ({e}). Ensure 'sudo'/'apt'/'pkg' is installed and in PATH.\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                tool_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_msg
            except Exception as e:
                error_msg = f"An unexpected error occurred during installation: {str(e)}\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                tool_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_msg

        # Start the installation in a separate thread
        install_thread = threading.Thread(target=_install_thread, args=(output_queue, scan_id, platform_type))
        install_thread.daemon = True
        install_thread.start()

        return jsonify({
            'status': 'running',
            'scan_id': scan_id, # Return the unique ID for polling
            'message': f'Stegseek installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Stegseek installation via this interface is only supported on Linux/Termux systems.',
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
    
    print(f"Stegseek sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)

