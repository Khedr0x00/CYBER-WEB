import os
import sys
import threading
import time
import requests
from flask import Flask, render_template, request, jsonify, Response
from queue import Queue

# Initialize Flask app
app = Flask(__name__)

# List of admin pages to check (combined from both original scripts)
# This list can be loaded from a file or database if it becomes very large
ADMPAGE_LIST = [
    'admin/', 'administrator/', 'admin1/', 'admin2/', 'admin3/', 'admin4/', 'admin5/',
    'usuarios/', 'usuario/', 'moderator/', 'webadmin/', 'adminarea/', 'bb-admin/',
    'adminLogin/', 'admin_area/', 'panel-administracion/', 'instadmin/', 'memberadmin/',
    'administratorlogin/', 'adm/', 'admin/account.php', 'admin/index.php',
    'admin/login.php', 'admin/admin.php', 'admin/account.php', 'admin_area/admin.php',
    'admin_area/login.php', 'siteadmin/login.php', 'siteadmin/index.php',
    'siteadmin/login.html', 'admin/account.html', 'admin/index.html',
    'admin/login.html', 'admin/admin.html', 'admin_area/index.php',
    'bb-admin/index.php', 'bb-admin/login.php', 'bb-admin/admin.php',
    'admin/home.php', 'admin_area/login.html', 'admin_area/index.html',
    'admin/controlpanel.php', 'admin.php', 'admincp/index.asp',
    'admincp/login.asp', 'admincp/index.html', 'admin/account.html',
    'adminpanel.html', 'webadmin.html', 'webadmin/index.html',
    'webadmin/admin.html', 'webadmin/login.html', 'admin/admin_login.html',
    'admin_login.html', 'panel-administracion/login.html', 'admin/cp.php',
    'cp.php', 'administrator/index.php', 'administrator/login.php',
    'nsw/admin/login.php', 'webadmin/login.php', 'admin/admin_login.php',
    'admin_login.php', 'administrator/account.php', 'administrator.php',
    'admin_area/admin.html', 'pages/admin/admin-login.php',
    'admin/admin-login.php', 'admin-login.php', 'bb-admin/index.html',
    'bb-admin/login.html', 'acceso.php', 'bb-admin/admin.html',
    'admin/home.html', 'login.php', 'modelsearch/login.php', 'moderator.php',
    'moderator/login.php', 'moderator/admin.php', 'account.php',
    'pages/admin/admin-login.html', 'admin/admin-login.html',
    'admin-login.html', 'controlpanel.php', 'admincontrol.php',
    'admin/adminLogin.html', 'adminLogin.html', 'admin/adminLogin.html',
    'home.html', 'rcjakar/admin/login.php', 'adminarea/index.html',
    'adminarea/admin.html', 'webadmin.php', 'webadmin/index.php',
    'webadmin/admin.php', 'admin/controlpanel.html', 'admin.html',
    'admin/cp.html', 'cp.html', 'adminpanel.php', 'moderator.html',
    'administrator/login.html', 'user.html', 'administrator/account.html',
    'administrator.html', 'login.html', 'modelsearch/login.html',
    'moderator/login.html', 'adminarea/login.html',
    'panel-administracion/index.html', 'panel-administracion/admin.html',
    'modelsearch/index.html', 'modelsearch/admin.html',
    'admincontrol/login.html', 'adm/index.html', 'adm.html',
    'moderator/admin.html', 'user.php', 'account.html', 'controlpanel.html',
    'admincontrol.html', 'panel-administracion/login.php', 'wp-login.php',
    'adminLogin.php', 'admin/adminLogin.php', 'home.php', 'admin.php',
    'adminarea/index.php', 'adminarea/admin.php', 'adminarea/login.php',
    'panel-administracion/index.php', 'panel-administracion/admin.php',
    'modelsearch/index.php', 'modelsearch/admin.php',
    'admincontrol/login.php', 'adm/admloginuser.php', 'admloginuser.php',
    'admin2.php', 'admin2/login.php', 'admin2/index.php', 'usuarios/login.php',
    'adm/index.php', 'adm.php', 'affiliate.php', 'adm_auth.php', 'memberadmin.php', 'administratorlogin.php'
]

# Queue for real-time logging to the frontend
log_queue = Queue()
# Variable to track if a scan is in progress
scan_in_progress = False

# Define the directory for saving logs
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

def log_message(message, message_type='info'):
    """
    Puts a message into the log queue for real-time display.
    Also prints to console for server-side logging.
    Args:
        message (str): The message content.
        message_type (str): Type of message ('info', 'found', 'not_found', 'error').
    """
    timestamp = time.strftime('%H:%M:%S')
    # Prepend message type for frontend to parse
    formatted_message = f"[{timestamp}] [{message_type.upper()}] {message}"
    log_queue.put(formatted_message)
    print(formatted_message) # For server console visibility

def get_banner():
    """
    Returns the ASCII art banner for the application.
    """
    return """
          \\||                                  
         ,'_,-\\             C  O  D  E  D    B  Y    K  H  E  D  R  0  X  0  0
         ;'____\\

         || =\\=|
         ||  - |
     ,---'._--''-,,---------.--.----_,          Admin finder - Coded by Khedr0x00     
    / `-._- _--/,,|  ___,,--'--'._<       
   /-._,  `-.__;,,|'                            
  /   ;\\      / , ;                              
 /  ,' | _ - ',/, ;     
(  (   |     /, ,,;
    """

def perform_scan(site):
    """
    Performs the actual scanning of admin pages in a separate thread.
    Args:
        site (str): The cleaned website URL (e.g., "example.com").
    """
    global scan_in_progress
    scan_in_progress = True
    log_queue.put("CLEAR_LOG") # Signal frontend to clear log before new scan
    log_message(get_banner())
    log_message(f"Starting scan for: {site}")

    # Ensure site has a scheme for requests library
    if not site.startswith(('http://', 'https://')):
        site = 'http://' + site # Default to http if no scheme provided

    try:
        log_message(f"Attempting initial connection to {site}...")
        # Use a HEAD request for faster initial connection check
        requests.head(site, timeout=5)
        log_message("Initial connection successful.")
        log_message(f"Loaded {len(ADMPAGE_LIST)} admin-pages.")

        found_pages = []

        for adminpage in ADMPAGE_LIST:
            if not scan_in_progress: # Allow stopping the scan mid-way
                log_message("Scan interrupted by user.")
                break

            # Ensure adminpage starts with '/'
            if not adminpage.startswith('/'):
                adminpage = '/' + adminpage
            
            full_url = site + adminpage
            log_message(f"Checking --- {full_url}")

            try:
                response = requests.get(full_url, timeout=5)
                if response.status_code == 200:
                    log_message(f"Page found --- {full_url}", message_type='found')
                    found_pages.append(full_url)
                else:
                    # Explicitly mark as 'not_found' for non-200 status codes
                    log_message(f"Page not found (Status {response.status_code}) --- {full_url}", message_type='not_found')
            except requests.exceptions.Timeout:
                log_message(f"Timeout checking {full_url}", message_type='error')
            except requests.exceptions.ConnectionError:
                log_message(f"Connection error for {full_url}", message_type='error')
            except requests.exceptions.RequestException as e:
                log_message(f"Error checking {full_url}: {e}", message_type='error')
            time.sleep(0.05) # Small delay to prevent overwhelming the target server

        if scan_in_progress: # Only show completion message if not interrupted
            log_message("Scan completed.")
            if found_pages:
                log_message("--- Found Admin Pages ---")
                for page in found_pages:
                    log_message(page, message_type='found') # Re-log found pages at the end for summary
            else:
                log_message("No admin pages found.")

    except requests.exceptions.ConnectionError as e:
        log_message(f"Invalid URL / Offline Server: {e}", message_type='error')
    except requests.exceptions.RequestException as e:
        log_message(f"An unexpected error occurred: {e}", message_type='error')
    except Exception as e:
        log_message(f"An unexpected error occurred during scan setup: {e}", message_type='error')
    finally:
        scan_in_progress = False
        log_message("SCAN_FINISHED") # Signal frontend that scan has truly finished

@app.route('/')
def index():
    """
    Renders the main HTML page for the Admin Finder.
    """
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def start_scan_route():
    """
    API endpoint to start the admin page scanning process.
    """
    global scan_in_progress
    if scan_in_progress:
        return jsonify({'status': 'error', 'message': 'Scan already in progress.'}), 409

    data = request.get_json()
    website_url = data.get('website_url', '').strip()

    if not website_url:
        return jsonify({'status': 'error', 'message': 'Website URL is required.'}), 400

    # Start the scanning in a new thread to keep the Flask app responsive
    thread = threading.Thread(target=perform_scan, args=(website_url,))
    thread.daemon = True # Allow the main program to exit even if thread is running
    thread.start()

    return jsonify({'status': 'success', 'message': 'Scan started.'})

@app.route('/stop_scan', methods=['POST'])
def stop_scan_route():
    """
    API endpoint to stop the admin page scanning process.
    """
    global scan_in_progress
    if scan_in_progress:
        scan_in_progress = False # Signal the scanning thread to stop
        return jsonify({'status': 'success', 'message': 'Scan stop requested.'})
    else:
        return jsonify({'status': 'info', 'message': 'No scan is currently in progress.'})

@app.route('/stream_logs')
def stream_logs():
    """
    Streams real-time logs to the frontend using Server-Sent Events (SSE).
    """
    def generate_logs():
        while True:
            # Check if the queue is empty. If so, wait a bit before checking again.
            # This prevents busy-waiting and allows the server to handle other requests.
            if not log_queue.empty():
                log_entry = log_queue.get()
                # Send the log entry as an SSE event
                yield f"data: {log_entry}\n\n"
            else:
                time.sleep(0.05) # Small delay to prevent high CPU usage

    return Response(generate_logs(), mimetype='text/event-stream')

@app.route('/save_log', methods=['POST'])
def save_log():
    """
    Saves the current content of the log box to a text file.
    """
    data = request.get_json()
    log_content = data.get('log_content', '')

    if not log_content:
        return jsonify({'status': 'error', 'message': 'No log content to save.'}), 400

    timestamp = time.strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(LOGS_DIR, f'admin_finder_log_{timestamp}.txt')

    try:
        # Before saving, strip out the `[TYPE]` prefixes for cleaner log file output
        clean_log_content = "\n".join([
            line.split('] ', 2)[2] if line.count(']') >= 2 else line
            for line in log_content.split('\n') if line.strip()
        ])
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(clean_log_content)
        return jsonify({'status': 'success', 'message': f'Log saved to {os.path.basename(filename)}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to save log: {e}'}), 500

# Endpoint for PHP to shut down the Flask app gracefully
@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    Shuts down the Flask application. This is intended to be called by the PHP controller.
    """
    log_message("Received shutdown request. Shutting down Flask app...")
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'

if __name__ == '__main__':
    # Default port if not provided via command line
    port = 5000 
    # Check for --port argument from the PHP launcher
    if '--port' in sys.argv:
        try:
            port_index = sys.argv.index('--port') + 1
            if port_index < len(sys.argv):
                port = int(sys.argv[port_index])
        except (ValueError, IndexError):
            print("Warning: Invalid port specified. Using default port 5000.")

    app.run(host='0.0.0.0', port=port, debug=False) # debug should be False in production
