// Global variables (if needed, or passed as arguments)
const messageBox = document.getElementById('messageBox');

/**
 * Displays a message box with a given message and type (success or error).
 * @param {string} message - The message to display.
 * @param {string} [type='success'] - The type of message ('success' or 'error').
 */
function showMessage(message, type = 'success') {
    messageBox.textContent = message;
    messageBox.className = 'message-box show';
    if (type === 'error') {
        messageBox.classList.add('error');
    } else {
        messageBox.classList.remove('error');
    }
    setTimeout(() => {
        messageBox.classList.remove('show');
    }, 3000);
}

/**
 * Generates a random integer within a specified range.
 * @param {number} min - The minimum value (inclusive).
 * @param {number} max - The maximum value (inclusive).
 * @returns {number} A random integer.
 */
function getRandomInt(min, max) {
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

/**
 * Generates a random float within a specified range.
 * @param {number} min - The minimum value (inclusive).
 * @param {number} max - The maximum value (exclusive).
 * @returns {number} A random float.
 */
function getRandomFloat(min, max) {
    return Math.random() * (max - min) + min;
}

/**
 * Returns a random color from a predefined list.
 * @returns {string} A hex color string.
 */
function getRandomColor() {
    const colors = [
        '#00ff00', // green
        '#00ffff', // cyan
        '#ff00ff', // magenta
        '#ffff00', // yellow
        '#00aaff', // light blue
        '#ffaa00', // orange
        '#ff00aa', // pink
    ];
    return colors[getRandomInt(0, colors.length - 1)];
}

/**
 * Custom confirmation dialog.
 * @param {string} message - The message to display.
 * @param {function} onConfirm - Callback if user confirms.
 * @param {function} [onCancel] - Callback if user cancels.
 */
function showConfirmationDialog(message, onConfirm, onCancel = () => {}) {
    const dialogOverlay = document.createElement('div');
    dialogOverlay.className = 'modal-overlay show';
    dialogOverlay.style.zIndex = '1001';

    const dialogContent = document.createElement('div');
    dialogContent.className = 'modal-content';
    dialogContent.innerHTML = `
        <h3 class="text-xl font-bold text-white mb-4">${message}</h3>
        <div class="flex justify-end space-x-4">
            <button id="confirmBtn" class="btn bg-red-600 hover:bg-red-700">Confirm</button>
            <button id="cancelBtn" class="btn bg-gray-600 hover:bg-gray-700">Cancel</button>
        </div>
    `;

    dialogOverlay.appendChild(dialogContent);
    document.body.appendChild(dialogOverlay);

    document.getElementById('confirmBtn').onclick = () => {
        onConfirm();
        dialogOverlay.remove();
    };
    document.getElementById('cancelBtn').onclick = () => {
        onCancel();
        dialogOverlay.remove();
    };
}

/**
 * Function to convert ANSI escape codes to HTML spans for coloring.
 * @param {string} text - The text containing ANSI escape codes.
 * @returns {string} HTML string with styled spans.
 */
function ansiToHtml(text) {
    const ansiColors = {
        '30': 'ansi-black', '31': 'ansi-red', '32': 'ansi-green', '33': 'ansi-yellow',
        '34': 'ansi-blue', '35': 'ansi-magenta', '36': 'ansi-cyan', '37': 'ansi-white',
        '90': 'ansi-bright-black', '91': 'ansi-bright-red', '92': 'ansi-bright-green',
        '93': 'ansi-bright-yellow', '94': 'ansi-bright-blue', '95': 'ansi-bright-magenta',
        '96': 'ansi-bright-cyan', '97': 'ansi-bright-white',
        '1': 'ansi-bold', '4': 'ansi-underline', '0': 'ansi-reset'
    };

    let html = '';
    let parts = text.split(/(\x1b\[[0-9;]*m)/g);

    parts.forEach(part => {
        if (part.startsWith('\x1b[')) {
            const codes = part.substring(2, part.length - 1).split(';');
            codes.forEach(code => {
                if (ansiColors[code]) {
                    html += `<span class="${ansiColors[code]}">`;
                } else if (code === '0') {
                    html += `</span>`.repeat(10); // Close all open spans for reset
                }
            });
        } else {
            html += part;
        }
    });
    return html;
}

/**
 * Generates a SQLMap command string from the options object.
 * @param {object} options - The options object for the SQLMap command.
 * @returns {string} The generated SQLMap command.
 */
function generateSqlmapCommand(options) {
    let command = 'sqlmap.py';
    if (options.target_url_entry) { command += ` -u "${options.target_url_entry}"`; }
    if (options.post_data_entry) { command += ` --data="${options.post_data_entry}"`; }
    if (options.dbs_var) { command += ' --dbs'; }
    if (options.database_entry) { command += ` -D ${options.database_entry}`; }
    if (options.tables_var) { command += ' --tables'; }
    if (options.table_entry) { command += ` -T ${options.table_entry}`; }
    if (options.columns_var) { command += ' --columns'; }
    if (options.dump_var) { command += ' --dump'; }
    if (options.sql_shell_var) { command += ' --sql-shell'; }
    if (options.os_shell_var) { command += ' --os-shell'; }
    if (options.level_entry) { command += ` --level=${options.level_entry}`; }
    if (options.risk_entry) { command += ` --risk=${options.risk_entry}`; }
    if (options.technique_entry) { command += ` --technique=${options.technique_entry}`; }
    if (options.tamper_entry) { command += ` --tamper=${options.tamper_entry}`; }
    if (options.current_user_var) { command += ' --current-user'; }
    if (options.current_db_var) { command += ' --current-db'; }
    if (options.cookie_entry) { command += ` --cookie="${options.cookie_entry}"`; }
    if (options.user_agent_entry) { command += ` --user-agent="${options.user_agent_entry}"`; }
    if (options.threads_entry) { command += ` --threads=${options.threads_entry}`; }
    if (options.check_waf_var) { command += ' --check-waf'; }
    if (options.tamper_detection_entry) { command += ` --tamper="${options.tamper_detection_entry}"`; }
    return command;
}

/**
 * Copies text to the clipboard.
 * @param {string} text - The text to copy.
 */
function copyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand('copy');
        showMessage('Command copied to clipboard!', 'success');
    } catch (err) {
        console.error('Failed to copy text: ', err);
        showMessage('Failed to copy command.', 'error');
    }
    document.body.removeChild(textarea);
}
