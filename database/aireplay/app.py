import os
import sys
import subprocess
import threading
import queue
import shlex
import time
import argparse
from flask import Flask, request, jsonify, render_template, Response

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) # Generate a random secret key for session management

# Global variables for managing the aireplay-ng process and its output
aireplay_process = None
output_queue = queue.Queue() # Queue to hold real-time output from aireplay-ng
process_running_lock = threading.Lock() # Lock to ensure thread-safe access to aireplay_process

# Define paths for saving logs and generated commands
# These paths are relative to the app.py location
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
AIREPLAY_LOG_FILE = os.path.join(LOG_DIR, 'aireplay_output.log')
GENERATED_COMMAND_FILE = os.path.join(LOG_DIR, 'generated_command.txt')

# --- Helper Functions ---

def generate_aireplay_command_parts(form_data):
    """
    Generates the aireplay-ng command parts based on form data.
    This logic is adapted from the original gui.py's generate_command method.
    """
    command_parts = ["aireplay-ng"]

    # Helper to add arguments if value is not empty
    def add_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)
            command_parts.append(shlex.quote(str(value))) # Quote values to handle spaces

    # Helper to add checkbox arguments
    def add_checkbox_arg(arg_name, value):
        if value:
            command_parts.append(arg_name)

    # Attack Modes (mutually exclusive, prioritize based on user input)
    # Deauthentication (-0)
    deauth_count = form_data.get('deauth_count_entry', '').strip()
    fake_auth_delay = form_data.get('fake_auth_delay_entry', '').strip()
    arp_replay = form_data.get('arp_replay_var') == 'true'
    chopchop = form_data.get('chopchop_var') == 'true'
    fragmentation = form_data.get('fragmentation_var') == 'true'
    caffe_latte = form_data.get('caffe_latte_var') == 'true'
    p0841 = form_data.get('p0841_var') == 'true'
    hirte = form_data.get('hirte_var') == 'true'
    handshake_capture = form_data.get('handshake_capture_var') == 'true'
    arp_request_replay = form_data.get('arp_request_replay_entry', '').strip()
    replay_file = form_data.get('replay_file_entry', '').strip()

    if deauth_count:
        command_parts.extend(["-0", shlex.quote(deauth_count)])
    elif fake_auth_delay:
        command_parts.extend(["-1", shlex.quote(fake_auth_delay)])
    elif arp_replay:
        command_parts.append("-3")
    elif chopchop:
        command_parts.append("-4")
    elif fragmentation:
        command_parts.append("-5")
    elif caffe_latte:
        command_parts.append("-6")
    elif p0841:
        command_parts.append("-7")
    elif hirte:
        command_parts.append("-8")
    elif handshake_capture:
        command_parts.append("-9")
    elif arp_request_replay:
        command_parts.extend(["-k", shlex.quote(arp_request_replay)])
    elif replay_file:
        command_parts.extend(["-r", shlex.quote(replay_file)])

    # Target/Interface Tab
    add_arg("-b", form_data.get('bssid_entry', ''))
    add_arg("-c", form_data.get('client_mac_entry', ''))
    add_arg("-e", form_data.get('essid_entry', ''))
    add_arg("--channel", form_data.get('channel_entry', ''))

    # Packet Injection Tab
    add_arg("-n", form_data.get('packet_count_entry', ''))
    add_arg("-x", form_data.get('injection_rate_entry', ''))
    add_arg("-i", form_data.get('interval_entry', ''))
    add_arg("-s", form_data.get('packet_size_entry', ''))
    add_arg("-h", form_data.get('source_mac_entry', ''))
    add_checkbox_arg("-D", form_data.get('no_ack_var') == 'true')

    # Filtering Tab
    add_arg("-a", form_data.get('filter_bssid_entry', ''))
    # Note: -c and -e are overloaded. Assuming they are for filtering here if not used for target.
    # The original GUI code had -c and -e in both target and filter tabs.
    # For simplicity, I'll allow them here, but a real GUI would need more sophisticated logic
    # to differentiate based on which tab is active or which attack mode is selected.
    add_arg("-c", form_data.get('filter_client_mac_entry', ''))
    add_arg("-e", form_data.get('filter_essid_entry', ''))
    add_arg("--channel", form_data.get('filter_channel_entry', ''))
    add_checkbox_arg("--ignore-deauth", form_data.get('ignore_deauth_var') == 'true')

    # Output Tab
    add_arg("-w", form_data.get('output_file_entry', ''))
    add_checkbox_arg("-v", form_data.get('verbose_var') == 'true')
    add_checkbox_arg("-q", form_data.get('quiet_var') == 'true')
    add_checkbox_arg("--no-color", form_data.get('no_color_var') == 'true')

    # Advanced Tab
    add_arg("--auth-timeout", form_data.get('auth_timeout_entry', ''))
    add_arg("--deauth-timeout", form_data.get('deauth_timeout_entry', ''))
    add_arg("--burst", form_data.get('packet_burst_entry', ''))
    add_arg("--bssid-timeout", form_data.get('bssid_timeout_entry', ''))
    
    # Additional Arguments
    additional_args = form_data.get('additional_args_entry', '').strip()
    if additional_args:
        try:
            split_args = shlex.split(additional_args)
            command_parts.extend(split_args)
        except ValueError:
            # Fallback if shlex cannot parse, treat as single string
            command_parts.append(additional_args)

    # Interface is always the last argument
    interface = form_data.get('interface_entry', '').strip()
    if not interface:
        return [], "Error: Wireless interface is required."

    command_parts.append(shlex.quote(interface))

    return command_parts, None

def read_process_output(pipe, output_queue, log_file_path):
    """
    Reads output from a subprocess pipe line by line and puts it into a queue.
    Also writes the output to a log file.
    """
    with open(log_file_path, 'a') as f:
        for line in iter(pipe.readline, ''):
            output_queue.put(line)
            f.write(line)
    pipe.close()

def run_aireplay_in_thread(command_str):
    """
    Executes the aireplay-ng command in a separate thread.
    """
    global aireplay_process

    # Clear previous log file content if it exists
    if os.path.exists(AIREPLAY_LOG_FILE):
        os.remove(AIREPLAY_LOG_FILE)

    output_queue.put(f"Executing command: {command_str}\n\n")

    try:
        # Check if aireplay-ng is available in PATH
        if sys.platform.startswith('win'):
            # On Windows, `where` command checks for executables
            check_cmd = ['where', 'aireplay-ng']
        else:
            # On Unix-like systems, `which` command checks for executables
            check_cmd = ['which', 'aireplay-ng']
        
        # Suppress output of check_cmd to console
        subprocess.run(check_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        command = shlex.split(command_str)
        
        with process_running_lock:
            aireplay_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # Line-buffered
                universal_newlines=True
            )

        # Start threads to read stdout and stderr
        stdout_thread = threading.Thread(target=read_process_output, args=(aireplay_process.stdout, output_queue, AIREPLAY_LOG_FILE))
        stderr_thread = threading.Thread(target=read_process_output, args=(aireplay_process.stderr, output_queue, AIREPLAY_LOG_FILE))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        # Wait for the process to finish
        aireplay_process.wait()
        return_code = aireplay_process.returncode
        output_queue.put(f"\nAireplay-ng finished with exit code: {return_code}\n")
        output_queue.put(f"STATUS: {'Completed' if return_code == 0 else 'Failed'}\n")

    except FileNotFoundError:
        output_queue.put("Error: aireplay-ng command not found. Make sure aireplay-ng is installed and in your system's PATH.\n")
        output_queue.put("STATUS: Error\n")
    except subprocess.CalledProcessError:
        output_queue.put("Error: aireplay-ng command not found in system PATH. Please ensure aireplay-ng is installed and accessible.\n")
        output_queue.put("STATUS: Error\n")
    except Exception as e:
        output_queue.put(f"An error occurred while running aireplay-ng: {e}\n")
        output_queue.put("STATUS: Error\n")
    finally:
        with process_running_lock:
            aireplay_process = None # Clear the process object when done

# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main HTML page."""
    return render_template('index.html')

@app.route('/generate_command', methods=['POST'])
def generate_command():
    """Generates the aireplay-ng command based on form data."""
    form_data = request.json
    command_parts, error = generate_aireplay_command_parts(form_data)
    if error:
        return jsonify({'status': 'error', 'message': error, 'command': ''}), 400
    
    generated_cmd = " ".join(command_parts)
    return jsonify({'status': 'success', 'command': generated_cmd})

@app.route('/run_aireplay', methods=['POST'])
def run_aireplay():
    """Starts the aireplay-ng process."""
    global aireplay_process
    
    with process_running_lock:
        if aireplay_process and aireplay_process.poll() is None:
            return jsonify({'status': 'info', 'message': 'Aireplay-ng is already running.'}), 200

    data = request.json
    command_str = data.get('command')
    if not command_str:
        return jsonify({'status': 'error', 'message': 'No command provided to run.'}), 400

    # Start the aireplay-ng process in a new thread
    thread = threading.Thread(target=run_aireplay_in_thread, args=(command_str,))
    thread.daemon = True # Allow the main program to exit even if this thread is running
    thread.start()

    return jsonify({'status': 'success', 'message': 'Aireplay-ng started.'})

@app.route('/stream_output')
def stream_output():
    """Streams real-time output from aireplay-ng using Server-Sent Events (SSE)."""
    def generate():
        while True:
            try:
                line = output_queue.get(timeout=1) # Wait for a line with a timeout
                yield f"data: {line}\n\n"
            except queue.Empty:
                # If the queue is empty and the process is not running, break
                with process_running_lock:
                    if aireplay_process is None or aireplay_process.poll() is not None:
                        # Add a final message and break
                        if not output_queue.empty(): # Clear any remaining items
                            while not output_queue.empty():
                                yield f"data: {output_queue.get_nowait()}\n\n"
                        yield "event: end\ndata: Aireplay-ng session ended.\n\n"
                        break
                time.sleep(0.1) # Small delay to prevent busy-waiting if queue is empty

    return Response(generate(), mimetype='text/event-stream')

@app.route('/is_running')
def is_running():
    """Checks if the aireplay-ng process is currently running."""
    with process_running_lock:
        running = (aireplay_process is not None and aireplay_process.poll() is None)
    return jsonify({'running': running})

@app.route('/save_output', methods=['POST'])
def save_output():
    """Saves the current aireplay-ng output to a text file."""
    try:
        # Read the content from the log file
        if os.path.exists(AIREPLAY_LOG_FILE):
            with open(AIREPLAY_LOG_FILE, 'r') as f:
                output_content = f.read()
        else:
            output_content = "No output available to save yet."

        # Use a timestamp for the filename to avoid overwriting
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        save_path = os.path.join(LOG_DIR, f"aireplay_output_{timestamp}.txt")
        
        with open(save_path, 'w') as f:
            f.write(output_content)
        return jsonify({'status': 'success', 'message': f'Output saved to {save_path}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to save output: {e}'}), 500

@app.route('/save_command', methods=['POST'])
def save_command():
    """Saves the generated command to a text file."""
    data = request.json
    command_to_save = data.get('command')
    if not command_to_save:
        return jsonify({'status': 'error', 'message': 'No command provided to save.'}), 400

    try:
        # Use a timestamp for the filename to avoid overwriting
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        save_path = os.path.join(LOG_DIR, f"aireplay_command_{timestamp}.txt")

        with open(save_path, 'w') as f:
            f.write(command_to_save)
        return jsonify({'status': 'success', 'message': f'Command saved to {save_path}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to save command: {e}'}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Endpoint for graceful shutdown of the Flask application."""
    global aireplay_process
    
    # Terminate the aireplay-ng process if it's running
    with process_running_lock:
        if aireplay_process and aireplay_process.poll() is None:
            try:
                aireplay_process.terminate()
                aireplay_process.wait(timeout=5) # Give it some time to terminate
                output_queue.put("\nAireplay-ng process terminated by shutdown request.\n")
            except Exception as e:
                output_queue.put(f"\nError terminating aireplay-ng process: {e}\n")
            finally:
                aireplay_process = None

    # Shut down the Flask server
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return jsonify({'status': 'success', 'message': 'Server shutting down...'}), 200

# --- Main execution ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Aireplay-ng Web GUI Flask App")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the Flask app on.")
    args = parser.parse_args()

    # Ensure the 'templates' directory exists
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print(f"Created directory: {templates_dir}")

    # Ensure the 'logs' directory exists
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
        print(f"Created directory: {LOG_DIR}")

    print(f"Starting Flask app on port {args.port}...")
    app.run(host='127.0.0.1', port=args.port, debug=False) # debug=False for production use
