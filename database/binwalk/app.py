import os
import subprocess
import shlex
import json
from flask import Flask, render_template, request, jsonify, send_file, Response
import threading
import queue
import time
import uuid # For unique filenames
import shutil # Added for shutil.which
import sys # To detect OS and get command-line arguments

app = Flask(__name__)

# Directory to store temporary files (e.g., uploaded target files, scan outputs)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# In-memory storage for binwalk outputs (for demonstration).
# In a real-world app, consider a more persistent and scalable solution (e.g., database, cloud storage).
binwalk_outputs = {}
binwalk_processes = {} # To keep track of running binwalk processes
binwalk_queues = {} # To store queues for real-time output

# Load examples from binwalk_examples.txt
def load_examples(filename="binwalk_examples.txt"):
    """Loads examples from a JSON file."""
    try:
        # Assuming binwalk_examples.txt is in the same directory as app.py
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Examples file '{filename}' not found. Please ensure it's in the same directory as app.py.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{filename}'. Please check its format.")
        return []

# Function to run a command and stream its output to a queue
def run_command_stream_output(command, scan_id, output_queue):
    process = None
    try:
        # Use shlex.split to correctly handle command arguments, especially with spaces
        process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        binwalk_processes[scan_id] = process

        for line in process.stdout:
            output_queue.put(line)
            # print(f"[{scan_id}] {line.strip()}") # For debugging on server side
        process.wait()
        output_queue.put(f"\n--- Binwalk process finished with exit code {process.returncode} ---")
    except FileNotFoundError:
        output_queue.put(f"Error: Command not found. Make sure 'binwalk' is installed and in your system's PATH.\n")
    except Exception as e:
        output_queue.put(f"An error occurred: {e}\n")
    finally:
        if scan_id in binwalk_processes:
            del binwalk_processes[scan_id]
        output_queue.put("---END_OF_STREAM---") # Signal the end of the stream

@app.route('/')
def index():
    """Renders the main HTML page for the Binwalk GUI."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles file uploads for Binwalk analysis."""
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    if file:
        # Generate a unique filename to prevent conflicts
        unique_filename = str(uuid.uuid4()) + "_" + file.filename
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        return jsonify({'message': 'File uploaded successfully', 'filepath': filepath}), 200

@app.route('/run_binwalk', methods=['POST'])
def run_binwalk():
    """
    Constructs and executes a binwalk command based on frontend parameters.
    Starts a new thread to run binwalk and stream output.
    """
    data = request.get_json()
    target = data.get('target', '').strip()
    options = data.get('options', [])

    if not target:
        return jsonify({'message': 'No target specified.'}), 400

    # Basic command structure
    command_parts = ['binwalk']

    # Add options based on frontend selections
    command_parts.extend(options)
    command_parts.append(target)

    full_command = ' '.join(command_parts)
    print(f"Executing command: {full_command}")

    scan_id = str(uuid.uuid4())
    output_queue = queue.Queue()
    binwalk_queues[scan_id] = output_queue

    # Start binwalk in a new thread to avoid blocking the Flask app
    thread = threading.Thread(target=run_command_stream_output, args=(full_command, scan_id, output_queue))
    thread.daemon = True # Allow the thread to exit when the main program exits
    thread.start()

    return jsonify({'message': 'Binwalk scan started', 'scan_id': scan_id}), 200

@app.route('/stream_output/<scan_id>')
def stream_output(scan_id):
    """Streams real-time binwalk output to the frontend using Server-Sent Events."""
    if scan_id not in binwalk_queues:
        return Response("Scan ID not found", status=404)

    output_queue = binwalk_queues[scan_id]

    def generate():
        while True:
            try:
                line = output_queue.get(timeout=1) # Wait for 1 second
                if line == "---END_OF_STREAM---":
                    break
                yield f"data: {json.dumps({'output': line})}\n\n"
            except queue.Empty:
                # Keep the connection alive
                yield f"data: {json.dumps({'output': ''})}\n\n"
            except Exception as e:
                print(f"Error streaming output: {e}")
                break
        # Clean up the queue after the stream ends
        if scan_id in binwalk_queues:
            del binwalk_queues[scan_id]

    return Response(generate(), mimetype='text/event-stream')

@app.route('/get_examples')
def get_examples():
    """Returns the binwalk examples."""
    examples = load_examples()
    return jsonify(examples)

@app.route('/check_binwalk_installed')
def check_binwalk_installed():
    """Checks if binwalk is installed on the system."""
    binwalk_path = shutil.which("binwalk")
    if binwalk_path:
        return jsonify({'installed': True, 'path': binwalk_path}), 200
    else:
        return jsonify({'installed': False}), 200

@app.route('/install_binwalk', methods=['POST'])
def install_binwalk():
    """
    Handles automatic binwalk installation for Linux/Termux systems.
    Provides instructions for other OS.
    """
    os_platform = sys.platform
    install_type = request.json.get('install_type')

    if install_type == 'linux' and ('linux' in os_platform or 'ubuntu' in os_platform):
        try:
            # Update package list and install binwalk
            update_command = "sudo apt update -y"
            install_command = "sudo apt install -y binwalk firmware-mod-kit" # firmware-mod-kit is a common dependency

            subprocess.run(shlex.split(update_command), check=True, capture_output=True, text=True)
            subprocess.run(shlex.split(install_command), check=True, capture_output=True, text=True)

            return jsonify({
                'message': 'Binwalk and dependencies installed successfully on Linux.',
                'output': 'Installation complete.'
            }), 200
        except subprocess.CalledProcessError as e:
            return jsonify({
                'message': f'Error during Binwalk installation: {e.stderr}',
                'output': f'Command failed: {e.cmd}\nStdout: {e.stdout}\nStderr: {e.stderr}'
            }), 500
        except FileNotFoundError:
            return jsonify({
                'message': 'Error: "apt" command not found. Are you on a Debian/Ubuntu-based system?',
                'output': 'apt command not found.'
            }), 500
        except Exception as e:
            return jsonify({
                'message': f'An unexpected error occurred during Linux installation: {str(e)}',
                'output': 'Unexpected error.'
            }), 500
    elif install_type == 'termux' and 'android' in os_platform: # Termux on Android
        try:
            # Update package list and install binwalk
            update_command = "pkg update -y"
            install_command = "pkg install -y binwalk"

            subprocess.run(shlex.split(update_command), check=True, capture_output=True, text=True)
            subprocess.run(shlex.split(install_command), check=True, capture_output=True, text=True)

            return jsonify({
                'message': 'Binwalk installed successfully on Termux.',
                'output': 'Installation complete.'
            }), 200
        except subprocess.CalledProcessError as e:
            return jsonify({
                'message': f'Error during Binwalk installation: {e.stderr}',
                'output': f'Command failed: {e.cmd}\nStdout: {e.stdout}\nStderr: {e.stderr}'
            }), 500
        except FileNotFoundError:
            return jsonify({
                'message': 'Error: "pkg" command not found. Are you sure you are in Termux?',
                'output': 'pkg command not found.'
            }), 500
        except Exception as e:
            return jsonify({
                'message': f'An unexpected error occurred during Termux installation: {str(e)}',
                'output': 'Unexpected error.'
            }), 500
    elif install_type == 'windows':
        return jsonify({
            'message': 'For Windows, please download the installer from the official Binwalk GitHub page or use WSL (Windows Subsystem for Linux).',
            'output': 'Windows installation instructions provided.'
        }), 200
    elif install_type == 'macos':
        return jsonify({
            'message': 'For macOS, you can install Binwalk via Homebrew: `brew install binwalk`.',
            'output': 'macOS installation instructions provided.'
        }), 200
    else:
        return jsonify({
            'message': 'Binwalk installation via this interface is only supported on Linux/Termux systems.',
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
    
    print(f"Binwalk sub-app is starting on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

