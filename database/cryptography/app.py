import os
import sys
import threading
import time
import queue
import logging
import base64
import urllib.parse
import binascii
import hashlib
import json
from flask import Flask, request, render_template, jsonify, Response
from werkzeug.serving import make_server

# --- Flask Application Setup ---
app = Flask(__name__)

# --- Logging Setup ---
# Create a thread-safe queue for logs
log_queue = queue.Queue()

# Define log file path relative to the app.py location
LOG_FILE_NAME = "app_activity.log"
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_FILE_NAME)

# Custom handler to put logs into the queue and write to file
class QueueAndFileHandler(logging.Handler):
    def __init__(self, log_queue, filename):
        super().__init__()
        self.log_queue = log_queue
        self.file_handler = logging.FileHandler(filename, mode='a')
        self.file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        log_entry = self.format(record)
        self.log_queue.put(log_entry)
        self.file_handler.emit(record)

# Configure the logger
app_logger = logging.getLogger(__name__)
app_logger.setLevel(logging.INFO)

# Clear existing handlers to prevent duplicate logs
if app_logger.hasHandlers():
    app_logger.handlers.clear()

# Add the custom handler
handler = QueueAndFileHandler(log_queue, LOG_FILE_PATH)
app_logger.addHandler(handler)

# Also add a StreamHandler to print to console (useful for debugging)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
app_logger.addHandler(console_handler)

app_logger.info("Flask application started and logger initialized.")

# --- Morse Code Mapping ---
MORSE_CODE_DICT = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
    'Z': '--..', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...',
    '8': '---..', '9': '----.', '0': '-----',
    ',': '--..--', '.': '.-.-.-', '?': '..--..', '/': '-..-.',
    '-': '-....-', '(': '-.--.', ')': '-.--.-', '&': '.-...',
    ':': '---...', ';': '-.-.-.', '=': '-...-', '+': '.-.-.',
    '"': '.-..-.', '$': '...-..-', '!': '-.-.--', '@': '.--.-.',
    ' ': '/' # Space is represented by a single slash in Morse
}
# Reverse dictionary for decoding Morse
MORSE_DECODE_DICT = {value: key for key, value in MORSE_CODE_DICT.items()}


# --- Encoding/Decoding Functions ---
def process_single_line(line, encoding_option, key=None):
    """Processes a single line of text based on the selected encoding option."""
    try:
        if encoding_option == "Base64 Encode":
            return base64.b64encode(line.encode('utf-8')).decode('utf-8')
        elif encoding_option == "Base64 Decode":
            return base64.b64decode(line.encode('utf-8')).decode('utf-8')
        elif encoding_option == "URL Encode":
            return urllib.parse.quote(line)
        elif encoding_option == "URL Decode":
            return urllib.parse.unquote(line)
        elif encoding_option == "Hex Encode":
            return line.encode('utf-8').hex()
        elif encoding_option == "Hex Decode":
            return bytes.fromhex(line).decode('utf-8')
        elif encoding_option == "MD5 Hash":
            return hashlib.md5(line.encode('utf-8')).hexdigest()
        elif encoding_option == "SHA1 Hash":
            return hashlib.sha1(line.encode('utf-8')).hexdigest()
        elif encoding_option == "SHA256 Hash":
            return hashlib.sha256(line.encode('utf-8')).hexdigest()
        elif encoding_option == "SHA512 Hash":
            return hashlib.sha512(line.encode('utf-8')).hexdigest()
        elif encoding_option == "JSON Beautify":
            return json.dumps(json.loads(line), indent=4)
        elif encoding_option == "JSON Minify":
            return json.dumps(json.loads(line), separators=(",", ":"))
        elif encoding_option == "ASCII to Binary":
            return ' '.join(format(ord(char), '08b') for char in line)
        elif encoding_option == "Binary to ASCII":
            return ''.join(chr(int(byte, 2)) for byte in line.split())
        elif encoding_option == "Reverse String":
            return line[::-1]
        elif encoding_option == "Morse Encode":
            return ' '.join(MORSE_CODE_DICT.get(char.upper(), '') for char in line)
        elif encoding_option == "Morse Decode":
            # Morse code words are separated by ' / ' and letters by ' '
            words = line.split(' / ')
            decoded_words = []
            for word in words:
                chars = word.split(' ')
                decoded_chars = []
                for char in chars:
                    decoded_chars.append(MORSE_DECODE_DICT.get(char, ''))
                decoded_words.append(''.join(decoded_chars))
            return ' '.join(decoded_words)
        elif encoding_option == "Caesar Encrypt":
            if not key: raise ValueError("Caesar cipher requires a key (shift value).")
            shift = int(key) % 26
            result = ""
            for char in line:
                if 'a' <= char <= 'z':
                    result += chr(((ord(char) - ord('a') + shift) % 26) + ord('a'))
                elif 'A' <= char <= 'Z':
                    result += chr(((ord(char) - ord('A') + shift) % 26) + ord('A'))
                else:
                    result += char
            return result
        elif encoding_option == "Caesar Decrypt":
            if not key: raise ValueError("Caesar cipher requires a key (shift value).")
            shift = int(key) % 26
            result = ""
            for char in line:
                if 'a' <= char <= 'z':
                    result += chr(((ord(char) - ord('a') - shift + 26) % 26) + ord('a'))
                elif 'A' <= char <= 'Z':
                    result += chr(((ord(char) - ord('A') - shift + 26) % 26) + ord('A'))
                else:
                    result += char
            return result
        elif encoding_option == "ROT13 Encrypt/Decrypt":
            result = ""
            for char in line:
                if 'a' <= char <= 'z':
                    result += chr(((ord(char) - ord('a') + 13) % 26) + ord('a'))
                elif 'A' <= char <= 'Z':
                    result += chr(((ord(char) - ord('A') + 13) % 26) + ord('A'))
                else:
                    result += char
            return result
        elif encoding_option == "Vigenere Encrypt":
            if not key: raise ValueError("Vigenere cipher requires a key.")
            key = key.upper()
            result = ""
            key_index = 0
            for char in line:
                if 'a' <= char <= 'z':
                    shift = ord(key[key_index % len(key)]) - ord('A')
                    result += chr(((ord(char) - ord('a') + shift) % 26) + ord('a'))
                    key_index += 1
                elif 'A' <= char <= 'Z':
                    shift = ord(key[key_index % len(key)]) - ord('A')
                    result += chr(((ord(char) - ord('A') + shift) % 26) + ord('A'))
                    key_index += 1
                else:
                    result += char
            return result
        elif encoding_option == "Vigenere Decrypt":
            if not key: raise ValueError("Vigenere cipher requires a key.")
            key = key.upper()
            result = ""
            key_index = 0
            for char in line:
                if 'a' <= char <= 'z':
                    shift = ord(key[key_index % len(key)]) - ord('A')
                    result += chr(((ord(char) - ord('a') - shift + 26) % 26) + ord('a'))
                    key_index += 1
                elif 'A' <= char <= 'Z':
                    shift = ord(key[key_index % len(key)]) - ord('A')
                    result += chr(((ord(char) - ord('A') - shift + 26) % 26) + ord('A'))
                    key_index += 1
                else:
                    result += char
            return result
        elif encoding_option == "XOR Encrypt/Decrypt":
            if not key: raise ValueError("XOR cipher requires a key.")
            result_bytes = bytearray()
            key_bytes = key.encode('utf-8')
            key_len = len(key_bytes)
            for i, byte_val in enumerate(line.encode('utf-8')):
                result_bytes.append(byte_val ^ key_bytes[i % key_len])
            return result_bytes.decode('utf-8', errors='ignore') # Use errors='ignore' for non-decodable bytes
        elif encoding_option == "Atbash Encrypt/Decrypt":
            result = ""
            for char in line:
                if 'a' <= char <= 'z':
                    result += chr(ord('a') + (ord('z') - ord(char)))
                elif 'A' <= char <= 'Z':
                    result += chr(ord('A') + (ord('Z') - ord(char)))
                else:
                    result += char
            return result
        else:
            return "Invalid option"
    except Exception as e:
        app_logger.error(f"Error processing line '{line}' with option '{encoding_option}': {e}")
        return f"Error: {str(e)}"

# --- Flask Routes ---
@app.route('/')
def index():
    """Renders the main HTML page for the encoder/decoder tool."""
    app_logger.info("Serving index.html")
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_text_route():
    """Handles POST requests for text encoding/decoding."""
    data = request.json
    input_text = data.get('inputText', '').strip()
    encoding_option = data.get('encodingOption', '')
    key = data.get('key', None) # Get the key if provided

    app_logger.info(f"Processing request: Option='{encoding_option}', Input length={len(input_text)}, Key present={bool(key)}")

    output_lines = []
    for line in input_text.splitlines():
        output_lines.append(process_single_line(line, encoding_option, key))

    output_text = "\n".join(output_lines)

    app_logger.info(f"Processing complete. Output length={len(output_text)}")
    return jsonify({'outputText': output_text})

@app.route('/save_output', methods=['POST'])
def save_output():
    """Handles POST requests to save output text to a file."""
    data = request.json
    output_text = data.get('outputText', '')
    file_name = data.get('fileName', 'output.txt')

    # Ensure file_name is safe (basic sanitization)
    file_name = os.path.basename(file_name)
    if not file_name.endswith('.txt'):
        file_name += '.txt'

    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)

    try:
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(output_text)
        app_logger.info(f"Output saved to {save_path}")
        return jsonify({'status': 'success', 'message': f'Output saved to {file_name}'})
    except Exception as e:
        app_logger.error(f"Error saving output to {save_path}: {e}")
        return jsonify({'status': 'error', 'message': f'Failed to save output: {str(e)}'})

@app.route('/log_stream')
def log_stream():
    """Streams real-time logs to the client using Server-Sent Events (SSE)."""
    def generate_logs():
        # Try to open the log file and seek to the end
        try:
            with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
                f.seek(0, os.SEEK_END)  # Go to the end of the file
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(1)  # Wait for new log entries
                        continue
                    yield f"data: {line}\n\n"
        except FileNotFoundError:
            app_logger.warning(f"Log file not found at {LOG_FILE_PATH}. Streaming will start when it's created.")
            # If file doesn't exist, wait for it to be created
            while not os.path.exists(LOG_FILE_PATH):
                time.sleep(1)
            # Once created, restart the generator
            yield from generate_logs() # Recursive call to start reading from the new file
        except Exception as e:
            app_logger.error(f"Error reading log file for streaming: {e}")
            yield f"data: Error streaming logs: {e}\n\n"

    app_logger.info("Client connected to log stream.")
    return Response(generate_logs(), mimetype='text/event-stream')

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Handles requests to gracefully shut down the Flask server."""
    app_logger.info("Received shutdown request.")
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        app_logger.warning("Not running with the Werkzeug server. Cannot shut down gracefully.")
        return jsonify({'status': 'error', 'message': 'Not running with Werkzeug server'})
    func()
    app_logger.info("Server shutting down...")
    return jsonify({'status': 'success', 'message': 'Server shutting down'})


# --- Main execution ---
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Run the Encoder/Decoder Flask App.")
    parser.add_argument('--port', type=int, default=5000,
                        help='Port number for the Flask application to listen on.')
    args = parser.parse_args()

    # Ensure the log file exists or is created
    # This is handled by FileHandler when it's initialized, but good to be explicit
    if not os.path.exists(LOG_FILE_PATH):
        try:
            with open(LOG_FILE_PATH, 'w') as f:
                f.write("") # Create an empty file
            app_logger.info(f"Created empty log file at {LOG_FILE_PATH}")
        except Exception as e:
            app_logger.error(f"Could not create log file at {LOG_FILE_PATH}: {e}")

    app_logger.info(f"Starting Flask app on port {args.port}...")
    # Using app.run() directly for simplicity, but for production, use a WSGI server
    app.run(host='0.0.0.0', port=args.port, debug=False)
