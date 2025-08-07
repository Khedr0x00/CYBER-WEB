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

# Directory to store temporary files (e.g., generated payloads)
UPLOAD_FOLDER = 'payloads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# In-memory storage for process outputs (for demonstration).
# In a real-world app, consider a more persistent and scalable solution (e.g., database, cloud storage).
process_outputs = {}
process_queues = {} # To store queues for real-time output

# Load examples from msfvenom_examples.txt
def load_examples(filename="msfvenom_examples.txt"):
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
    """Renders the main msfvenom GUI HTML page."""
    return render_template('index.html')

# New endpoint to serve msfvenom examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the msfvenom examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the msfvenom command based on form data."""
    data = request.json
    command_parts = ["msfvenom"]

    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value)))

    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Payload Options
    add_arg("-p", data.get('payload_entry'))
    add_arg("LHOST=", data.get('lhost_entry'))
    add_arg("LPORT=", data.get('lport_entry'))
    add_arg("RHOST=", data.get('rhost_entry'))
    add_arg("RPORT=", data.get('rport_entry'))

    # Encoding Options
    add_arg("-e", data.get('encoder_entry'))
    add_arg("-i", data.get('iterations_entry'))
    add_checkbox_arg("-k", data.get('keep_template_var'))
    add_checkbox_arg("-x", data.get('template_entry'))
    add_checkbox_arg("-a", data.get('arch_entry'))
    add_checkbox_arg("--platform", data.get('platform_entry'))
    add_checkbox_arg("--bad-chars", data.get('bad_chars_entry'))
    add_checkbox_arg("--encoder-info", data.get('encoder_info_var'))

    # Output Options
    add_arg("-f", data.get('format_entry'))
    add_arg("-o", data.get('output_file_entry'))
    add_checkbox_arg("-v", data.get('verbose_var'))
    add_checkbox_arg("-h", data.get('help_var'))
    add_checkbox_arg("--list-options", data.get('list_options_var'))
    add_checkbox_arg("--list-formats", data.get('list_formats_var'))
    add_checkbox_arg("--list-encoders", data.get('list_encoders_var'))
    add_checkbox_arg("--list-payloads", data.get('list_payloads_var'))
    add_checkbox_arg("--list-nops", data.get('list_nops_var'))
    add_checkbox_arg("--list-architectures", data.get('list_architectures_var'))
    add_checkbox_arg("--list-platforms", data.get('list_platforms_var'))

    # Advanced Options
    add_arg("--smallest", data.get('smallest_var'))
    add_arg("--encrypt", data.get('encrypt_entry'))
    add_arg("--encrypt-key", data.get('encrypt_key_entry'))
    add_arg("--encrypt-iv", data.get('encrypt_iv_entry'))
    add_arg("--iteration-time", data.get('iteration_time_entry'))
    add_arg("--template", data.get('custom_template_entry'))
    add_arg("--section", data.get('section_entry'))
    add_arg("--force-platform", data.get('force_platform_entry'))
    add_arg("--force-arch", data.get('force_arch_entry'))
    add_arg("--debug", data.get('debug_var'))
    add_arg("--raw", data.get('raw_var'))
    add_arg("--checksum-type", data.get('checksum_type_entry'))
    add_arg("--add-code", data.get('add_code_entry'))
    add_arg("--prepend-shellcode", data.get('prepend_shellcode_entry'))
    add_arg("--append-shellcode", data.get('append_shellcode_entry'))

    # NOPs Options
    add_arg("-n", data.get('nops_entry'))

    # Custom Options
    custom_options = data.get('custom_options_entry', '').strip()
    if custom_options:
        for opt_line in custom_options.split('\n'):
            opt_line = opt_line.strip()
            if opt_line:
                # Attempt to split by space, but handle quoted arguments correctly
                try:
                    split_opts = shlex.split(opt_line)
                    command_parts.extend(split_opts)
                except ValueError:
                    # Fallback if shlex can't parse, just add as a single string (less safe)
                    command_parts.append(shlex.quote(opt_line))

    generated_cmd = " ".join(command_parts)
    return jsonify({'command': generated_cmd})

@app.route('/run_msfvenom', methods=['POST'])
def run_msfvenom():
    """
    Executes the msfvenom command received from the frontend.
    IMPORTANT: Running arbitrary commands from user input on a web server is a severe security risk.
    This implementation is for demonstration and should NOT be used in a production environment
    without extensive security measures, input validation, and sandboxing.
    """
    data = request.json
    command_str = data.get('command')
    output_filename = data.get('output_file') # Get the desired output filename
    scan_id = str(uuid.uuid4()) # Unique ID for this process

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

    # Ensure msfvenom is the command being run
    if command[0] != 'msfvenom':
        return jsonify({'status': 'error', 'message': 'Only msfvenom commands are allowed.'}), 403

    # Check if msfvenom executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"msfvenom executable '{command[0]}' not found on the server. Please ensure msfvenom is installed and accessible in the system's PATH."}), 500

    # Determine the actual output path for the payload
    final_output_path = None
    if "-o" in command:
        output_index = command.index("-o") + 1
        if output_index < len(command):
            # Use the filename provided in the command, but ensure it's in UPLOAD_FOLDER
            raw_filename = command[output_index]
            # Remove any quotes from the filename
            raw_filename = raw_filename.strip("'\"")
            final_output_path = os.path.join(UPLOAD_FOLDER, os.path.basename(raw_filename))
            command[output_index] = final_output_path # Update command to use absolute path
    elif output_filename: # If -o wasn't in command but a filename was provided by frontend
        final_output_path = os.path.join(UPLOAD_FOLDER, os.path.basename(output_filename))
        command.extend(["-o", final_output_path]) # Add -o to the command

    # Create a new queue for this process's real-time output
    output_queue = queue.Queue()
    process_queues[scan_id] = output_queue
    process_outputs[scan_id] = {"output": "", "file_path": final_output_path} # Initialize full output storage

    def _run_msfvenom_thread(cmd, q, scan_id_val):
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
            
            for line in iter(process.stdout.readline, ''):
                q.put(line) # Put each line into the queue
                full_output_buffer.append(line) # Also append to buffer for final output

            process.wait()
            return_code = process.returncode

            final_status_line = f"\nmsfvenom finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            process_outputs[scan_id_val]["output"] = "".join(full_output_buffer) # Store complete output
            process_outputs[scan_id_val]["status"] = 'completed' if return_code == 0 else 'error'

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure msfvenom is installed and in your system's PATH.\nSTATUS: Error\n"
            q.put(error_msg)
            process_outputs[scan_id_val]["output"] = error_msg
            process_outputs[scan_id_val]["status"] = 'error'
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}\nSTATUS: Error\n"
            q.put(error_msg)
            process_outputs[scan_id_val]["output"] = error_msg
            process_outputs[scan_id_val]["status"] = 'error'
        finally:
            # Signal end of output by putting a special marker
            q.put("---PROCESS_COMPLETE---")


    # Start the msfvenom process in a separate thread
    thread = threading.Thread(target=_run_msfvenom_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'msfvenom command started.', 'output_file_path': final_output_path})

@app.route('/get_process_output/<scan_id>', methods=['GET'])
def get_process_output(scan_id):
    """
    Polls for real-time msfvenom process output.
    Returns new lines from the queue or the final output if process is complete.
    """
    output_queue = process_queues.get(scan_id)
    if not output_queue:
        # If queue is not found, check if the process completed and its final output is stored
        final_info = process_outputs.get(scan_id)
        if final_info:
            return jsonify({'status': final_info.get('status', 'completed'), 'output': final_info['output'], 'file_path': final_info.get('file_path')})
        return jsonify({'status': 'not_found', 'message': 'Process ID not found or expired.'}), 404

    new_output_lines = []
    process_finished = False

    try:
        while True:
            # Get items from queue without blocking
            line = output_queue.get_nowait()
            if line == "---PROCESS_COMPLETE---":
                process_finished = True
                break
            new_output_lines.append(line)
    except queue.Empty:
        pass # No more lines in queue for now

    current_output_segment = "".join(new_output_lines)

    if process_finished:
        # Process is truly complete, clean up the queue
        del process_queues[scan_id]
        final_info = process_outputs.get(scan_id, {"output": "Process completed, but output not fully captured.", "status": "completed"})
        return jsonify({'status': final_info.get('status'), 'output': final_info['output'], 'file_path': final_info.get('file_path')})
    else:
        # Process is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})

@app.route('/download_payload/<filename>')
def download_payload(filename):
    """Allows downloading a generated payload file."""
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'status': 'error', 'message': 'File not found.'}), 404

@app.route('/install_msfvenom', methods=['POST'])
def install_msfvenom():
    """
    Attempts to install Metasploit Framework (which includes msfvenom) on the server (Linux/Termux only).
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
        process_queues[scan_id] = output_queue
        process_outputs[scan_id] = {"output": "", "status": "running"} # Initialize full output storage for this ID

        def _install_thread(q, current_scan_id, p_type):
            temp_buffer_thread = [] # Local buffer for the thread
            try:
                if p_type == 'termux':
                    update_command = shlex.split("pkg update -y && pkg upgrade -y")
                    install_command = shlex.split("pkg install metasploit -y")
                    q.put("Detected Termux. Using 'pkg' for installation.\n")
                elif p_type == 'linux':
                    # For Kali/Ubuntu, Metasploit is usually in the default repos
                    update_command = shlex.split("sudo apt update -y && sudo apt upgrade -y")
                    install_command = shlex.split("sudo apt install metasploit-framework -y")
                    q.put("Detected Linux. Using 'sudo apt' for installation.\n")
                else:
                    q.put("Error: Unsupported platform type for installation.\n")
                    q.put("---PROCESS_COMPLETE---")
                    process_outputs[current_scan_id]["status"] = 'error'
                    return

                # First, update and upgrade package list
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
                    q.put(f"Update/Upgrade command failed with exit code {update_process.returncode}\n")
                    raise subprocess.CalledProcessError(update_process.returncode, update_command, "".join(temp_buffer_thread), "")

                # Then, install metasploit
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
                process_outputs[current_scan_id]["output"] = "".join(temp_buffer_thread)
                process_outputs[current_scan_id]["status"] = 'success'
                q.put("---PROCESS_COMPLETE---")

            except subprocess.CalledProcessError as e:
                error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}"
                q.put(error_output)
                process_outputs[current_scan_id]["output"] = "".join(temp_buffer_thread) + error_output
                process_outputs[current_scan_id]["status"] = 'error'
                q.put("---PROCESS_COMPLETE---")
            except FileNotFoundError as e:
                error_msg = f"Error: Command not found ({e}). Ensure 'sudo'/'apt'/'pkg' is installed and in PATH.\n"
                q.put(error_msg)
                process_outputs[current_scan_id]["output"] = "".join(temp_buffer_thread) + error_msg
                process_outputs[current_scan_id]["status"] = 'error'
                q.put("---PROCESS_COMPLETE---")
            except Exception as e:
                error_msg = f"An unexpected error occurred during installation: {str(e)}\n"
                q.put(error_msg)
                process_outputs[current_scan_id]["output"] = "".join(temp_buffer_thread) + error_msg
                process_outputs[current_scan_id]["status"] = 'error'
                q.put("---PROCESS_COMPLETE---")

        # Start the installation in a separate thread
        install_thread = threading.Thread(target=_install_thread, args=(output_queue, scan_id, platform_type))
        install_thread.daemon = True
        install_thread.start()

        return jsonify({
            'status': 'running',
            'scan_id': scan_id, # Return the unique ID for polling
            'message': f'msfvenom installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'msfvenom installation via this interface is only supported on Linux/Termux systems.',
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
    
    print(f"msfvenom sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)

