import os
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
import sys # For port argument

app = Flask(__name__)

# Define the root directory for the application
# This assumes app.py is directly inside the image gallery app folder (e.g., scripts/image_gallery_app/)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# Allowed image extensions
ALLOWED_EXTENSIONS = ('.png', '.webp', '.jpg', '.jpeg', '.gif') # Added more common image types for flexibility

@app.route('/')
def index():
    """Renders the main image gallery HTML page."""
    return render_template('index.html')

@app.route('/categories')
def get_categories():
    """
    Scans the APP_ROOT for main category folders (e.g., 'cyber', 'program').
    Only directories directly under APP_ROOT are considered categories.
    """
    categories = []
    try:
        for item in os.listdir(APP_ROOT):
            item_path = os.path.join(APP_ROOT, item)
            if os.path.isdir(item_path) and not item.startswith('.'): # Exclude hidden directories
                # You can add specific category checks here if needed, e.g., if item in ['cyber', 'program']
                categories.append(item)
        categories.sort() # Sort categories alphabetically
    except Exception as e:
        print(f"Error listing categories: {e}")
        return jsonify({"error": "Failed to list categories", "details": str(e)}), 500
    return jsonify(categories)

@app.route('/subfolders/<category_name>')
def get_subfolders(category_name):
    """
    Scans a given category folder for its subfolders.
    """
    category_path = os.path.join(APP_ROOT, category_name)
    subfolders = []
    if not os.path.isdir(category_path):
        return jsonify({"error": "Category not found"}), 404

    try:
        for item in os.listdir(category_path):
            item_path = os.path.join(category_path, item)
            if os.path.isdir(item_path) and not item.startswith('.'): # Exclude hidden directories
                subfolders.append(item)
        subfolders.sort() # Sort subfolders alphabetically
    except Exception as e:
        print(f"Error listing subfolders for {category_name}: {e}")
        return jsonify({"error": f"Failed to list subfolders for {category_name}", "details": str(e)}), 500
    return jsonify(subfolders)

@app.route('/images/<category_name>/<subfolder_name>')
def get_images(category_name, subfolder_name):
    """
    Lists all allowed image files (.webp, .png, etc.) within a specified subfolder.
    Returns relative paths for serving.
    """
    subfolder_path = os.path.join(APP_ROOT, category_name, subfolder_name)
    images = []
    if not os.path.isdir(subfolder_path):
        return jsonify({"error": "Subfolder not found"}), 404

    try:
        for filename in os.listdir(subfolder_path):
            if filename.lower().endswith(ALLOWED_EXTENSIONS):
                # Construct a URL that Flask's send_from_directory can handle
                # The 'image_display' endpoint will serve these files
                relative_path = os.path.join(category_name, subfolder_name, filename)
                images.append(relative_path.replace(os.sep, '/')) # Use forward slashes for URLs
        images.sort() # Sort images alphabetically
    except Exception as e:
        print(f"Error listing images in {subfolder_path}: {e}")
        return jsonify({"error": f"Failed to list images in {subfolder_path}", "details": str(e)}), 500
    return jsonify(images)

@app.route('/image_display/<path:image_path>')
def image_display(image_path):
    """
    Serves image files from the APP_ROOT directory based on the provided path.
    The path parameter is expected to be relative to APP_ROOT (e.g., 'cyber/subfolder1/image.png').
    """
    # Split the image_path to get the directory and filename
    directory = os.path.dirname(image_path)
    filename = os.path.basename(image_path)

    # Ensure the directory is within APP_ROOT for security
    full_path = os.path.join(APP_ROOT, directory)
    if not os.path.abspath(full_path).startswith(APP_ROOT):
        return "Access denied", 403

    try:
        return send_from_directory(full_path, filename)
    except FileNotFoundError:
        return "Image not found", 404
    except Exception as e:
        print(f"Error serving image {image_path}: {e}")
        return "Error serving image", 500

# Function to gracefully shut down the Flask server (for PHP controller)
def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Endpoint to gracefully shut down the Flask application."""
    print("Received shutdown request.")
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

    print(f"Image Gallery sub-app is starting on port {port}...")
    app.run(debug=True, host='0.0.0.0', port=port)
