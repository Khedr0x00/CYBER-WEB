import os
import sys
import argparse
from flask import Flask, request, jsonify

app = Flask(__name__)

# Function to change DocumentRoot and Directory paths in httpd.conf
def change_document_root_logic(httpd_conf_path, new_path):
    """
    Reads the httpd.conf file, replaces DocumentRoot and Directory paths,
    and returns the changes.
    """
    if not httpd_conf_path or not new_path:
        return {'status': 'error', 'message': 'Please provide both the httpd.conf path and the new document root path.'}

    # Normalize the new path for Apache config (using forward slashes)
    apache_formatted_new_path = new_path.replace("\\", "/")

    try:
        # Read the content of httpd.conf
        with open(httpd_conf_path, 'r') as f:
            lines = f.readlines()

        modified_lines = []
        document_root_found = False
        directory_found = False
        old_document_root = ""

        for line in lines:
            if line.strip().startswith("DocumentRoot"):
                # Extract the old DocumentRoot path
                parts = line.split('"')
                if len(parts) > 1:
                    old_document_root = parts[1].replace("\\", "/")
                
                modified_lines.append(f'DocumentRoot "{apache_formatted_new_path}"\n')
                document_root_found = True
            elif line.strip().startswith("<Directory") and old_document_root and old_document_root in line:
                # Replace the old Directory path only if DocumentRoot was found and matched
                modified_lines.append(f'<Directory "{apache_formatted_new_path}">\n')
                directory_found = True
            else:
                modified_lines.append(line)

        if not document_root_found:
            return {'status': 'warning', 'message': "Could not find 'DocumentRoot' directive in the file. No changes made."}

        # Write the modified content back to the file
        with open(httpd_conf_path, 'w') as f:
            f.writelines(modified_lines)

        message = f"Successfully updated DocumentRoot to '{new_path}' in:\n{httpd_conf_path}"
        if not directory_found:
            message += "\n\nWarning: Could not find a matching '<Directory>' directive for the old DocumentRoot. Only 'DocumentRoot' was updated."
        message += "\n\n*** IMPORTANT: You MUST manually stop and start Apache in your XAMPP Control Panel for these changes to take effect. ***"
        
        return {'status': 'success', 'message': message}

    except FileNotFoundError:
        return {'status': 'error', 'message': f"httpd.conf file not found at: {httpd_conf_path}\nPlease ensure the path is correct."}
    except PermissionError:
        return {'status': 'error', 'message': f"Permission denied to modify: {httpd_conf_path}\nPlease ensure the PHP server has write permissions or run this script with elevated privileges."}
    except Exception as e:
        return {'status': 'error', 'message': f"An unexpected error occurred: {e}"}

@app.route('/')
def index():
    return jsonify({"message": "XAMPP Document Root Changer Flask App is running."})

@app.route('/change_document_root', methods=['POST'])
def change_root():
    data = request.get_json()
    httpd_conf_path = data.get('httpd_conf_path')
    new_path = data.get('new_path')
    
    result = change_document_root_logic(httpd_conf_path, new_path)
    return jsonify(result)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    Endpoint to gracefully shut down the Flask application.
    This is called by the PHP script when stopping the app.
    """
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return jsonify({'status': 'success', 'message': 'Server shutting down...'}), 200

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run Flask XAMPP Document Root Changer App.')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the Flask app on.')
    args = parser.parse_args()
    app.run(host='127.0.0.1', port=args.port)
