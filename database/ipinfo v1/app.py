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
tool_outputs = {}
tool_processes = {} # To keep track of running processes
tool_queues = {} # To store queues for real-time output

# Load examples from ip_info_examples.txt
def load_examples(filename="ip_info_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming ip_info_examples.txt is in the same directory as app.py
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
    """Renders the main IP Info GUI HTML page."""
    return render_template('index.html')

# New endpoint to serve examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the command based on form data and selected tool."""
    data = request.json
    tool_type = data.get('tool_type')
    command_parts = []

    target = shlex.quote(data.get('target_entry', '').strip())
    if not target:
        return jsonify({'command': 'Please enter a target IP or hostname.'})

    if tool_type == 'whois':
        command_parts.append("whois")
        if data.get('whois_verbose_var'):
            command_parts.append("-v")
        if data.get('whois_no_recursion_var'):
            command_parts.append("-r")
        if data.get('whois_server_entry'):
            command_parts.append("-h")
            command_parts.append(shlex.quote(data['whois_server_entry']))
        command_parts.append(target)
    elif tool_type == 'ping':
        command_parts.append("ping")
        if sys.platform.startswith('linux') or sys.platform == 'darwin': # Linux/macOS
            if data.get('ping_count_entry'):
                command_parts.append("-c")
                command_parts.append(str(data['ping_count_entry']))
            if data.get('ping_interval_entry'):
                command_parts.append("-i")
                command_parts.append(str(data['ping_interval_entry']))
            if data.get('ping_size_entry'):
                command_parts.append("-s")
                command_parts.append(str(data['ping_size_entry']))
            if data.get('ping_timeout_entry'):
                command_parts.append("-W") # Timeout in seconds for Linux
                command_parts.append(str(data['ping_timeout_entry']))
        elif sys.platform == 'win32': # Windows
            if data.get('ping_count_entry'):
                command_parts.append("-n")
                command_parts.append(str(data['ping_count_entry']))
            if data.get('ping_size_entry'):
                command_parts.append("-l")
                command_parts.append(str(data['ping_size_entry']))
            if data.get('ping_timeout_entry'):
                command_parts.append("-w") # Timeout in milliseconds for Windows
                command_parts.append(str(int(data['ping_timeout_entry']) * 1000)) # Convert to ms
        command_parts.append(target)
    elif tool_type == 'traceroute':
        command_parts.append("traceroute")
        if data.get('traceroute_max_hops_entry'):
            command_parts.append("-m")
            command_parts.append(str(data['traceroute_max_hops_entry']))
        if data.get('traceroute_wait_time_entry'):
            command_parts.append("-w")
            command_parts.append(str(data['traceroute_wait_time_entry']))
        if data.get('traceroute_tcp_var'):
            command_parts.append("-T") # TCP traceroute (Linux)
        elif data.get('traceroute_udp_var'):
            command_parts.append("-U") # UDP traceroute (Linux)
        command_parts.append(target)
    elif tool_type == 'dnslookup':
        dns_tool = data.get('dns_tool_select', 'dig')
        if dns_tool == 'dig':
            command_parts.append("dig")
            if data.get('dig_type_select'):
                command_parts.append(data['dig_type_select'])
            if data.get('dig_short_var'):
                command_parts.append("+short")
            if data.get('dig_trace_var'):
                command_parts.append("+trace")
            if data.get('dig_server_entry'):
                command_parts.append(f"@{shlex.quote(data['dig_server_entry'])}")
            command_parts.append(target)
        elif dns_tool == 'nslookup':
            command_parts.append("nslookup")
            if data.get('nslookup_server_entry'):
                command_parts.append(shlex.quote(data['nslookup_server_entry']))
            if data.get('nslookup_type_select'):
                command_parts.append("-type=" + data['nslookup_type_select'])
            command_parts.append(target)
        # Fallback for Windows if dig/nslookup not found, use system nslookup
        if sys.platform == 'win32' and not shutil.which(command_parts[0]):
            command_parts = ["nslookup"]
            if data.get('nslookup_server_entry'):
                command_parts.append(shlex.quote(data['nslookup_server_entry']))
            command_parts.append(target)
            # Windows nslookup doesn't have -type= easily, so simplify for now
            if data.get('nslookup_type_select') and data['nslookup_type_select'] != 'A':
                 return jsonify({'command': 'Windows nslookup does not easily support specific query types like this in command line. Use default A record or try dig on Linux/Termux.'})


    generated_cmd = " ".join(command_parts)
    return jsonify({'command': generated_cmd})

@app.route('/run_tool', methods=['POST'])
def run_tool():
    """
    Executes the command received from the frontend.
    IMPORTANT: Running arbitrary commands from user input on a web server is a severe security risk.
    This implementation is for demonstration and should NOT be used in a production environment
    without extensive security measures, input validation, and sandboxing.
    """
    data = request.json
    command_str = data.get('command')
    tool_id = str(uuid.uuid4()) # Unique ID for this tool run

    if not command_str:
        return jsonify({'status': 'error', 'message': 'No command provided.'}), 400

    # Basic check to prevent common dangerous commands. This is NOT exhaustive.
    if any(cmd in command_str for cmd in ['rm ', 'sudo ', 'reboot', 'shutdown', 'init ', 'format ', 'del ']):
        return jsonify({'status': 'error', 'message': 'Potentially dangerous command detected. Operation aborted.'}), 403

    # Use shlex.split to safely split the command string into a list
    try:
        command = shlex.split(command_str)
    except ValueError as e:
        return jsonify({'status': 'error', 'message': f'Error parsing command: {e}'}), 400

    # Check if executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"Executable '{command[0]}' not found on the server. Please ensure the tool is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this tool's real-time output
    output_queue = queue.Queue()
    tool_queues[tool_id] = output_queue
    tool_outputs[tool_id] = "" # Initialize full output storage

    def _run_tool_thread(cmd, q, tool_id_val):
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
            tool_processes[tool_id_val] = process

            for line in iter(process.stdout.readline, ''):
                q.put(line) # Put each line into the queue
                full_output_buffer.append(line) # Also append to buffer for final output

            process.wait()
            return_code = process.returncode

            final_status_line = f"\nTool finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            tool_outputs[tool_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure the tool is installed and in your system's PATH.\nSTATUS: Error\n"
            q.put(error_msg)
            tool_outputs[tool_id_val] = error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}\nSTATUS: Error\n"
            q.put(error_msg)
            tool_outputs[tool_id_val] = error_msg
        finally:
            if tool_id_val in tool_processes:
                del tool_processes[tool_id_val]
            # Signal end of output by putting a special marker
            q.put("---TOOL_COMPLETE---")


    # Start the tool process in a separate thread
    thread = threading.Thread(target=_run_tool_thread, args=(command, output_queue, tool_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'tool_id': tool_id, 'message': 'Tool execution started.'})

@app.route('/get_tool_output/<tool_id>', methods=['GET'])
def get_tool_output(tool_id):
    """
    Polls for real-time tool output.
    Returns new lines from the queue or the final output if tool run is complete.
    """
    output_queue = tool_queues.get(tool_id)
    if not output_queue:
        # If queue is not found, check if the tool run completed and its final output is stored
        final_output = tool_outputs.get(tool_id)
        if final_output: # If it's a regular tool run that completed
            return jsonify({'status': 'completed', 'output': final_output})
        return jsonify({'status': 'not_found', 'message': 'Tool ID not found or expired.'}), 404

    new_output_lines = []
    tool_finished = False

    try:
        while True:
            # Get items from queue without blocking
            line = output_queue.get_nowait()
            if line == "---TOOL_COMPLETE---":
                tool_finished = True
                break
            new_output_lines.append(line)
    except queue.Empty:
        pass # No more lines in queue for now

    current_output_segment = "".join(new_output_lines)

    if tool_finished:
        # Tool run is truly complete, clean up the queue
        del tool_queues[tool_id]
        status_to_return = 'completed'
        
        # Ensure the final output includes all accumulated output
        final_output_content = tool_outputs.get(tool_id, "Tool completed, but output not fully captured.")
        return jsonify({'status': status_to_return, 'output': final_output_content})
    else:
        # Tool is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})


@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the provided content to a file on the server and allows download."""
    data = request.json
    content = data.get('content')
    filename = data.get('filename', f'ip_info_output_{uuid.uuid4()}.txt')

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

@app.route('/install_tool', methods=['POST'])
def install_tool():
    """
    Attempts to install common IP info tools on the server (Linux/Termux only).
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
        install_id = str(uuid.uuid4()) # Unique ID for this installation process
        full_output = []
        output_queue = queue.Queue()
        tool_queues[install_id] = output_queue
        tool_outputs[install_id] = "" # Initialize full output storage for this ID

        def _install_thread(q, current_install_id, p_type):
            temp_buffer_thread = [] # Local buffer for the thread
            try:
                if p_type == 'termux':
                    update_command = shlex.split("pkg update -y")
                    install_commands = [
                        shlex.split("pkg install whois -y"),
                        shlex.split("pkg install iputils -y"), # for ping, traceroute
                        shlex.split("pkg install dnsutils -y") # for dig, nslookup
                    ]
                    q.put("Detected Termux. Using 'pkg' for installation.\n")
                elif p_type == 'linux':
                    update_command = shlex.split("sudo apt update -y")
                    install_commands = [
                        shlex.split("sudo apt install whois -y"),
                        shlex.split("sudo apt install iputils-ping -y"), # for ping
                        shlex.split("sudo apt install iputils-tracepath -y"), # for traceroute
                        shlex.split("sudo apt install dnsutils -y") # for dig, nslookup
                    ]
                    q.put("Detected Linux. Using 'sudo apt' for installation.\n")
                else:
                    q.put("Error: Unsupported platform type for installation.\n")
                    q.put("---TOOL_COMPLETE---") # Use generic complete marker
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

                # Then, install tools
                for cmd in install_commands:
                    q.put(f"\nExecuting: {' '.join(cmd)}\n")
                    install_process = subprocess.Popen(
                        cmd,
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
                        # Don't raise error immediately, try other installations
                        # For now, just log and continue, mark overall as failure later
                        pass
                
                # Signal success and store final output
                q.put("---TOOL_COMPLETE---") # Use generic complete marker
                tool_outputs[current_install_id] = "".join(temp_buffer_thread)

            except subprocess.CalledProcessError as e:
                error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}"
                q.put(error_output)
                q.put("---TOOL_COMPLETE---")
                tool_outputs[current_install_id] = "".join(temp_buffer_thread) + error_output
            except FileNotFoundError as e:
                error_msg = f"Error: Command not found ({e}). Ensure 'sudo'/'apt'/'pkg' is installed and in PATH.\n"
                q.put(error_msg)
                q.put("---TOOL_COMPLETE---")
                tool_outputs[current_install_id] = "".join(temp_buffer_thread) + error_msg
            except Exception as e:
                error_msg = f"An unexpected error occurred during installation: {str(e)}\n"
                q.put(error_msg)
                q.put("---TOOL_COMPLETE---")
                tool_outputs[current_install_id] = "".join(temp_buffer_thread) + error_msg

        # Start the installation in a separate thread
        install_thread = threading.Thread(target=_install_thread, args=(output_queue, install_id, platform_type))
        install_thread.daemon = True
        install_thread.start()

        return jsonify({
            'status': 'running',
            'tool_id': install_id, # Return the unique ID for polling
            'message': f'Tool installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Tool installation via this interface is only supported on Linux/Termux systems.',
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
    
    print(f"IP Info sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)
