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
scan_processes = {} # To keep track of running Nmap processes
scan_queues = {} # To store queues for real-time output

# Load examples from nmap_examples.txt
def load_examples(filename="nmap_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming nmap_examples.txt is in the same directory as app.py
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
    """Renders the main Nmap GUI HTML page."""
    # The examples are now loaded via a separate API call in the frontend,
    # so no need to pass them directly to render_template here.
    return render_template('index.html')

# New endpoint to serve Nmap examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the Nmap examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the Nmap command based on form data."""
    data = request.json
    command_parts = ["nmap"]

    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value)))

    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Target Tab
    if data.get('target_entry'):
        command_parts.append(shlex.quote(data['target_entry']))
    add_arg("-iL", data.get('target_list_file_entry'))
    add_arg("--exclude", data.get('exclude_hosts_entry'))
    add_arg("--excludefile", data.get('exclude_file_entry'))
    add_arg("-iR", data.get('random_hosts_entry'))
    add_checkbox_arg("-iS", data.get('stdin_input_var'))
    add_checkbox_arg("-Pn", data.get('no_ping_var'))
    add_checkbox_arg("-sP", data.get('ping_scan_var'))
    add_checkbox_arg("-sL", data.get('list_scan_var'))
    add_checkbox_arg("-n", data.get('no_dns_resolution_var'))
    add_checkbox_arg("-R", data.get('force_dns_resolution_var'))
    add_checkbox_arg("--system-dns", data.get('system_dns_var'))
    add_arg("--dns-servers", data.get('dns_servers_entry'))

    # Scan Types Tab
    add_checkbox_arg("-sS", data.get('syn_scan_var'))
    add_checkbox_arg("-sT", data.get('connect_scan_var'))
    add_checkbox_arg("-sU", data.get('udp_scan_var'))
    add_checkbox_arg("-sA", data.get('ack_scan_var'))
    add_checkbox_arg("-sW", data.get('window_scan_var'))
    add_checkbox_arg("-sM", data.get('maimon_scan_var'))
    add_checkbox_arg("-sF", data.get('fin_scan_var'))
    add_checkbox_arg("-sX", data.get('xmas_scan_var'))
    add_checkbox_arg("-sN", data.get('null_scan_var'))
    add_checkbox_arg("-sO", data.get('ip_protocol_scan_var'))
    add_checkbox_arg("-F", data.get('fast_scan_var'))
    add_checkbox_arg("-f", data.get('fragment_packets_var'))
    add_checkbox_arg("--noreason", data.get('no_reason_var'))
    add_checkbox_arg("-6", data.get('ipv6_scan_var'))
    add_checkbox_arg("--append-output", data.get('append_output_var'))
    add_checkbox_arg("-Pn", data.get('disable_host_discovery_var')) # This is redundant with target tab's -Pn, but kept for clarity
    add_checkbox_arg("-p", data.get('only_specified_ports_var'))
    add_arg("-PS", data.get('syn_ack_discovery_entry'))
    add_arg("-PU", data.get('udp_discovery_entry'))
    add_checkbox_arg("-sY", data.get('sctp_init_scan_var'))
    add_checkbox_arg("-sZ", data.get('sctp_cookie_echo_scan_var'))
    add_arg("-sI", data.get('idle_scan_entry'))
    add_checkbox_arg("-sO", data.get('protocol_scan_var'))
    add_arg("-D", data.get('decoy_scan_entry'))
    add_arg("--spoof-mac", data.get('spoof_mac_entry'))
    add_arg("--source-port", data.get('source_port_entry'))
    add_arg("--data-length", data.get('data_length_entry'))
    add_checkbox_arg("--badsum", data.get('bad_checksum_var'))

    # Port Specification Tab
    add_arg("-p", data.get('ports_entry'))
    add_arg("--exclude-ports", data.get('exclude_ports_entry'))
    add_checkbox_arg("-F", data.get('fast_scan_ports_var'))
    add_checkbox_arg("-p-", data.get('all_ports_var'))
    add_arg("--top-ports", data.get('top_ports_entry'))
    add_arg("--port-ratio", data.get('port_ratio_entry'))
    add_checkbox_arg("-sV", data.get('service_version_detection_var'))

    # Timing/Performance Tab
    add_arg("-T", data.get('timing_template_var'))
    add_arg("--min-hostgroup", data.get('min_hostgroup_entry'))
    add_arg("--max-hostgroup", data.get('max_hostgroup_entry'))
    add_arg("--min-parallelism", data.get('min_parallelism_entry'))
    add_arg("--max-parallelism", data.get('max_parallelism_entry'))
    add_arg("--min-rtt-timeout", data.get('min_rtt_timeout_entry'))
    add_arg("--max-rtt-timeout", data.get('max_rtt_timeout_entry'))
    add_arg("--initial-rtt-timeout", data.get('initial_rtt_timeout_entry'))
    add_arg("--max-retries", data.get('max_retries_entry'))
    add_arg("--host-timeout", data.get('host_timeout_entry'))
    add_arg("--scan-delay", data.get('scan_delay_entry'))
    add_arg("--min-rate", data.get('min_rate_entry'))
    add_arg("--max-rate", data.get('max_rate_entry'))

    # Detection Tab
    add_checkbox_arg("-O", data.get('os_detection_var'))
    add_checkbox_arg("-sV", data.get('service_version_detection_det_var'))
    add_checkbox_arg("-A", data.get('aggressive_detection_var'))
    add_arg("--version-intensity", data.get('version_intensity_entry'))
    add_checkbox_arg("--version-light", data.get('version_light_var'))
    add_checkbox_arg("--version-all", data.get('version_all_var'))
    add_checkbox_arg("--osscan-guess", data.get('osscan_guess_var'))
    add_checkbox_arg("--osscan-limit", data.get('osscan_limit_var'))
    add_checkbox_arg("--all-ports", data.get('all_ports_service_var'))

    # Evasion/Spoofing Tab
    add_checkbox_arg("-f", data.get('fragment_packets_evasion_var'))
    add_arg("--mtu", data.get('mtu_entry'))
    add_arg("-D", data.get('decoy_scan_evasion_entry'))
    add_arg("-sI", data.get('idle_scan_evasion_entry'))
    add_arg("--spoof-mac", data.get('spoof_mac_evasion_entry'))
    add_arg("--source-port", data.get('source_port_evasion_entry'))
    add_arg("--data-length", data.get('data_length_evasion_entry'))
    add_checkbox_arg("--badsum", data.get('bad_checksum_evasion_var'))
    add_checkbox_arg("--randomize-hosts", data.get('randomize_hosts_var'))
    add_checkbox_arg("--randomize-ports", data.get('randomize_ports_var'))
    add_arg("--ip-options", data.get('ip_options_entry'))
    add_arg("--ttl", data.get('ttl_entry'))
    add_arg("--data-string", data.get('data_string_entry'))
    add_arg("--data-binary", data.get('data_binary_entry'))
    add_arg("--scan-flags", data.get('scan_flags_entry'))

    # Output Tab
    add_arg("-oN", data.get('normal_output_file_entry'))
    add_arg("-oX", data.get('xml_output_file_entry'))
    add_arg("-oG", data.get('grepable_output_file_entry'))
    add_arg("-oA", data.get('all_formats_output_file_entry'))
    add_checkbox_arg("-v", data.get('verbose_var'))
    add_checkbox_arg("-d", data.get('debug_var'))
    add_checkbox_arg("--reason", data.get('reason_var'))
    add_checkbox_arg("--open", data.get('open_ports_only_var'))
    add_checkbox_arg("--packet-trace", data.get('packet_trace_var'))
    add_arg("--resume", data.get('resume_file_entry'))
    add_checkbox_arg("--append-output", data.get('append_output_output_var'))
    add_checkbox_arg("--no-host-discovery", data.get('no_host_discovery_var'))
    add_checkbox_arg("--version", data.get('show_version_var'))
    add_checkbox_arg("-h", data.get('show_help_var'))

    # Scripting Tab
    add_checkbox_arg("-sC", data.get('script_scan_var'))
    add_arg("--script", data.get('scripts_entry'))
    script_args = data.get('script_args_entry', '').strip()
    if script_args:
        for arg_line in script_args.split('\n'):
            arg_line = arg_line.strip()
            if arg_line:
                command_parts.append("--script-args")
                command_parts.append(shlex.quote(arg_line))
    add_arg("--script-timeout", data.get('script_timeout_entry'))
    add_checkbox_arg("--script-trace", data.get('script_trace_var'))
    add_checkbox_arg("--script-debug", data.get('script_debug_var'))
    add_arg("--script-help", data.get('script_help_entry'))
    add_checkbox_arg("--script-updatedb", data.get('script_update_db_var'))
    add_checkbox_arg("--script-fags", data.get('script_fags_var'))

    # Advanced Tab
    add_arg("-e", data.get('interface_entry'))
    add_arg("-S", data.get('source_address_entry'))
    add_arg("--data-length", data.get('payload_length_entry'))
    add_arg("--max-parallelism", data.get('max_parallelism_adv_entry'))
    add_arg("--min-parallelism", data.get('min_parallelism_adv_entry'))
    add_checkbox_arg("--packet-trace", data.get('packet_trace_adv_var'))
    add_checkbox_arg("--badsum", data.get('badsum_adv_var'))
    add_checkbox_arg("-f", data.get('fragment_packets_adv_var'))
    add_arg("--ip-options", data.get('ip_options_adv_entry'))
    add_arg("--ttl", data.get('ttl_adv_entry'))
    add_arg("--max-retries", data.get('max_retries_adv_entry'))
    add_arg("--host-timeout", data.get('host_timeout_adv_entry'))
    add_arg("--scan-delay", data.get('scan_delay_adv_entry'))
    
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

@app.route('/run_nmap', methods=['POST'])
def run_nmap():
    """
    Executes the Nmap command received from the frontend.
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

    # Ensure nmap is the command being run
    if command[0] != 'nmap':
        return jsonify({'status': 'error', 'message': 'Only Nmap commands are allowed.'}), 403

    # Check if nmap executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"Nmap executable '{command[0]}' not found on the server. Please ensure Nmap is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this scan's real-time output
    output_queue = queue.Queue()
    scan_queues[scan_id] = output_queue
    scan_outputs[scan_id] = "" # Initialize full output storage

    def _run_nmap_thread(cmd, q, scan_id_val):
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

            final_status_line = f"\nNmap finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            scan_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure Nmap is installed and in your system's PATH.\nSTATUS: Error\n"
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


    # Start the Nmap process in a separate thread
    thread = threading.Thread(target=_run_nmap_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'Nmap scan started.'})

# Modified get_scan_output to handle 'nmap_install' ID
@app.route('/get_scan_output/<scan_id>', methods=['GET'])
def get_scan_output(scan_id):
    """
    Polls for real-time Nmap scan output.
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
    filename = data.get('filename', f'nmap_output_{uuid.uuid4()}.txt')

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

@app.route('/install_nmap', methods=['POST'])
def install_nmap():
    """
    Attempts to install Nmap on the server (Linux/Termux only).
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
                    install_command = shlex.split("pkg install nmap -y")
                    q.put("Detected Termux. Using 'pkg' for installation.\n")
                elif p_type == 'linux':
                    update_command = shlex.split("sudo apt update -y")
                    install_command = shlex.split("sudo apt install nmap -y")
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

                # Then, install nmap
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
                error_msg = f"Error: Command not found ({e}). Ensure 'sudo'/'apt'/'pkg' is installed and in PATH.\n"
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
            'message': f'Nmap installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Nmap installation via this interface is only supported on Linux/Termux systems.',
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
    
    print(f"Nmap sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)
