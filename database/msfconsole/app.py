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
msf_outputs = {}
msf_processes = {} # To keep track of running msfconsole processes
msf_queues = {} # To store queues for real-time output

# Load examples from msf_examples.txt
def load_examples(filename="msf_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming msf_examples.txt is in the same directory as app.py
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
    """Renders the main Metasploit GUI HTML page."""
    return render_template('index.html')

# New endpoint to serve Metasploit examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the Metasploit examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the msfconsole command based on form data."""
    data = request.json
    command_parts = ["msfconsole", "-q"] # -q for quiet startup

    # Module Type and Name
    module_type = data.get('module_type_select')
    module_name = data.get('module_name_entry')

    if module_type and module_name:
        command_parts.append(f"use {module_type}/{module_name}")
    elif module_name: # If only module name is provided, assume it's for search
        command_parts = ["msfconsole", "-q", f"search {module_name}"]
        return jsonify({'command': " ".join(command_parts)}) # Return early for search

    # Global Options (setg)
    global_options = []
    if data.get('lhost_entry'):
        global_options.append(f"setg LHOST {shlex.quote(data['lhost_entry'])}")
    if data.get('lport_entry'):
        global_options.append(f"setg LPORT {shlex.quote(str(data['lport_entry']))}")
    if data.get('rhost_entry'):
        global_options.append(f"setg RHOSTS {shlex.quote(data['rhost_entry'])}")
    if data.get('rport_entry'):
        global_options.append(f"setg RPORT {shlex.quote(str(data['rport_entry']))}")
    if data.get('payload_entry'):
        global_options.append(f"setg PAYLOAD {shlex.quote(data['payload_entry'])}")
    if data.get('encoder_entry'):
        global_options.append(f"setg ENCODER {shlex.quote(data['encoder_entry'])}")
    if data.get('nops_entry'):
        global_options.append(f"setg NOP {shlex.quote(data['nops_entry'])}")
    if data.get('platform_entry'):
        global_options.append(f"setg PLATFORM {shlex.quote(data['platform_entry'])}")
    if data.get('arch_entry'):
        global_options.append(f"setg ARCH {shlex.quote(data['arch_entry'])}")
    if data.get('exit_func_entry'):
        global_options.append(f"setg ExitFunction {shlex.quote(data['exit_func_entry'])}")
    if data.get('disable_payload_handler_var'):
        global_options.append("setg DisablePayloadHandler true")
    if data.get('auto_run_script_entry'):
        global_options.append(f"setg AutoRunScript {shlex.quote(data['auto_run_script_entry'])}")
    if data.get('session_comm_timeout_entry'):
        global_options.append(f"setg SessionCommunicationTimeout {shlex.quote(str(data['session_comm_timeout_entry']))}")
    if data.get('session_exp_timeout_entry'):
        global_options.append(f"setg SessionExpirationTimeout {shlex.quote(str(data['session_exp_timeout_entry']))}")
    if data.get('reverse_listener_bind_addr_entry'):
        global_options.append(f"setg ReverseListenerBindAddress {shlex.quote(data['reverse_listener_bind_addr_entry'])}")
    if data.get('reverse_listener_bind_port_entry'):
        global_options.append(f"setg ReverseListenerBindPort {shlex.quote(str(data['reverse_listener_bind_port_entry']))}")

    # Module-specific options (set)
    module_options = []
    if data.get('custom_options_entry'):
        for line in data['custom_options_entry'].split('\n'):
            line = line.strip()
            if line and '=' in line:
                module_options.append(f"set {shlex.quote(line)}")
            elif line: # For options like 'show options' or 'info'
                module_options.append(line)

    # Actions
    action_command = ""
    if data.get('show_options_var'):
        action_command = "show options"
    elif data.get('show_payloads_var'):
        action_command = "show payloads"
    elif data.get('show_targets_var'):
        action_command = "show targets"
    elif data.get('run_exploit_var'):
        action_command = "exploit -j -z" # -j for job, -z for don't interact
    elif data.get('check_exploit_var'):
        action_command = "check"
    elif data.get('background_session_var'):
        action_command = "background"
    elif data.get('sessions_list_var'):
        action_command = "sessions -l"
    elif data.get('interact_session_entry'):
        action_command = f"sessions -i {shlex.quote(str(data['interact_session_entry']))}"
    elif data.get('kill_session_entry'):
        action_command = f"sessions -k {shlex.quote(str(data['kill_session_entry']))}"
    elif data.get('exit_msfconsole_var'):
        action_command = "exit"

    # Combine parts
    full_command_list = []
    if global_options:
        full_command_list.extend(global_options)
    if module_type and module_name:
        full_command_list.append(f"use {module_type}/{module_name}")
    if module_options:
        full_command_list.extend(module_options)
    if action_command:
        full_command_list.append(action_command)

    # Join with semicolons for msfconsole -x
    generated_cmd = f"msfconsole -x \"{' ; '.join(full_command_list)}\""
    
    # Special handling for 'search' command to not use -x
    if command_parts[0] == "msfconsole" and command_parts[-2] == "search":
        generated_cmd = " ".join(command_parts)


    return jsonify({'command': generated_cmd})

@app.route('/run_msfconsole', methods=['POST'])
def run_msfconsole():
    """
    Executes the msfconsole command received from the frontend.
    IMPORTANT: Running arbitrary commands from user input on a web server is a severe security risk.
    This implementation is for demonstration and should NOT be used in a production environment
    without extensive security measures, input validation, and sandboxing.
    """
    data = request.json
    command_str = data.get('command')
    scan_id = str(uuid.uuid4()) # Unique ID for this process

    if not command_str:
        return jsonify({'status': 'error', 'message': 'No command provided.'}), 400

    # Basic check to prevent common dangerous commands. This is NOT exhaustive.
    if any(cmd in command_str for cmd in ['rm ', 'sudo ', 'reboot', 'shutdown', 'init ']):
        return jsonify({'status': 'error', 'message': 'Potentially dangerous command detected. Operation aborted.'}), 403

    # Use shlex.split to safely split the command string into a list
    try:
        # msfconsole -x "commands" needs special handling for shlex
        if command_str.startswith("msfconsole -x \"") and command_str.endswith("\""):
            # Extract the inner commands, then split them by ';'
            inner_commands_str = command_str[len("msfconsole -x \""):-1]
            # Split by ';' but handle quoted strings within
            commands_to_execute = [cmd.strip() for cmd in inner_commands_str.split(';') if cmd.strip()]
            
            # Reconstruct for subprocess.Popen
            command = ["msfconsole", "-x", "; ".join(commands_to_execute)]
        else:
            command = shlex.split(command_str)
    except ValueError as e:
        return jsonify({'status': 'error', 'message': f'Error parsing command: {e}'}), 400

    # Ensure msfconsole is the command being run
    if command[0] != 'msfconsole':
        return jsonify({'status': 'error', 'message': 'Only msfconsole commands are allowed.'}), 403

    # Check if msfconsole executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"msfconsole executable '{command[0]}' not found on the server. Please ensure Metasploit is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this process's real-time output
    output_queue = queue.Queue()
    msf_queues[scan_id] = output_queue
    msf_outputs[scan_id] = "" # Initialize full output storage

    def _run_msfconsole_thread(cmd, q, scan_id_val):
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
            msf_processes[scan_id_val] = process

            for line in iter(process.stdout.readline, ''):
                q.put(line) # Put each line into the queue
                full_output_buffer.append(line) # Also append to buffer for final output

            process.wait()
            return_code = process.returncode

            final_status_line = f"\nMetasploit finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            msf_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure Metasploit is installed and in your system's PATH.\nSTATUS: Error\n"
            q.put(error_msg)
            msf_outputs[scan_id_val] = error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}\nSTATUS: Error\n"
            q.put(error_msg)
            msf_outputs[scan_id_val] = error_msg
        finally:
            if scan_id_val in msf_processes:
                del msf_processes[scan_id_val]
            # Signal end of output by putting a special marker
            q.put("---SCAN_COMPLETE---")


    # Start the msfconsole process in a separate thread
    thread = threading.Thread(target=_run_msfconsole_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'Metasploit command started.'})

# Modified get_scan_output to handle 'msf_install' ID
@app.route('/get_msf_output/<scan_id>', methods=['GET'])
def get_msf_output(scan_id):
    """
    Polls for real-time msfconsole output.
    Returns new lines from the queue or the final output if process is complete.
    """
    output_queue = msf_queues.get(scan_id)
    if not output_queue:
        # If queue is not found, check if the process completed and its final output is stored
        final_output = msf_outputs.get(scan_id)
        final_status = msf_outputs.get(scan_id + "_status") # Check for installation status
        if final_output and final_status:
            return jsonify({'status': final_status, 'output': final_output})
        elif final_output: # If it's a regular process that completed
            return jsonify({'status': 'completed', 'output': final_output})
        return jsonify({'status': 'not_found', 'message': 'Process ID not found or expired.'}), 404

    new_output_lines = []
    process_finished = False
    install_success = False
    install_failure = False

    try:
        while True:
            # Get items from queue without blocking
            line = output_queue.get_nowait()
            if line == "---SCAN_COMPLETE---":
                process_finished = True
                break
            elif line == "---INSTALL_COMPLETE_SUCCESS---":
                install_success = True
                process_finished = True # Treat installation completion as a process completion for frontend
                break
            elif line == "---INSTALL_COMPLETE_FAILURE---":
                install_failure = True
                process_finished = True # Treat installation completion as a process completion for frontend
                break
            new_output_lines.append(line)
    except queue.Empty:
        pass # No more lines in queue for now

    current_output_segment = "".join(new_output_lines)

    if process_finished:
        # Process or installation is truly complete, clean up the queue
        del msf_queues[scan_id]
        status_to_return = 'completed'
        if install_success:
            status_to_return = 'success'
        elif install_failure:
            status_to_return = 'error'
        
        # Ensure the final output includes all accumulated output
        final_output_content = msf_outputs.get(scan_id, "Process/Installation completed, but output not fully captured.")
        return jsonify({'status': status_to_return, 'output': final_output_content})
    else:
        # Process/Installation is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})


@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the provided content to a file on the server and allows download."""
    data = request.json
    content = data.get('content')
    filename = data.get('filename', f'msfconsole_output_{uuid.uuid4()}.txt')

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

@app.route('/install_metasploit', methods=['POST'])
def install_metasploit():
    """
    Attempts to install Metasploit on the server (Linux/Termux only).
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
        msf_queues[scan_id] = output_queue
        msf_outputs[scan_id] = "" # Initialize full output storage for this ID

        def _install_thread(q, current_scan_id, p_type):
            temp_buffer_thread = [] # Local buffer for the thread
            try:
                if p_type == 'termux':
                    q.put("Detected Termux. Using 'pkg' for installation.\n")
                    # Metasploit installation on Termux is usually via a script or direct package
                    # This is a simplified example; real Termux install might be more complex.
                    # For a full install, one might use: pkg install unstable-repo && pkg install metasploit
                    commands = [
                        shlex.split("pkg update -y"),
                        shlex.split("pkg upgrade -y"),
                        shlex.split("pkg install unstable-repo -y"),
                        shlex.split("pkg install metasploit -y")
                    ]
                elif p_type == 'linux':
                    q.put("Detected Linux. Using 'sudo apt' for installation.\n")
                    # Metasploit installation on Linux (Debian/Ubuntu)
                    commands = [
                        shlex.split("sudo apt update -y"),
                        shlex.split("sudo apt install curl gnupg2 -y"),
                        shlex.split("curl https://apt.metasploit.com/metasploit-framework.gpg --output /tmp/metasploit-framework.gpg"),
                        shlex.split("sudo gpg --no-default-keyring --keyring /etc/apt/trusted.gpg.d/metasploit-framework.gpg --import /tmp/metasploit-framework.gpg"),
                        shlex.split("sudo sh -c 'echo \"deb http://apt.metasploit.com/ focal main\" > /etc/apt/sources.list.d/metasploit-framework.list'"),
                        shlex.split("sudo apt update -y"),
                        shlex.split("sudo apt install metasploit-framework -y")
                    ]
                else:
                    q.put("Error: Unsupported platform type for installation.\n")
                    q.put("---INSTALL_COMPLETE_FAILURE---")
                    return

                for cmd in commands:
                    q.put(f"\nExecuting: {' '.join(cmd)}\n")
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
                msf_outputs[current_scan_id] = "".join(temp_buffer_thread)

            except subprocess.CalledProcessError as e:
                error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}"
                q.put(error_output)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                msf_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_output
            except FileNotFoundError as e:
                error_msg = f"Error: Command not found ({e}). Ensure necessary tools are installed and in PATH.\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                msf_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_msg
            except Exception as e:
                error_msg = f"An unexpected error occurred during installation: {str(e)}\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                msf_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_msg

        # Start the installation in a separate thread
        install_thread = threading.Thread(target=_install_thread, args=(output_queue, scan_id, platform_type))
        install_thread.daemon = True
        install_thread.start()

        return jsonify({
            'status': 'running',
            'scan_id': scan_id, # Return the unique ID for polling
            'message': f'Metasploit installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Metasploit installation via this interface is only supported on Linux/Termux systems.',
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
    
    print(f"Metasploit sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)

