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
scan_processes = {} # To keep track of running tcpdump processes
scan_queues = {} # To store queues for real-time output

# Load examples from tcpdump_examples.txt
def load_examples(filename="tcpdump_examples.txt"):
    """Loads tcpdump examples from a JSON file."""
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
    """Renders the main tcpdump GUI HTML page."""
    return render_template('index.html')

# New endpoint to serve tcpdump examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the tcpdump examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the tcpdump command based on form data."""
    data = request.json
    command_parts = ["tcpdump"]

    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value)))

    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Basic Options Tab
    add_arg("-i", data.get('interface_entry'))
    add_checkbox_arg("-n", data.get('no_name_resolution_var'))
    add_checkbox_arg("-nn", data.get('no_port_name_resolution_var'))
    add_checkbox_arg("-v", data.get('verbose_var'))
    add_checkbox_arg("-vv", data.get('more_verbose_var'))
    add_checkbox_arg("-vvv", data.get('most_verbose_var'))
    add_checkbox_arg("-e", data.get('ethernet_header_var'))
    add_checkbox_arg("-x", data.get('hex_dump_var'))
    add_checkbox_arg("-xx", data.get('hex_dump_ether_var'))
    add_checkbox_arg("-A", data.get('ascii_dump_var'))
    add_checkbox_arg("-X", data.get('hex_ascii_dump_var'))
    add_checkbox_arg("-XX", data.get('hex_ascii_dump_ether_var'))
    add_checkbox_arg("-q", data.get('quick_output_var'))
    add_checkbox_arg("-t", data.get('no_timestamp_var'))
    add_checkbox_arg("-tt", data.get('micro_timestamp_var'))
    add_checkbox_arg("-ttt", data.get('delta_timestamp_var'))
    add_checkbox_arg("-tttt", data.get('date_timestamp_var'))
    add_checkbox_arg("-ttttt", data.get('boot_timestamp_var'))
    add_arg("-c", data.get('packet_count_entry'))
    add_checkbox_arg("-l", data.get('line_buffered_var'))
    add_checkbox_arg("-p", data.get('no_promiscuous_var'))
    add_checkbox_arg("-L", data.get('list_interfaces_var'))

    # Filtering Tab
    # Host filter
    host_type = data.get('host_type_select')
    host_value = data.get('host_value_entry')
    if host_value:
        if host_type == 'src':
            command_parts.append("src")
        elif host_type == 'dst':
            command_parts.append("dst")
        command_parts.append("host")
        command_parts.append(shlex.quote(host_value))

    # Port filter
    port_type = data.get('port_type_select')
    port_value = data.get('port_value_entry')
    if port_value:
        if port_type == 'src':
            command_parts.append("src")
        elif port_type == 'dst':
            command_parts.append("dst")
        command_parts.append("port")
        command_parts.append(shlex.quote(port_value))

    # Protocol filter
    protocol_value = data.get('protocol_select')
    if protocol_value:
        command_parts.append(shlex.quote(protocol_value))
    
    # Network filter
    net_type = data.get('net_type_select')
    net_value = data.get('net_value_entry')
    if net_value:
        if net_type == 'src':
            command_parts.append("src")
        elif net_type == 'dst':
            command_parts.append("dst")
        command_parts.append("net")
        command_parts.append(shlex.quote(net_value))

    # Other common filters
    add_checkbox_arg("arp", data.get('arp_var'))
    add_checkbox_arg("icmp", data.get('icmp_var'))
    add_checkbox_arg("tcp", data.get('tcp_var'))
    add_checkbox_arg("udp", data.get('udp_var'))
    add_checkbox_arg("ip", data.get('ip_var'))
    add_checkbox_arg("vlan", data.get('vlan_var'))
    add_checkbox_arg("broadcast", data.get('broadcast_var'))
    add_checkbox_arg("multicast", data.get('multicast_var'))
    add_checkbox_arg("gateway", data.get('gateway_var'))
    
    # Expression
    expression = data.get('expression_entry')
    if expression:
        command_parts.append(shlex.quote(expression))

    # File Operations Tab
    add_arg("-r", data.get('read_file_entry'))
    add_arg("-w", data.get('write_file_entry'))
    add_arg("-C", data.get('file_size_rotate_entry'))
    add_arg("-W", data.get('file_count_rotate_entry'))
    add_checkbox_arg("-G", data.get('rotate_time_var'))
    add_arg("-G", data.get('rotate_time_entry')) # This will add -G again if rotate_time_var is false but entry has value
    add_checkbox_arg("-K", data.get('dont_checksum_var'))
    add_checkbox_arg("-E", data.get('decrypt_ipsec_var'))
    add_arg("-z", data.get('compress_file_entry'))

    # Advanced Options Tab
    add_arg("-s", data.get('snaplen_entry'))
    add_arg("-B", data.get('buffer_size_entry'))
    add_checkbox_arg("-P", data.get('promiscuous_var'))
    add_checkbox_arg("-F", data.get('filter_file_var'))
    add_arg("-F", data.get('filter_file_entry')) # This will add -F again if filter_file_var is false but entry has value
    add_checkbox_arg("-y", data.get('data_link_type_var'))
    add_arg("-y", data.get('data_link_type_entry')) # This will add -y again if data_link_type_var is false but entry has value
    add_checkbox_arg("-D", data.get('list_interfaces_adv_var')) # Redundant with -L but kept for clarity
    add_checkbox_arg("--time-stamp-precision", data.get('timestamp_precision_var'))
    add_arg("--time-stamp-precision", data.get('timestamp_precision_entry')) # This will add --time-stamp-precision again if timestamp_precision_var is false but entry has value


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

@app.route('/run_tcpdump', methods=['POST'])
def run_tcpdump():
    """
    Executes the tcpdump command received from the frontend.
    IMPORTANT: Running arbitrary commands from user input on a web server is a severe security risk.
    This implementation is for demonstration and should NOT be used in a production environment
    without extensive security measures, input validation, and sandboxing.
    tcpdump often requires root privileges. The command will be prefixed with 'sudo' if available.
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

    # Ensure tcpdump is the command being run
    if command[0] != 'tcpdump':
        return jsonify({'status': 'error', 'message': 'Only tcpdump commands are allowed.'}), 403

    # Check if tcpdump executable exists. Add sudo if needed and available.
    tcpdump_path = shutil.which(command[0])
    if tcpdump_path is None:
        return jsonify({'status': 'error', 'message': f"tcpdump executable '{command[0]}' not found on the server. Please ensure tcpdump is installed and accessible in the system's PATH."}), 500
    
    # Check if sudo is available and prepend if tcpdump is not directly executable by current user
    # This is a heuristic and might not be perfect for all setups.
    if os.geteuid() != 0 and shutil.which('sudo'): # Check if not root and sudo exists
        # Check if tcpdump requires root (e.g., cannot open device)
        # A more robust check would involve trying to run a simple tcpdump command
        # and checking for permission errors, but that adds complexity.
        # For simplicity, we'll assume if not root, sudo might be needed.
        command.insert(0, 'sudo')
        print(f"Prepending 'sudo' to tcpdump command: {' '.join(command)}")


    # Create a new queue for this scan's real-time output
    output_queue = queue.Queue()
    scan_queues[scan_id] = output_queue
    scan_outputs[scan_id] = "" # Initialize full output storage

    def _run_tcpdump_thread(cmd, q, scan_id_val):
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

            final_status_line = f"\ntcpdump finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            scan_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure tcpdump is installed and in your system's PATH.\nSTATUS: Error\n"
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


    # Start the tcpdump process in a separate thread
    thread = threading.Thread(target=_run_tcpdump_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'tcpdump capture started.'})

# Modified get_scan_output to handle 'tcpdump_install' ID
@app.route('/get_scan_output/<scan_id>', methods=['GET'])
def get_scan_output(scan_id):
    """
    Polls for real-time tcpdump scan output.
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
    filename = data.get('filename', f'tcpdump_output_{uuid.uuid4()}.txt')

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

@app.route('/install_tcpdump', methods=['POST'])
def install_tcpdump():
    """
    Attempts to install tcpdump on the server (Linux/Termux only).
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
                if p_type == 'termux':
                    update_command = shlex.split("pkg update -y")
                    install_command = shlex.split("pkg install tcpdump -y")
                    q.put("Detected Termux. Using 'pkg' for installation.\n")
                elif p_type == 'linux':
                    # Check for apt, then yum, then dnf
                    if shutil.which('apt'):
                        update_command = shlex.split("sudo apt update -y")
                        install_command = shlex.split("sudo apt install tcpdump -y")
                        q.put("Detected Linux (apt). Using 'sudo apt' for installation.\n")
                    elif shutil.which('yum'):
                        update_command = shlex.split("sudo yum check-update -y") # yum update is interactive
                        install_command = shlex.split("sudo yum install tcpdump -y")
                        q.put("Detected Linux (yum). Using 'sudo yum' for installation.\n")
                    elif shutil.which('dnf'):
                        update_command = shlex.split("sudo dnf check-update -y") # dnf update is interactive
                        install_command = shlex.split("sudo dnf install tcpdump -y")
                        q.put("Detected Linux (dnf). Using 'sudo dnf' for installation.\n")
                    else:
                        q.put("Error: No supported package manager (apt, yum, dnf) found on Linux.\n")
                        q.put("---INSTALL_COMPLETE_FAILURE---")
                        return
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
                    # Don't raise, try install anyway, sometimes update fails but install works
                    # raise subprocess.CalledProcessError(update_process.returncode, update_command, "".join(temp_buffer_thread), "")

                # Then, install tcpdump
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
                scan_outputs[current_scan_id] = "".join(temp_buffer_thread)

            except subprocess.CalledProcessError as e:
                error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}"
                q.put(error_output)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                scan_outputs[current_scan_id] = "".join(temp_buffer_thread) + error_output
            except FileNotFoundError as e:
                error_msg = f"Error: Command not found ({e}). Ensure 'sudo'/'apt'/'pkg'/'yum'/'dnf' is installed and in PATH.\n"
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
            'message': f'tcpdump installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'tcpdump installation via this interface is only supported on Linux/Termux systems.',
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
    
    print(f"tcpdump sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)
