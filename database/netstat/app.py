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
scan_processes = {} # To keep track of running processes
scan_queues = {} # To store queues for real-time output

# Load examples from netstat_examples.txt
def load_examples(filename="netstat_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming netstat_examples.txt is in the same directory as app.py
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
    """Renders the main Netstat GUI HTML page."""
    return render_template('index.html')

# New endpoint to serve Netstat examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the Netstat examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the Netstat command based on form data."""
    data = request.json
    command_parts = ["netstat"]

    # Helper to add a flag if its checkbox is true
    def add_flag(flag_name, value):
        if value:
            command_parts.append(flag_name)

    # Helper to add an option with a value if provided
    def add_option_value(option_name, value):
        if value:
            command_parts.append(option_name)
            command_parts.append(shlex.quote(str(value)))

    # Main Options Tab
    add_flag("-a", data.get('all_connections_var'))
    add_flag("-t", data.get('tcp_connections_var'))
    add_flag("-u", data.get('udp_connections_var'))
    add_flag("-n", data.get('numeric_var'))
    add_flag("-p", data.get('program_name_pid_var')) # Linux/macOS
    add_flag("-r", data.get('routing_table_var'))
    add_flag("-s", data.get('statistics_var'))
    add_flag("-l", data.get('listening_sockets_var')) # Linux/macOS
    add_flag("-e", data.get('ethernet_statistics_var')) # Windows only
    add_flag("-v", data.get('verbose_var')) # Windows/Linux (behavior varies)

    # Continuous display (Linux/Termux specific, -c flag)
    if data.get('continuous_display_var'):
        command_parts.append("-c")
        interval = data.get('interval_entry')
        if interval:
            command_parts.append(shlex.quote(str(interval)))

    # Filtering Tab (using grep/findstr for cross-platform filtering)
    # These will be handled post-netstat execution or as part of additional arguments
    # For now, we'll focus on direct netstat flags.
    # The frontend will likely need to filter output client-side for these.

    # Netstat itself doesn't have direct flags for state/port/protocol filtering in a universal way
    # like 'netstat --state ESTABLISHED'. These are typically done with `grep` or `findstr`.
    # We will generate the base netstat command and let the frontend handle the filtering
    # or add a note that these are for post-processing.
    # For a "real tool", if the user wants server-side filtering, we'd need to pipe the output.

    # Advanced/Output Control Tab
    add_flag("--numeric-ports", data.get('numeric_ports_var')) # Linux/macOS
    add_flag("--numeric-hosts", data.get('numeric_hosts_var')) # Linux/macOS
    add_flag("--program", data.get('program_name_pid_var')) # Alias for -p on Linux
    add_flag("--timers", data.get('timers_var')) # Linux/macOS
    add_flag("--extend", data.get('extended_output_var')) # Linux/macOS
    add_flag("--wide", data.get('wide_output_var')) # Linux/macOS
    add_flag("--line", data.get('single_line_var')) # Linux/macOS

    # Protocol filtering (if specific to netstat implementation, otherwise handled by grep)
    protocol_filter = data.get('protocol_filter_entry')
    if protocol_filter and protocol_filter != "any":
        # On Windows, -p can filter protocols (e.g., netstat -p tcp)
        # On Linux, filtering is often done by `grep`
        if sys.platform.startswith('win'):
            command_parts.append("-p")
            command_parts.append(shlex.quote(protocol_filter))
        # For Linux, we'll assume client-side filtering or advanced piping via additional args

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

    # Add client-side filtering instructions if relevant filters are applied
    client_side_filter_instructions = ""
    state_filter = data.get('state_filter_entry')
    port_filter = data.get('port_filter_entry')

    if state_filter:
        client_side_filter_instructions += f" | Filter by state: '{state_filter}'"
    if port_filter:
        client_side_filter_instructions += f" | Filter by port: '{port_filter}'"
    
    if client_side_filter_instructions:
        generated_cmd += f" # NOTE: Client-side filtering will apply: {client_side_filter_instructions}"

    return jsonify({'command': generated_cmd})

@app.route('/run_netstat', methods=['POST'])
def run_netstat():
    """
    Executes the Netstat command received from the frontend.
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
    if any(cmd in command_str for cmd in ['rm ', 'sudo ', 'reboot', 'shutdown', 'init ', 'format', 'del ']):
        return jsonify({'status': 'error', 'message': 'Potentially dangerous command detected. Operation aborted.'}), 403

    # Use shlex.split to safely split the command string into a list
    try:
        command = shlex.split(command_str)
    except ValueError as e:
        return jsonify({'status': 'error', 'message': f'Error parsing command: {e}'}), 400

    # Ensure netstat is the command being run
    if command[0] != 'netstat':
        return jsonify({'status': 'error', 'message': 'Only Netstat commands are allowed.'}), 403

    # Check if netstat executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"Netstat executable '{command[0]}' not found on the server. Please ensure Netstat is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this execution's real-time output
    output_queue = queue.Queue()
    scan_queues[scan_id] = output_queue
    scan_outputs[scan_id] = "" # Initialize full output storage

    def _run_netstat_thread(cmd, q, scan_id_val):
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

            final_status_line = f"\nNetstat finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            scan_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure Netstat is installed and in your system's PATH.\nSTATUS: Error\n"
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


    # Start the Netstat process in a separate thread
    thread = threading.Thread(target=_run_netstat_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'Netstat command started.'})

@app.route('/get_scan_output/<scan_id>', methods=['GET'])
def get_scan_output(scan_id):
    """
    Polls for real-time Netstat command output.
    Returns new lines from the queue or the final output if command is complete.
    """
    output_queue = scan_queues.get(scan_id)
    if not output_queue:
        # If queue is not found, check if the command completed and its final output is stored
        final_output = scan_outputs.get(scan_id)
        if final_output:
            return jsonify({'status': 'completed', 'output': final_output})
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
        # Command is truly complete, clean up the queue
        del scan_queues[scan_id]
        status_to_return = 'completed'
        
        # Ensure the final output includes all accumulated output
        final_output_content = scan_outputs.get(scan_id, "Command completed, but output not fully captured.")
        return jsonify({'status': status_to_return, 'output': final_output_content})
    else:
        # Command is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})


@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the provided content to a file on the server and allows download."""
    data = request.json
    content = data.get('content')
    filename = data.get('filename', f'netstat_output_{uuid.uuid4()}.txt')

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

@app.route('/install_netstat', methods=['POST'])
def install_netstat():
    """
    Provides guidance for installing net-tools (which includes netstat) on various systems.
    Direct automatic installation is limited for security reasons.
    """
    data = request.json
    platform_type = data.get('platform') # 'linux', 'termux', 'windows'

    scan_id = str(uuid.uuid4()) # Unique ID for this "installation" process
    output_queue = queue.Queue()
    scan_queues[scan_id] = output_queue
    scan_outputs[scan_id] = "" # Initialize full output storage for this ID

    def _install_guidance_thread(q, current_scan_id, p_type):
        temp_buffer_thread = []
        try:
            if p_type == 'termux':
                guidance_msg = "Netstat on Termux is typically provided by the 'net-tools' package.\n" \
                               "To install, open your Termux app and run:\n" \
                               "pkg update -y\n" \
                               "pkg install net-tools -y\n" \
                               "Please execute these commands directly in your Termux terminal."
            elif p_type == 'linux':
                guidance_msg = "Netstat on Linux is usually part of the 'net-tools' package. Modern Linux distributions often use 'iproute2' commands (like 'ip a', 'ss -tunlp') instead of 'netstat'.\n" \
                               "To install 'net-tools' (if not already present), open your terminal and run:\n" \
                               "sudo apt update -y  (for Debian/Ubuntu-based systems)\n" \
                               "sudo apt install net-tools -y\n\n" \
                               "sudo dnf install net-tools -y (for Fedora/RHEL-based systems)\n" \
                               "Please execute these commands directly in your Linux terminal."
            elif p_type == 'windows':
                guidance_msg = "Netstat is a built-in command on Windows operating systems (netstat.exe).\n" \
                               "No installation is required. You can run 'netstat' directly from Command Prompt or PowerShell."
            else:
                guidance_msg = f"Unsupported platform type '{p_type}' for installation guidance."

            q.put(guidance_msg + "\n---SCAN_COMPLETE---") # Use SCAN_COMPLETE marker
            scan_outputs[current_scan_id] = guidance_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred while generating installation guidance: {str(e)}\n"
            q.put(error_msg + "---SCAN_COMPLETE---")
            scan_outputs[current_scan_id] = error_msg

    # Start the guidance generation in a separate thread
    install_thread = threading.Thread(target=_install_guidance_thread, args=(output_queue, scan_id, platform_type))
    install_thread.daemon = True
    install_thread.start()

    return jsonify({
        'status': 'running',
        'scan_id': scan_id, # Return the unique ID for polling
        'message': f'Providing Netstat installation guidance for {platform_type}. Polling for output...'
    })

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
    
    print(f"Netstat sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)

