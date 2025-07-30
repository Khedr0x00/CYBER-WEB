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
scan_processes = {} # To keep track of running ffuf processes
scan_queues = {} # To store queues for real-time output

# Load examples from ffuf_examples.txt
def load_examples(filename="ffuf_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming ffuf_examples.txt is in the same directory as app.py
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
    """Renders the main ffuf GUI HTML page."""
    return render_template('index.html')

# New endpoint to serve ffuf examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the ffuf examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the ffuf command based on form data."""
    data = request.json
    command_parts = ["ffuf"]

    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value)))

    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Target Tab
    add_arg("-u", data.get('url_entry'))
    add_arg("-request", data.get('request_file_entry'))
    add_arg("-recursion", data.get('recursion_depth_entry'))
    add_checkbox_arg("-recursion", data.get('recursion_var'))
    add_checkbox_arg("-r", data.get('follow_redirects_var'))
    add_arg("-x", data.get('proxy_entry'))
    add_arg("-timeout", data.get('timeout_entry'))
    add_arg("-rate", data.get('rate_limit_entry'))
    add_arg("-replay-proxy", data.get('replay_proxy_entry'))
    add_arg("-replay-auth", data.get('replay_auth_entry'))

    # Input Tab
    add_arg("-w", data.get('wordlist_entry'))
    add_arg("-w", data.get('wordlist_2_entry')) # For multiple wordlists
    add_arg("-request-proto", data.get('request_proto_entry'))
    add_arg("-input-file", data.get('input_file_entry'))
    add_arg("-input-mode", data.get('input_mode_select'))
    add_arg("-D", data.get('data_entry'))
    add_arg("-X", data.get('request_method_select'))
    add_arg("-H", data.get('headers_entry'))
    add_arg("-b", data.get('cookie_entry'))
    add_arg("-u", data.get('url_fuzz_entry')) # For URL fuzzing
    add_arg("-d", data.get('data_fuzz_entry')) # For data fuzzing
    add_arg("-c", data.get('config_file_entry'))
    add_checkbox_arg("-s", data.get('stop_on_all_var'))
    add_checkbox_arg("-sa", data.get('stop_on_all_codes_var'))
    add_checkbox_arg("-se", data.get('stop_on_error_var'))
    add_checkbox_arg("-sf", data.get('stop_on_filter_var'))
    add_checkbox_arg("-sfreq", data.get('stop_on_freq_var'))
    add_arg("-p", data.get('delay_entry'))
    add_arg("-t", data.get('threads_entry'))
    add_arg("-maxtime", data.get('max_time_entry'))
    add_arg("-maxtime-job", data.get('max_time_job_entry'))
    add_arg("-max-size", data.get('max_size_entry'))
    add_arg("-max-error", data.get('max_error_entry'))

    # Filtering/Matching Tab
    add_arg("-fc", data.get('filter_status_entry'))
    add_arg("-fs", data.get('filter_size_entry'))
    add_arg("-fw", data.get('filter_words_entry'))
    add_arg("-fl", data.get('filter_lines_entry'))
    add_arg("-fd", data.get('filter_duration_entry'))
    add_arg("-mc", data.get('match_status_entry'))
    add_arg("-ms", data.get('match_size_entry'))
    add_arg("-mw", data.get('match_words_entry'))
    add_arg("-ml", data.get('match_lines_entry'))
    add_arg("-md", data.get('match_duration_entry'))
    add_checkbox_arg("-acc", data.get('auto_calibrate_var'))
    add_checkbox_arg("-ac", data.get('auto_calibrate_codes_var'))
    add_checkbox_arg("-acs", data.get('auto_calibrate_size_var'))

    # Output Tab
    add_arg("-o", data.get('output_file_entry'))
    add_arg("-of", data.get('output_format_select'))
    add_checkbox_arg("-v", data.get('verbose_var'))
    add_checkbox_arg("-sa", data.get('show_all_var'))
    add_checkbox_arg("-q", data.get('quiet_var'))
    add_checkbox_arg("-c", data.get('colors_var'))
    add_checkbox_arg("-s", data.get('silent_var'))
    add_checkbox_arg("-k", data.get('insecure_var'))
    add_checkbox_arg("-r", data.get('follow_redirects_output_var')) # Redundant but kept for clarity
    add_checkbox_arg("-v", data.get('verbose_output_var')) # Redundant but kept for clarity
    add_checkbox_arg("-s", data.get('show_request_var'))
    add_checkbox_arg("-sf", data.get('show_response_var'))
    add_checkbox_arg("-hh", data.get('hide_headers_var'))
    add_checkbox_arg("-hc", data.get('hide_color_var'))
    add_checkbox_arg("-H", data.get('show_headers_var'))
    add_checkbox_arg("-i", data.get('show_input_var'))
    add_checkbox_arg("-e", data.get('show_errors_var'))
    add_checkbox_arg("-j", data.get('json_output_var'))
    add_checkbox_arg("-html", data.get('html_output_var'))
    add_checkbox_arg("-csv", data.get('csv_output_var'))
    add_checkbox_arg("-e", data.get('export_errors_var'))

    # Advanced Tab
    add_arg("-H", data.get('custom_headers_adv_entry')) # For multiple custom headers
    add_arg("-b", data.get('custom_cookies_adv_entry')) # For multiple custom cookies
    add_arg("-d", data.get('custom_data_adv_entry'))
    add_arg("-X", data.get('custom_method_adv_entry'))
    add_arg("-timeout", data.get('timeout_adv_entry'))
    add_arg("-rate", data.get('rate_limit_adv_entry'))
    add_arg("-t", data.get('threads_adv_entry'))
    add_checkbox_arg("-r", data.get('follow_redirects_adv_var'))
    add_checkbox_arg("-k", data.get('insecure_adv_var'))
    add_checkbox_arg("-s", data.get('silent_adv_var'))
    add_checkbox_arg("-c", data.get('colors_adv_var'))
    add_checkbox_arg("-v", data.get('verbose_adv_var'))
    add_arg("-maxtime", data.get('max_time_adv_entry'))
    add_arg("-maxtime-job", data.get('max_time_job_adv_entry'))
    add_arg("-max-size", data.get('max_size_adv_entry'))
    add_arg("-max-error", data.get('max_error_adv_entry'))
    add_arg("-delay", data.get('delay_adv_entry'))
    add_arg("-input-cmd", data.get('input_cmd_entry'))
    add_arg("-input-num", data.get('input_num_entry'))
    add_arg("-input-num-min", data.get('input_num_min_entry'))
    add_arg("-input-num-max", data.get('input_num_max_entry'))
    add_arg("-input-num-step", data.get('input_num_step_entry'))
    add_arg("-se", data.get('stop_on_error_adv_var'))
    add_arg("-sf", data.get('stop_on_filter_adv_var'))
    add_arg("-sfreq", data.get('stop_on_freq_adv_var'))
    add_arg("-acc", data.get('auto_calibrate_adv_var'))
    add_arg("-ac", data.get('auto_calibrate_codes_adv_var'))
    add_arg("-acs", data.get('auto_calibrate_size_adv_var'))
    add_arg("-e", data.get('data_encoding_select')) # Data encoding
    add_arg("-sa", data.get('show_all_adv_var'))
    add_arg("-q", data.get('quiet_adv_var'))
    add_arg("-ignore-body", data.get('ignore_body_var'))
    add_arg("-ignore-content-length", data.get('ignore_content_length_var'))
    add_arg("-recursion-depth", data.get('recursion_depth_adv_entry'))
    add_arg("-recursion-strategy", data.get('recursion_strategy_select'))
    add_arg("-request-proto", data.get('request_proto_adv_entry'))
    add_arg("-request-base", data.get('request_base_entry'))
    add_arg("-request-body", data.get('request_body_entry'))
    add_arg("-request-header", data.get('request_header_entry'))
    add_arg("-request-url", data.get('request_url_entry'))
    add_arg("-request-method", data.get('request_method_adv_entry'))
    add_arg("-request-data", data.get('request_data_entry'))
    add_arg("-request-cookie", data.get('request_cookie_entry'))
    add_arg("-request-proxy", data.get('request_proxy_entry'))
    add_arg("-request-timeout", data.get('request_timeout_entry'))
    add_arg("-request-delay", data.get('request_delay_entry'))
    add_arg("-request-rate", data.get('request_rate_entry'))
    add_arg("-request-threads", data.get('request_threads_entry'))
    add_arg("-request-maxtime", data.get('request_maxtime_entry'))
    add_arg("-request-maxtime-job", data.get('request_maxtime_job_entry'))
    add_arg("-request-max-size", data.get('request_max_size_entry'))
    add_arg("-request-max-error", data.get('request_max_error_entry'))
    add_arg("-request-stop-on-all", data.get('request_stop_on_all_var'))
    add_arg("-request-stop-on-all-codes", data.get('request_stop_on_all_codes_var'))
    add_arg("-request-stop-on-error", data.get('request_stop_on_error_var'))
    add_arg("-request-stop-on-filter", data.get('request_stop_on_filter_var'))
    add_arg("-request-stop-on-freq", data.get('request_stop_on_freq_var'))
    add_arg("-request-auto-calibrate", data.get('request_auto_calibrate_var'))
    add_arg("-request-auto-calibrate-codes", data.get('request_auto_calibrate_codes_var'))
    add_arg("-request-auto-calibrate-size", data.get('request_auto_calibrate_size_var'))
    add_arg("-request-show-all", data.get('request_show_all_var'))
    add_arg("-request-quiet", data.get('request_quiet_var'))
    add_arg("-request-colors", data.get('request_colors_var'))
    add_arg("-request-silent", data.get('request_silent_var'))
    add_arg("-request-insecure", data.get('request_insecure_var'))
    add_arg("-request-follow-redirects", data.get('request_follow_redirects_var'))
    add_arg("-request-verbose", data.get('request_verbose_var'))
    add_arg("-request-show-request", data.get('request_show_request_var'))
    add_arg("-request-show-response", data.get('request_show_response_var'))
    add_arg("-request-hide-headers", data.get('request_hide_headers_var'))
    add_arg("-request-hide-color", data.get('request_hide_color_var'))
    add_arg("-request-show-headers", data.get('request_show_headers_var'))
    add_arg("-request-show-input", data.get('request_show_input_var'))
    add_arg("-request-show-errors", data.get('request_show_errors_var'))
    add_arg("-request-json-output", data.get('request_json_output_var'))
    add_arg("-request-html-output", data.get('request_html_output_var'))
    add_arg("-request-csv-output", data.get('request_csv_output_var'))
    add_arg("-request-export-errors", data.get('request_export_errors_var'))
    add_arg("-request-ignore-body", data.get('request_ignore_body_var'))
    add_arg("-request-ignore-content-length", data.get('request_ignore_content_length_var'))
    add_arg("-request-recursion-depth", data.get('request_recursion_depth_var'))
    add_arg("-request-recursion-strategy", data.get('request_recursion_strategy_var'))

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

@app.route('/run_ffuf', methods=['POST'])
def run_ffuf():
    """
    Executes the ffuf command received from the frontend.
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

    # Ensure ffuf is the command being run
    if command[0] != 'ffuf':
        return jsonify({'status': 'error', 'message': 'Only ffuf commands are allowed.'}), 403

    # Check if ffuf executable exists using shutil.which
    if shutil.which(command[0]) is None:
        return jsonify({'status': 'error', 'message': f"ffuf executable '{command[0]}' not found on the server. Please ensure ffuf is installed and accessible in the system's PATH."}), 500

    # Create a new queue for this scan's real-time output
    output_queue = queue.Queue()
    scan_queues[scan_id] = output_queue
    scan_outputs[scan_id] = "" # Initialize full output storage

    def _run_ffuf_thread(cmd, q, scan_id_val):
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

            final_status_line = f"\nffuf finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            scan_outputs[scan_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure ffuf is installed and in your system's PATH.\nSTATUS: Error\n"
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


    # Start the ffuf process in a separate thread
    thread = threading.Thread(target=_run_ffuf_thread, args=(command, output_queue, scan_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'scan_id': scan_id, 'message': 'ffuf scan started.'})

@app.route('/get_scan_output/<scan_id>', methods=['GET'])
def get_scan_output(scan_id):
    """
    Polls for real-time ffuf scan output.
    Returns new lines from the queue or the final output if scan is complete.
    """
    output_queue = scan_queues.get(scan_id)
    if not output_queue:
        # If queue is not found, check if the scan completed and its final output is stored
        if scan_id in scan_outputs:
            return jsonify({'status': 'completed', 'output': scan_outputs[scan_id]})
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
        # Scan is truly complete, clean up the queue
        del scan_queues[scan_id]
        return jsonify({'status': 'completed', 'output': scan_outputs.get(scan_id, "Scan completed, but output not fully captured.")})
    else:
        # Scan is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})


@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the provided content to a file on the server and allows download."""
    data = request.json
    content = data.get('content')
    filename = data.get('filename', f'ffuf_output_{uuid.uuid4()}.txt')

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

@app.route('/install_ffuf', methods=['POST'])
def install_ffuf():
    """
    Attempts to install ffuf on the server (Linux only).
    WARNING: This endpoint executes system commands with 'sudo'.
    This is a significant security risk and should ONLY be used in a
    controlled, isolated development environment where you fully trust
    the users and the environment. In a production setting, exposing
    such functionality is highly discouraged.
    """
    platform = sys.platform
    full_output = []

    if platform.startswith('linux'):
        try:
            # Determine package manager
            package_manager = None
            if shutil.which("apt"):
                package_manager = "apt"
            elif shutil.which("pkg"): # For Termux
                package_manager = "pkg"
            
            if not package_manager:
                return jsonify({
                    'status': 'error',
                    'message': 'No supported package manager (apt or pkg) found.',
                    'output': 'Neither apt nor pkg command found.'
                }), 500

            # First, update package list
            update_command = shlex.split(f"sudo {package_manager} update -y")
            update_process = subprocess.run(
                update_command,
                capture_output=True,
                text=True,
                check=True # Raise CalledProcessError for non-zero exit codes
            )
            full_output.append(update_process.stdout)
            if update_process.stderr:
                full_output.append(update_process.stderr)

            # Then, install ffuf
            install_command = shlex.split(f"sudo {package_manager} install ffuf -y")
            install_process = subprocess.run(
                install_command,
                capture_output=True,
                text=True,
                check=True # Raise CalledProcessError for non-zero exit codes
            )
            full_output.append(install_process.stdout)
            if install_process.stderr:
                full_output.append(install_process.stderr)

            return jsonify({
                'status': 'success',
                'message': 'ffuf installed/updated successfully.',
                'output': "".join(full_output)
            })
        except subprocess.CalledProcessError as e:
            error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}\\n{e.stderr}"
            full_output.append(error_output)
            return jsonify({
                'status': 'error',
                'message': f"Failed to install ffuf. Check output for details. (Error: {e.returncode})",
                'output': "".join(full_output)
            }), 500
        except FileNotFoundError:
            return jsonify({
                'status': 'error',
                'message': "sudo, apt, or pkg command not found. Ensure they are in PATH and you have necessary permissions.",
                'output': "sudo, apt, or pkg command not found."
            }), 500
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f"An unexpected error occurred during installation: {str(e)}",
                'output': str(e)
            }), 500
    else:
        return jsonify({
            'status': 'error',
            'message': 'ffuf installation via this interface is only supported on Linux systems (Kali, Ubuntu, Termux).',
            'output': f'Operating system is {platform}.'
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
    
    print(f"ffuf sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)

