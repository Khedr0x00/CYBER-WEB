import sys
from flask import Flask, request, jsonify, render_template
import os

# Original TwinHexEncoder class (copied from twin_cipher.py)
class TwinHexEncoder:
    cbase = [chr(x) + chr(y) for x in range(32, 128) for y in range(32, 128)]
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"

    def base36encode(self, number):
        if not isinstance(number, (int)):
            raise TypeError("must be an integer")
        if number < 0:
            raise ValueError("must be positive")
        encoded_string = ""
        while number:
            number, i = divmod(number, 36)
            encoded_string = self.alphabet[i] + encoded_string
        return encoded_string or self.alphabet[0]

    def encrypt(self, char):
        flag_out = ""
        for i in range(0, len(char), 2):
            pair = char[i : i + 2]
            if len(pair) < 2:
                pair += " "
            try:
                flag_out += self.base36encode(self.cbase.index(pair)).ljust(3, " ")
            except ValueError:
                # Handle cases where a pair is not in cbase (e.g., non-printable chars)
                raise ValueError(f"Invalid character pair for encoding: '{pair}'")
        return flag_out

# Original TwinHexDecoder class (copied from twin_cipher.py)
class TwinHexDecoder:
    cbase = [chr(x) + chr(y) for x in range(32, 128) for y in range(32, 128)]

    def decrypt(self, char):
        flag_out = ""
        try:
            # Ensure input is a string and handle potential non-string inputs gracefully
            if not isinstance(char, str):
                raise TypeError("Input for decryption must be a string.")
            
            triples = [char[i : i + 3] for i in range(0, len(char), 3)]
            # Filter out empty or whitespace-only triples before conversion
            flag_out += "".join(self.cbase[int(x.strip(), 36)] for x in triples if x.strip())
        except ValueError as e:
            # Catch errors during base36 conversion or index lookup
            raise ValueError(f"Decryption Error: Invalid input format or character. Details: {e}")
        except IndexError as e:
            # Catch errors if the calculated index is out of bounds for cbase
            raise IndexError(f"Decryption Error: Invalid encoded sequence. Details: {e}")
        except Exception as e:
            # Catch any other unexpected errors
            raise Exception(f"An unexpected error occurred during decryption: {e}")
        return flag_out

app = Flask(__name__)

# Initialize encoder and decoder instances
encoder = TwinHexEncoder()
decoder = TwinHexDecoder()

@app.route('/')
def index():
    """Renders the main HTML page for the cipher application."""
    return render_template('index.html')

@app.route('/encode', methods=['POST'])
def encode_text():
    """
    API endpoint to encode text using the TwinHexEncoder.
    Expects JSON input: {"text": "your_text_here"}
    Returns JSON output: {"encoded_text": "...", "status": "success"} or {"error": "...", "status": "error"}
    """
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "Missing 'text' in request body", "status": "error"}), 400

    input_text = data['text']
    if not input_text.strip():
        return jsonify({"error": "Please enter text to encode.", "status": "error"}), 400

    try:
        encoded_flag = encoder.encrypt(input_text)
        return jsonify({"encoded_text": encoded_flag, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/decode', methods=['POST'])
def decode_text():
    """
    API endpoint to decode text using the TwinHexDecoder.
    Expects JSON input: {"text": "your_encoded_text_here"}
    Returns JSON output: {"decoded_text": "...", "status": "success"} or {"error": "...", "status": "error"}
    """
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "Missing 'text' in request body", "status": "error"}), 400

    input_text = data['text']
    if not input_text.strip():
        return jsonify({"error": "Please enter text to decode.", "status": "error"}), 400

    try:
        decoded_flag = decoder.decrypt(input_text)
        return jsonify({"decoded_text": decoded_flag, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    Endpoint to gracefully shut down the Flask server.
    This is called by the PHP controller when stopping the app.
    """
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return jsonify({"message": "Server shutting down...", "status": "success"})

if __name__ == '__main__':
    # Default port
    port = 5000

    # Parse command-line arguments for port (expected by index.php)
    if '--port' in sys.argv:
        try:
            port_index = sys.argv.index('--port') + 1
            if port_index < len(sys.argv):
                port = int(sys.argv[port_index])
        except (ValueError, IndexError):
            print("Warning: Invalid port argument. Using default port 5000.")

    print(f"Starting Flask app on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, debug=False) # debug=False for production use
