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
import re # For parsing Ngrok output

app = Flask(__name__)

# Directory to store temporary files (e.g., uploaded target lists, scan outputs)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# In-memory storage for tunnel outputs and processes
tunnel_outputs = {}
tunnel_processes = {} # To keep track of running Ngrok processes
tunnel_queues = {} # To store queues for real-time output

# Path to Ngrok executable (will be determined at runtime or assume in PATH)
NGROK_EXECUTABLE = shutil.which("ngrok")

# Load examples from ngrok_examples.txt
def load_examples(filename="ngrok_examples.txt"):
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
    """Renders the main Ngrok GUI HTML page."""
    return render_template('index.html')

# New endpoint to serve Ngrok examples
@app.route('/get_examples', methods=['GET'])
def get_examples():
    """Returns the Ngrok examples as JSON."""
    return jsonify(ALL_EXAMPLES)

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the Ngrok command based on form data."""
    data = request.json
    command_parts = ["ngrok"]

    # Determine base command type
    command_type = data.get('command_type_select', 'http') # 'http', 'tcp', 'tunnel'

    if command_type == 'authtoken':
        authtoken = data.get('authtoken_entry')
        if authtoken:
            command_parts.extend(["authtoken", shlex.quote(authtoken)])
        else:
            command_parts.append("authtoken <YOUR_AUTH_TOKEN>")
        return jsonify({'command': " ".join(command_parts)})

    elif command_type == 'http':
        command_parts.append("http")
        # HTTP specific options
        if data.get('http_port_entry'):
            command_parts.append(shlex.quote(data['http_port_entry']))
        
        if data.get('http_host_header_entry'):
            command_parts.extend(["--host-header", shlex.quote(data['http_host_header_entry'])])
        if data.get('http_hostname_entry'):
            command_parts.extend(["--hostname", shlex.quote(data['http_hostname_entry'])])
        if data.get('http_auth_entry'):
            command_parts.extend(["--auth", shlex.quote(data['http_auth_entry'])])
        if data.get('http_domain_entry'):
            command_parts.extend(["--domain", shlex.quote(data['http_domain_entry'])])
        if data.get('http_subdomain_entry'):
            command_parts.extend(["--subdomain", shlex.quote(data['http_subdomain_entry'])])
        if data.get('http_oauth_provider_select'):
            command_parts.extend(["--oauth", shlex.quote(data['http_oauth_provider_select'])])
        if data.get('http_oauth_allow_emails_entry'):
            command_parts.extend(["--oauth-allow-emails", shlex.quote(data['http_oauth_allow_emails_entry'])])
        if data.get('http_oauth_allow_domains_entry'):
            command_parts.extend(["--oauth-allow-domains", shlex.quote(data['http_oauth_allow_domains_entry'])])
        if data.get('http_schemes_select'):
            command_parts.extend(["--schemes", shlex.quote(data['http_schemes_select'])])
        if data.get('http_mutual_tls_var'):
            command_parts.append("--mutual-tls")
        if data.get('http_basic_auth_entry'):
            command_parts.extend(["--basic-auth", shlex.quote(data['http_basic_auth_entry'])])
        if data.get('http_compression_var'):
            command_parts.append("--compression")

    elif command_type == 'tcp':
        command_parts.append("tcp")
        # TCP specific options
        if data.get('tcp_port_entry'):
            command_parts.append(shlex.quote(data['tcp_port_entry']))
        
        if data.get('tcp_remote_addr_entry'):
            command_parts.extend(["--remote-addr", shlex.quote(data['tcp_remote_addr_entry'])])
        if data.get('tcp_host_header_entry_tcp'):
            command_parts.extend(["--host-header", shlex.quote(data['tcp_host_header_entry_tcp'])])
        if data.get('tcp_auth_entry_tcp'):
            command_parts.extend(["--auth", shlex.quote(data['tcp_auth_entry_tcp'])])

    elif command_type == 'tunnel':
        command_parts.append("tunnel")
        # Tunnel specific options (named tunnels)
        if data.get('tunnel_name_entry'):
            command_parts.append(shlex.quote(data['tunnel_name_entry']))
        else:
            command_parts.append("<TUNNEL_NAME>") # Placeholder if not provided

    # Common options (apply to HTTP/TCP/Tunnel)
    if data.get('region_select'):
        command_parts.extend(["--region", shlex.quote(data['region_select'])])
    if data.get('config_file_entry'):
        command_parts.extend(["--config", shlex.quote(data['config_file_entry'])])
    if data.get('log_file_entry'):
        command_parts.extend(["--log", shlex.quote(data['log_file_entry'])])
    if data.get('log_level_select'):
        command_parts.extend(["--log-level", shlex.quote(data['log_level_select'])])
    if data.get('metadata_entry'):
        command_parts.extend(["--metadata", shlex.quote(data['metadata_entry'])])
    if data.get('proxy_url_entry'):
        command_parts.extend(["--proxy-url", shlex.quote(data['proxy_url_entry'])])
    if data.get('inspect_var'):
        command_parts.append("--inspect")
    if data.get('debug_var'):
        command_parts.append("--debug")
    if data.get('log_format_select'):
        command_parts.extend(["--log-format", shlex.quote(data['log_format_select'])])
    if data.get('hostname_entry_common'):
        command_parts.extend(["--hostname", shlex.quote(data['hostname_entry_common'])])
    if data.get('domain_entry_common'):
        command_parts.extend(["--domain", shlex.quote(data['domain_entry_common'])])
    if data.get('subdomain_entry_common'):
        command_parts.extend(["--subdomain", shlex.quote(data['subdomain_entry_common'])])
    if data.get('auth_entry_common'):
        command_parts.extend(["--auth", shlex.quote(data['auth_entry_common'])])
    if data.get('scheme_select_common'):
        command_parts.extend(["--schemes", shlex.quote(data['scheme_select_common'])])
    if data.get('oauth_provider_select_common'):
        command_parts.extend(["--oauth", shlex.quote(data['oauth_provider_select_common'])])
    if data.get('oauth_allow_emails_entry_common'):
        command_parts.extend(["--oauth-allow-emails", shlex.quote(data['oauth_allow_emails_entry_common'])])
    if data.get('oauth_allow_domains_entry_common'):
        command_parts.extend(["--oauth-allow-domains", shlex.quote(data['oauth_allow_domains_entry_common'])])
    if data.get('mutual_tls_var_common'):
        command_parts.append("--mutual-tls")
    if data.get('basic_auth_entry_common'):
        command_parts.extend(["--basic-auth", shlex.quote(data['basic_auth_entry_common'])])
    if data.get('compression_var_common'):
        command_parts.append("--compression")

    additional_args = data.get('additional_args_entry', '').strip()
    if additional_args:
        try:
            split_args = shlex.split(additional_args)
            command_parts.extend(split_args)
        except ValueError:
            command_parts.append(shlex.quote(additional_args))

    generated_cmd = " ".join(command_parts)
    return jsonify({'command': generated_cmd})

@app.route('/run_ngrok', methods=['POST'])
def run_ngrok():
    """
    Executes the Ngrok command received from the frontend.
    IMPORTANT: Running arbitrary commands from user input on a web server is a severe security risk.
    This implementation is for demonstration and should NOT be used in a production environment
    without extensive security measures, input validation, and sandboxing.
    """
    data = request.json
    command_str = data.get('command')
    tunnel_id = str(uuid.uuid4()) # Unique ID for this tunnel session

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

    # Ensure ngrok is the command being run
    if command[0] != 'ngrok':
        return jsonify({'status': 'error', 'message': 'Only Ngrok commands are allowed.'}), 403

    # Check if ngrok executable exists
    global NGROK_EXECUTABLE
    if NGROK_EXECUTABLE is None:
        NGROK_EXECUTABLE = shutil.which("ngrok")
    
    if NGROK_EXECUTABLE is None:
        return jsonify({'status': 'error', 'message': "Ngrok executable 'ngrok' not found on the server. Please ensure Ngrok is installed and accessible in the system's PATH."}), 500

    # Replace 'ngrok' with the full path if found
    command[0] = NGROK_EXECUTABLE

    # Create a new queue for this tunnel's real-time output
    output_queue = queue.Queue()
    tunnel_queues[tunnel_id] = output_queue
    tunnel_outputs[tunnel_id] = "" # Initialize full output storage

    def _run_ngrok_thread(cmd, q, tunnel_id_val):
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
            tunnel_processes[tunnel_id_val] = process

            for line in iter(process.stdout.readline, ''):
                q.put(line) # Put each line into the queue
                full_output_buffer.append(line) # Also append to buffer for final output

            process.wait()
            return_code = process.returncode

            final_status_line = f"\nNgrok process finished with exit code: {return_code}\n"
            final_status_line += f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n"
            q.put(final_status_line) # Add final status to queue

            full_output_buffer.append(final_status_line)
            tunnel_outputs[tunnel_id_val] = "".join(full_output_buffer) # Store complete output

        except FileNotFoundError:
            error_msg = f"Error: '{cmd[0]}' command not found. Make sure Ngrok is installed and in your system's PATH.\nSTATUS: Error\n"
            q.put(error_msg)
            tunnel_outputs[tunnel_id_val] = error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}\nSTATUS: Error\n"
            q.put(error_msg)
            tunnel_outputs[tunnel_id_val] = error_msg
        finally:
            if tunnel_id_val in tunnel_processes:
                del tunnel_processes[tunnel_id_val]
            # Signal end of output by putting a special marker
            q.put("---TUNNEL_COMPLETE---")


    # Start the Ngrok process in a separate thread
    thread = threading.Thread(target=_run_ngrok_thread, args=(command, output_queue, tunnel_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'running', 'tunnel_id': tunnel_id, 'message': 'Ngrok tunnel started.'})

@app.route('/stop_ngrok/<tunnel_id>', methods=['POST'])
def stop_ngrok(tunnel_id):
    """Stops a running Ngrok tunnel process."""
    process = tunnel_processes.get(tunnel_id)
    if process:
        try:
            # Attempt graceful termination first
            process.terminate()
            process.wait(timeout=5) # Wait for process to terminate

            if process.poll() is None: # If still running after terminate, force kill
                process.kill()
                process.wait(timeout=5)
            
            # Clean up associated queue and output
            if tunnel_id in tunnel_queues:
                # Put a message into the queue to indicate termination
                tunnel_queues[tunnel_id].put("\n---TUNNEL_STOPPED_BY_USER---\n")
                tunnel_queues[tunnel_id].put("---TUNNEL_COMPLETE---") # Signal completion
            
            # Ensure final output is stored if the process was terminated before natural completion
            if tunnel_id not in tunnel_outputs:
                 tunnel_outputs[tunnel_id] = "Tunnel stopped by user.\n"

            return jsonify({'status': 'success', 'message': 'Ngrok tunnel stopped.'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Failed to stop tunnel: {e}'}), 500
    else:
        return jsonify({'status': 'not_found', 'message': 'Tunnel ID not found or already stopped.'}), 404

@app.route('/get_tunnel_output/<tunnel_id>', methods=['GET'])
def get_tunnel_output(tunnel_id):
    """
    Polls for real-time Ngrok tunnel output.
    Returns new lines from the queue or the final output if tunnel is complete.
    """
    output_queue = tunnel_queues.get(tunnel_id)
    if not output_queue:
        # If queue is not found, check if the tunnel completed and its final output is stored
        final_output = tunnel_outputs.get(tunnel_id)
        if final_output:
            return jsonify({'status': 'completed', 'output': final_output})
        return jsonify({'status': 'not_found', 'message': 'Tunnel ID not found or expired.'}), 404

    new_output_lines = []
    tunnel_finished = False

    try:
        while True:
            # Get items from queue without blocking
            line = output_queue.get_nowait()
            if line == "---TUNNEL_COMPLETE---":
                tunnel_finished = True
                break
            new_output_lines.append(line)
    except queue.Empty:
        pass # No more lines in queue for now

    current_output_segment = "".join(new_output_lines)

    if tunnel_finished:
        # Tunnel is truly complete, clean up the queue
        del tunnel_queues[tunnel_id]
        status_to_return = 'completed'
        
        # Ensure the final output includes all accumulated output
        final_output_content = tunnel_outputs.get(tunnel_id, "Tunnel completed, but output not fully captured.")
        return jsonify({'status': status_to_return, 'output': final_output_content})
    else:
        # Tunnel is still running, return partial output
        return jsonify({'status': 'running', 'output': current_output_segment})

@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the provided content to a file on the server and allows download."""
    data = request.json
    content = data.get('content')
    filename = data.get('filename', f'ngrok_output_{uuid.uuid4()}.txt')

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

@app.route('/install_ngrok', methods=['POST'])
def install_ngrok():
    """
    Attempts to install Ngrok on the server (Linux/Termux only) or provides Windows download link.
    WARNING: This endpoint executes system commands with 'sudo'.
    This is a significant security risk and should ONLY be used in a
    controlled, isolated development environment where you fully trust
    the users and the environment. In a production setting, exposing
    such functionality is highly discouraged.
    """
    data = request.json
    platform_type = data.get('platform') # 'linux', 'termux', 'windows'

    if platform_type == 'windows':
        return jsonify({
            'status': 'info',
            'message': 'For Windows, please download Ngrok manually from https://ngrok.com/download',
            'output': 'Ngrok installation via this interface is not supported on Windows. Please download manually.'
        }), 200

    # Check if running on Linux or Termux (sys.platform for Termux is 'linux')
    if sys.platform.startswith('linux'):
        install_id = str(uuid.uuid4()) # Unique ID for this installation process
        output_queue = queue.Queue()
        tunnel_queues[install_id] = output_queue
        tunnel_outputs[install_id] = "" # Initialize full output storage for this ID

        def _install_thread(q, current_install_id, p_type):
            temp_buffer_thread = [] # Local buffer for the thread
            try:
                if p_type == 'termux':
                    update_command = shlex.split("pkg update -y")
                    install_command = shlex.split("pkg install ngrok -y")
                    q.put("Detected Termux. Using 'pkg' for installation.\n")
                elif p_type == 'linux':
                    # For Linux, Ngrok typically needs to be downloaded and unzipped
                    # This is a simplified example. A real installer might fetch from ngrok.com
                    # and place it in /usr/local/bin or similar.
                    # For now, we'll just check if it's already in PATH or provide instructions.
                    if shutil.which("ngrok"):
                        q.put("Ngrok already found in system PATH. No installation needed.\n")
                        q.put("---INSTALL_COMPLETE_SUCCESS---")
                        tunnel_outputs[current_install_id] = "".join(temp_buffer_thread) + "Ngrok already found in system PATH. No installation needed."
                        return
                    
                    # Provide instructions for manual installation on Linux
                    instructions = """
                    Ngrok is not typically installed via apt/pkg on Linux directly.
                    Please follow these steps to install Ngrok:

                    1.  <a href="https://ngrok.com/download" target="_blank" class="text-blue-400 hover:underline">Download Ngrok</a> for your Linux architecture.
                    2.  Unzip the downloaded file: `unzip /path/to/ngrok.zip`
                    3.  Move the ngrok executable to a directory in your PATH (e.g., /usr/local/bin):
                        `sudo mv ngrok /usr/local/bin/`
                    4.  Make it executable: `sudo chmod +x /usr/local/bin/ngrok`
                    5.  Set your authtoken (replace YOUR_AUTH_TOKEN):
                        `ngrok authtoken YOUR_AUTH_TOKEN`
                    """
                    q.put(f"Installation instructions for Linux:\n{instructions}\n")
                    q.put("---INSTALL_COMPLETE_INFO---") # Special status for info message
                    tunnel_outputs[current_install_id] = "".join(temp_buffer_thread) + instructions
                    return
                else:
                    q.put("Error: Unsupported platform type for installation.\n")
                    q.put("---INSTALL_COMPLETE_FAILURE---")
                    return

                # Execute update command (Termux specific)
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

                # Execute install command (Termux specific)
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
                tunnel_outputs[current_install_id] = "".join(temp_buffer_thread)

            except subprocess.CalledProcessError as e:
                error_output = f"Command failed with exit code {e.returncode}:\n{e.stdout}"
                q.put(error_output)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                tunnel_outputs[current_install_id] = "".join(temp_buffer_thread) + error_output
            except FileNotFoundError as e:
                error_msg = f"Error: Command not found ({e}). Ensure 'sudo'/'apt'/'pkg' is installed and in PATH.\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                tunnel_outputs[current_install_id] = "".join(temp_buffer_thread) + error_msg
            except Exception as e:
                error_msg = f"An unexpected error occurred during installation: {str(e)}\n"
                q.put(error_msg)
                q.put("---INSTALL_COMPLETE_FAILURE---")
                tunnel_outputs[current_install_id] = "".join(temp_buffer_thread) + error_msg

        # Start the installation in a separate thread
        install_thread = threading.Thread(target=_install_thread, args=(output_queue, install_id, platform_type))
        install_thread.daemon = True
        install_thread.start()

        return jsonify({
            'status': 'running',
            'install_id': install_id, # Return the unique ID for polling
            'message': f'Ngrok installation for {platform_type} started. Polling for output...'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Ngrok installation via this interface is only automatically supported on Linux/Termux systems. For Windows, please use the download link.',
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
    
    print(f"Ngrok sub-app is starting on port {port}...") # Added for clarity in logs
    app.run(debug=True, host='0.0.0.0', port=port)
