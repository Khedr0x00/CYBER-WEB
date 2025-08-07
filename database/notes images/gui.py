import os
import re
import tkinter as tk
from tkinter import Listbox, Label, Entry, Button, Frame, Scrollbar, Canvas, simpledialog, Text, messagebox, Toplevel, \
    PhotoImage, Checkbutton, BooleanVar, filedialog, OptionMenu
from PIL import Image, ImageTk, ImageGrab, ImageEnhance, ImageDraw, ImageFont
import pytesseract
import subprocess
import pyperclip
import shutil
import datetime
import platform

# Import for RTL/LTR text handling
try:
    from bidi import algorithm as bidi_alg
except ImportError:
    messagebox.showerror("Error", "The 'python-bidi' library is not installed.\n"
                                "Please install it using: pip install python-bidi\n"
                                "RTL functionality will be disabled.")
    bidi_alg = None

# Function for natural sorting (e.g., Image1, Image2, Image10 instead of Image1, Image10, Image2)
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


class ImageGallery:
    def __init__(self, root):
        self.root = root
        self.root.title("Seascape Image Viewer")
        self.root.geometry("1200x800")

        # Define color scheme for the UI
        self.bg_color = '#003049'       # Dark blue
        self.fg_color = '#FCBF49'       # Gold/Orange
        self.accent_color = '#D62828'   # Red
        self.button_bg = '#4169E1'      # Royal Blue
        self.button_fg = 'white'
        self.listbox_bg = '#87CEEB'     # Sky Blue
        self.listbox_fg = '#003049'     # Dark blue

        self.root.configure(bg=self.bg_color) # Set root window background

        # Automatically detect base directories (folders in the current directory)
        self.BASE_DIRS = [f for f in os.listdir(".") if os.path.isdir(f) and f != "__pycache__"]
        # Placeholder for screenshots directory (update as needed)
        self.SCREENSHOTS_DIR = r"C:\Users\user\Documents\Lightshot" # IMPORTANT: Update this path to your actual screenshots directory
        self.ATTACHMENTS_DIR_NAME = "attachments"  # Name of the subfolder for image notes
        # Supported image extensions, including webp for efficiency
        self.IMAGE_EXTENSIONS = ('png', 'jpg', 'jpeg', 'webp')

        # Pagination settings for folder cards
        self.cards_per_page = 10
        self.current_card_page = 1
        self.total_card_pages = 1
        self.filtered_folders_for_pagination = [] # Stores the full list of folders after search/filter, before pagination

        # --- Top Frame: Contains Search, Base Directory Dropdown, Folder Creation, and Folder List/Cards ---
        self.top_frame = Frame(root, bg=self.bg_color, borderwidth=1, relief=tk.GROOVE, padx=5, pady=5)
        self.top_frame.pack(fill=tk.X, padx=5, pady=5)

        # Configure columns for responsive layout in top_frame
        self.top_frame.grid_columnconfigure(0, weight=1) # Search and folder creation
        self.top_frame.grid_columnconfigure(1, weight=0) # Buttons
        self.top_frame.grid_columnconfigure(2, weight=2) # Folder list/cards will take more space

        # Search Entry for filtering folders
        self.search_var = tk.StringVar()
        self.search_entry = Entry(self.top_frame, textvariable=self.search_var, font=("Arial", 14), bg='white',
                                  fg='black', insertbackground='black')
        self.search_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self.update_folder_list) # Live search filtering

        # Dropdown for selecting base directory
        self.selected_base_dir_var = tk.StringVar(root)
        self.base_dir_options = ["All"] + [os.path.basename(d) for d in self.BASE_DIRS]
        self.selected_base_dir_var.set("All") # Default to "All" directories
        
        self.base_dir_dropdown = OptionMenu(self.top_frame, self.selected_base_dir_var, *self.base_dir_options, command=self.update_folder_list)
        self.base_dir_dropdown.config(bg=self.button_bg, fg=self.button_fg, font=("Arial", 12))
        self.base_dir_dropdown["menu"].config(bg=self.button_bg, fg=self.button_fg, font=("Arial", 12))
        self.base_dir_dropdown.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        # Create Folder Input and Button
        self.new_folder_var = tk.StringVar()
        self.new_folder_entry = Entry(self.top_frame, textvariable=self.new_folder_var, font=("Arial", 14),
                                       bg='white', fg='black', insertbackground='black')
        self.new_folder_entry.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        button_style = {'bg': self.button_bg, 'fg': self.button_fg, 'font': ("Arial", 12), 'borderwidth': 1,
                        'relief': tk.RAISED, 'padx': 3, 'pady': 3}
        Button(self.top_frame, text="Create Folder", command=self.create_new_folder, **button_style).grid(row=2,
                                                                                                             column=1,
                                                                                                             padx=5,
                                                                                                             pady=5,
                                                                                                             sticky="ew")
        
        # --- View Mode Selection for Folders (List vs. Cards) ---
        self.view_mode_var = tk.StringVar(root)
        self.view_mode_options = ["List", "Cards"]
        self.view_mode_var.set("List") # Default view mode
        self.view_mode_dropdown = OptionMenu(self.top_frame, self.view_mode_var, *self.view_mode_options, command=self.switch_folder_view)
        self.view_mode_dropdown.config(bg=self.button_bg, fg=self.button_fg, font=("Arial", 12))
        self.view_mode_dropdown["menu"].config(bg=self.button_bg, fg=self.button_fg, font=("Arial", 12))
        self.view_mode_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew") # Position next to search entry

        # --- Folder Display Frame: Dynamically holds Listbox or Card Gallery ---
        self.folder_display_frame = Frame(self.top_frame, bg=self.bg_color)
        self.folder_display_frame.grid(row=0, column=2, rowspan=3, padx=5, pady=5, sticky="nsew") 
        
        # --- Folder Listbox (for 'List' view) ---
        # Added exportselection=False to prevent deselection when other widgets gain focus
        self.folder_listbox = Listbox(self.folder_display_frame, bg=self.listbox_bg, fg=self.listbox_fg, font=("Arial", 12),
                                      height=5, borderwidth=1, relief=tk.SUNKEN, exportselection=False)
        self.folder_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) # Initially packed
        self.folder_scrollbar = Scrollbar(self.folder_display_frame, orient=tk.VERTICAL)
        self.folder_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.folder_listbox.config(yscrollcommand=self.folder_scrollbar.set)
        self.folder_scrollbar.config(command=self.folder_listbox.yview)
        self.folder_listbox.bind("<ButtonRelease-1>", self.load_images)
        self.folder_listbox.bind("<<ListboxSelect>>", self.on_folder_select)

        # --- Card Gallery Container Frame (for 'Cards' view) ---
        # This frame will hold the canvas+scrollbar and the pagination controls
        self.card_gallery_container_frame = Frame(self.folder_display_frame, bg=self.bg_color)
        # Not packed initially, will be packed/unpacked by switch_folder_view

        # --- Frame for Canvas and its Scrollbar ---
        self.card_canvas_and_scrollbar_frame = Frame(self.card_gallery_container_frame, bg=self.bg_color)
        self.card_canvas_and_scrollbar_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True) # Pack at top of container

        self.card_gallery_canvas = Canvas(self.card_canvas_and_scrollbar_frame, bg=self.bg_color, highlightthickness=0)
        self.card_gallery_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) # Canvas packed LEFT within its new parent
        
        self.card_gallery_scrollbar_y = Scrollbar(self.card_canvas_and_scrollbar_frame, orient=tk.VERTICAL, command=self.card_gallery_canvas.yview)
        self.card_gallery_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y) # Scrollbar packed RIGHT next to canvas

        self.card_gallery_canvas.configure(yscrollcommand=self.card_gallery_scrollbar_y.set)
        self.card_gallery_canvas.bind("<Configure>", self.configure_card_gallery_canvas)
        
        self.card_gallery_inner_frame = Frame(self.card_gallery_canvas, bg=self.bg_color)
        self.card_gallery_inner_frame.bind("<Configure>", lambda e: self.card_gallery_canvas.configure(scrollregion=self.card_gallery_canvas.bbox("all")))
        self.card_gallery_canvas.create_window((0, 0), window=self.card_gallery_inner_frame, anchor="nw")
        
        # Configure columns for the inner frame to allow multiple columns of cards
        self.card_gallery_inner_frame.grid_columnconfigure(0, weight=1)
        self.card_gallery_inner_frame.grid_columnconfigure(1, weight=1)
        self.card_gallery_inner_frame.grid_columnconfigure(2, weight=1) # Assuming num_columns = 3


        # --- Pagination Controls for Card Gallery ---
        self.card_pagination_frame = Frame(self.card_gallery_container_frame, bg=self.bg_color)
        self.card_pagination_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5) # Pack at bottom of container

        self.prev_page_button = Button(self.card_pagination_frame, text="Previous", command=self.go_to_prev_card_page, **button_style)
        self.prev_page_button.pack(side=tk.LEFT, padx=5)

        self.page_info_label = Label(self.card_pagination_frame, text="Page 1/1", bg=self.bg_color, fg=self.fg_color, font=("Arial", 10))
        self.page_info_label.pack(side=tk.LEFT, padx=5)

        self.next_page_button = Button(self.card_pagination_frame, text="Next", command=self.go_to_next_card_page, **button_style)
        self.next_page_button.pack(side=tk.LEFT, padx=5)

        self.card_buttons = [] # Store card buttons to clear them later
        self.card_thumbnail_size = (200, 150) # Size for folder card thumbnails

        # --- Navigation Frame: Buttons for image navigation and actions ---
        self.nav_frame = Frame(root, bg=self.bg_color, borderwidth=1, relief=tk.GROOVE)
        self.nav_frame.pack(fill=tk.X, pady=5, padx=5)

        # Button Styling (reused for consistency)
        button_style = {'bg': self.button_bg, 'fg': self.button_fg, 'font': ("Arial", 12), 'borderwidth': 1,
                        'relief': tk.RAISED, 'padx': 3, 'pady': 3}

        # Navigation Buttons
        Button(self.nav_frame, text="Previous", command=self.prev_image, **button_style).pack(side=tk.LEFT, padx=3)
        Button(self.nav_frame, text="Next", command=self.next_image, **button_style).pack(side=tk.LEFT, padx=3)
        Button(self.nav_frame, text="Go to Image", command=self.go_to_image, **button_style).pack(side=tk.LEFT, padx=3)

        # Action Buttons
        Button(self.nav_frame, text="Edit", command=self.edit_image, **button_style).pack(side=tk.RIGHT, padx=3)
        self.ocr_button = Button(self.nav_frame, text="OCR", command=self.open_ocr_popup, **button_style)
        self.ocr_button.pack(side=tk.LEFT, padx=3)
        self.tag_button = Button(self.nav_frame, text="Tags", command=self.open_tag_editor, **button_style)
        self.tag_button.pack(side=tk.LEFT, padx=3)
        self.notes_button = Button(self.nav_frame, text="Notes", command=self.open_notes_editor, **button_style)
        self.notes_button.pack(side=tk.LEFT, padx=3)
        self.image_note_button = Button(self.nav_frame, text="Note", command=self.open_image_note_editor, **button_style)
        self.image_note_button.pack(side=tk.LEFT, padx=3)

        self.gallery_button = Button(self.nav_frame, text="Gallery", command=self.toggle_gallery, **button_style)
        self.gallery_button.pack(side=tk.LEFT, padx=3)
        Button(self.nav_frame, text="Explorer", command=self.open_in_explorer, **button_style).pack(side=tk.LEFT, padx=3)
        Button(self.nav_frame, text="Copy Path", command=self.copy_path_to_clipboard, **button_style).pack(side=tk.LEFT, padx=3)
        self.add_images_button = Button(self.nav_frame, text="Add", command=self.add_images_to_selected_folder, **button_style)
        self.add_images_button.pack(side=tk.LEFT, padx=3)
        self.resize_button = Button(self.nav_frame, text="Resize", command=self.resize_images_in_current_folder, **button_style)
        self.resize_button.pack(side=tk.LEFT, padx=3)

        # Info Labels for image count and current index
        label_style = {'bg': self.bg_color, 'fg': self.fg_color, 'font': ("Arial", 12)}
        self.image_count_label = Label(self.nav_frame, text="T: 0", **label_style)
        self.image_count_label.pack(side=tk.LEFT, padx=3)
        self.selected_image_label = Label(self.nav_frame, text="s: 0/0", **label_style)
        self.selected_image_label.pack(side=tk.LEFT, padx=3)

        # --- Main Frame: Contains Image Canvas and Thumbnail Gallery ---
        self.main_frame = Frame(root, bg=self.bg_color)
        self.main_frame.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        # Image Canvas for displaying the main image
        self.image_canvas = Canvas(self.main_frame, bg=self.bg_color, highlightthickness=0, borderwidth=1, relief=tk.SOLID)
        self.image_canvas.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=5, pady=5) # Dock to the Right

        # Gallery Frame (Initially Hidden) for image thumbnails within a folder
        self.gallery_frame = Frame(self.main_frame, bg=self.bg_color)
        self.gallery_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        self.gallery_frame.pack_forget() # Initially hidden

        # Gallery Search Frame and Entry for filtering images by attachment notes
        self.gallery_search_frame = Frame(self.gallery_frame, bg=self.bg_color)
        self.gallery_search_frame.pack(fill=tk.X, padx=5, pady=5)
        self.gallery_search_var = tk.StringVar()
        self.gallery_search_entry = Entry(self.gallery_search_frame, textvariable=self.gallery_search_var,
                                            font=("Arial", 12), bg='white', fg='black', insertbackground='black')
        self.gallery_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.gallery_search_entry.bind("<KeyRelease>", self.update_gallery_search)

        self.gallery_canvas = Canvas(self.gallery_frame, bg=self.bg_color, highlightthickness=0)
        self.gallery_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.gallery_scrollbar_y = Scrollbar(self.gallery_frame, orient=tk.VERTICAL, command=self.gallery_canvas.yview)
        self.gallery_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.gallery_canvas.configure(yscrollcommand=self.gallery_scrollbar_y.set)
        self.gallery_canvas.bind("<Configure>", self.configure_gallery_canvas)
        self.gallery_inner_frame = Frame(self.gallery_canvas, bg=self.bg_color)
        self.gallery_canvas.create_window((0, 0), window=self.gallery_inner_frame, anchor="nw")

        # Bind resize event to image canvas
        self.image_canvas.bind("<Configure>", self.resize_image)

        # Bind mouse events for zooming and panning
        self.image_canvas.bind("<MouseWheel>", self.zoom_with_scroll)
        self.image_canvas.bind("<Button-4>", self.zoom_with_scroll) # Linux/macOS scroll up
        self.image_canvas.bind("<Button-5>", self.zoom_with_scroll) # Linux/macOS scroll down

        self.image_canvas.bind("<ButtonPress-1>", self.start_pan)
        self.image_canvas.bind("<B1-Motion>", self.pan_image)
        self.image_canvas.bind("<ButtonRelease-1>", self.end_pan)

        # OCR Selection Bindings - CTRL + Left Click to select region for OCR
        self.image_canvas.bind("<Control-ButtonPress-1>", self.start_selection)
        self.image_canvas.bind("<Control-B1-Motion>", self.update_selection)
        self.image_canvas.bind("<Control-ButtonRelease-1>", self.end_selection)

        # Image state variables
        self.image_paths = []           # List of full paths to images in the current folder
        self.current_index = 0          # Index of the currently displayed image
        self.current_image = None       # PhotoImage object for the current image
        self.original_image = None      # PIL Image object for the original (unscaled) image
        self.canvas_image_id = None     # ID of the image item on the canvas
        self.zoom_level = 1.0           # Current zoom level of the image
        self.image_x = 0                # X offset for image panning
        self.image_y = 0                # Y offset for image panning
        self.mouse_x = 0                # Current mouse X position on canvas
        self.mouse_y = 0                # Current mouse Y position on canvas
        self.pan_start_x = None         # Starting X for panning
        self.pan_start_y = None         # Starting Y for panning

        # OCR selection variables
        self.selection_start_x = None
        self.selection_start_y = None
        self.selection_end_x = None
        self.selection_end_y = None
        self.selection_rectangle = None # ID of the drawn selection rectangle

        # Tag, Notes, OCR window references
        self.current_tags = []
        self.tag_window = None
        self.ocr_window = None
        self.ocr_text_widget = None
        self.notes_window = None
        self.notes_text = None # Added for direct access in RTL function
        self.image_note_window = None
        self.image_note_text = None # Added for direct access in RTL function

        # Gallery variables
        self.gallery_images = [] # List of image filenames in the current folder for the gallery
        self.gallery_index = 0
        self.thumbnail_size = (128, 128) # Size for image gallery thumbnails
        self.gallery_visible = False  # Flag for gallery visibility
        self.gallery_buttons = []  # Store image gallery buttons
        self.selected_gallery_button = None  # Track the selected image gallery button
        self.attachment_texts = {} # Stores text content from attachment .txt files for searching

        self.image_canvas.bind("<Motion>", self.update_mouse_position) # Update mouse position on canvas

        self.load_folders() # Initial load of folders
        self.switch_folder_view() # Set initial view mode based on self.view_mode_var

        # Bind arrow keys for image navigation (global bindings)
        root.bind("<Left>", self.prev_image)
        root.bind("<Right>", self.next_image)
        root.bind("<Control-e>", self.edit_image) # Ctrl+E to edit image

        # Create OCR popup and show it immediately on startup
        self.open_ocr_popup(init_call=True)

    def load_folders(self):
        """
        Loads all subfolders from BASE_DIRS and populates `self.all_folders`.
        Then calls `update_folder_list` to refresh the display.
        """
        self.all_folders = []
        for base_dir in self.BASE_DIRS:
            # Determine if base_dir is absolute or relative and get its full path
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)

            if os.path.exists(full_base_dir):
                for item in os.listdir(full_base_dir):
                    item_path = os.path.join(full_base_dir, item)
                    if os.path.isdir(item_path):
                        # Append subfolders, preserving their parent directory for context (e.g., "BaseDir1/SubfolderA")
                        self.all_folders.append(os.path.join(os.path.basename(full_base_dir), item))

        self.all_folders = sorted(self.all_folders, key=natural_sort_key) # Sort folders naturally
        self.update_folder_list() # Update the listbox / card gallery

    def update_folder_list(self, event=None):
        """
        Filters and updates the folder listbox (or triggers card gallery update)
        based on search text and selected base directory.
        """
        search_text = self.search_var.get().lower()
        search_words = search_text.split()
        selected_dropdown_dir = self.selected_base_dir_var.get()

        # Clear current listbox
        self.folder_listbox.delete(0, tk.END)

        filtered_folders = []
        for folder in self.all_folders:
            parent_dir, folder_name = os.path.split(folder)

            # Filter by selected base directory from dropdown
            if selected_dropdown_dir != "All" and parent_dir != selected_dropdown_dir:
                continue

            # Construct the full path to the folder to check for tags.txt
            full_folder_path = None
            for base_dir_check in self.BASE_DIRS:
                if os.path.basename(base_dir_check) == parent_dir:
                    full_base_dir = base_dir_check if os.path.isabs(base_dir_check) else os.path.abspath(base_dir_check)
                    full_folder_path = os.path.join(full_base_dir, folder_name)
                    break

            if not full_folder_path:
                continue

            tag_match = False
            tags_file_path = os.path.join(full_folder_path, "tags.txt")
            if os.path.exists(tags_file_path):
                try:
                    with open(tags_file_path, "r") as f:
                        tags = [tag.strip().lower() for tag in f.read().splitlines() if tag.strip()]
                        tag_match = all(word in tags for word in search_words)
                except Exception as e:
                    print(f"Error reading tags for {folder_name}: {e}")
            
            # Check if folder name matches search words
            name_match = all(word in folder_name.lower() for word in search_words)

            if tag_match or name_match:
                filtered_folders.append(folder_name)
        
        self.filtered_folders_for_pagination = filtered_folders # Store for pagination
        # If in List view, populate the listbox directly
        if self.view_mode_var.get() == "List":
            for folder_name in filtered_folders:
                self.folder_listbox.insert(tk.END, folder_name)
        elif self.view_mode_var.get() == "Cards":
            # If in Cards view, populate the card gallery with filtered folders
            self.current_card_page = 1 # Reset to first page on new filter
            self.populate_card_gallery(self.filtered_folders_for_pagination, self.current_card_page)

    def switch_folder_view(self, event=None):
        """
        Switches between 'List' and 'Cards' view for folders.
        """
        current_mode = self.view_mode_var.get()

        # Clear and hide both display types
        self.folder_listbox.pack_forget()
        self.folder_scrollbar.pack_forget() # Also hide the scrollbar
        # Change: Use the new container frame for packing/forgetting
        self.card_gallery_container_frame.pack_forget() 
        
        for button in self.card_buttons: # Ensure old cards are destroyed
            button.destroy()
        self.card_buttons = []

        # The pagination frame is now part of card_gallery_container_frame, so no separate forget needed here.
        # self.card_pagination_frame.pack_forget() 

        if current_mode == "List":
            self.folder_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.folder_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.update_folder_list() # Re-populate listbox
        elif current_mode == "Cards":
            # Change: Pack the new container frame
            self.card_gallery_container_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            # The scrollbar is inside card_canvas_and_scrollbar_frame, which is packed into card_gallery_container_frame
            # No need to pack scrollbar directly here again.
            
            self.current_card_page = 1 # Reset to first page when switching to cards view
            self.populate_card_gallery(self.filtered_folders_for_pagination, self.current_card_page) 
            self.update_pagination_buttons()

    def populate_card_gallery(self, folders_to_display, page_number):
        """
        Populates the card gallery with folder cards for the given page.
        Each card displays the folder name and the first image as background,
        prioritizing 'cover.webp' or 'cover.png'.
        """
        # Clear existing cards
        for button in self.card_buttons:
            button.destroy()
        self.card_buttons = []

        total_folders = len(folders_to_display)
        self.total_card_pages = (total_folders + self.cards_per_page - 1) // self.cards_per_page
        self.current_card_page = max(1, min(page_number, self.total_card_pages)) # Ensure page number is valid

        start_index = (self.current_card_page - 1) * self.cards_per_page
        end_index = min(start_index + self.cards_per_page, total_folders)
        
        folders_on_page = folders_to_display[start_index:end_index]

        num_columns = 3 # Number of columns for the card layout
        row = 0
        col = 0

        for folder_name in folders_on_page:
            full_folder_path = None
            # Find the actual full path for the folder name
            for base_dir in self.BASE_DIRS:
                full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
                potential_path = os.path.join(full_base_dir, folder_name)
                if os.path.exists(potential_path) and os.path.isdir(potential_path):
                    full_folder_path = potential_path
                    break
            
            if not full_folder_path:
                print(f"Error: Could not find full path for folder name {folder_name}")
                continue

            card_image_path = None
            # Prioritize cover.webp or cover.png
            for cover_file in ['cover.webp', 'cover.png']:
                potential_cover_path = os.path.join(full_folder_path, cover_file)
                if os.path.exists(potential_cover_path):
                    card_image_path = potential_cover_path
                    break
            
            # Fallback to the first image if no cover found
            if not card_image_path:
                images_in_folder = sorted([f for f in os.listdir(full_folder_path) if
                                           f.lower().endswith(self.IMAGE_EXTENSIONS)], key=natural_sort_key)
                if images_in_folder:
                    card_image_path = os.path.join(full_folder_path, images_in_folder[0])

            photo = None
            if card_image_path:
                try:
                    img = Image.open(card_image_path)
                    img.thumbnail(self.card_thumbnail_size) # Resize for card background
                    photo = ImageTk.PhotoImage(img)
                except Exception as e:
                    print(f"Error loading image for card {folder_name} from {card_image_path}: {e}")
                    photo = None # Fallback to no image if error
            
            # If no image is found or loaded, create a blank image as a placeholder
            if photo is None:
                placeholder_img = Image.new('RGB', self.card_thumbnail_size, color = 'lightgrey')
                draw = ImageDraw.Draw(placeholder_img)
                text = f"No Image\n({folder_name})"
                try:
                    font = ImageFont.truetype("arial.ttf", 20)
                except IOError:
                    font = ImageFont.load_default()
                
                text_bbox = draw.textbbox((0,0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                x = (self.card_thumbnail_size[0] - text_width) / 2
                y = (self.card_thumbnail_size[1] - text_height) / 2
                draw.text((x, y), text, fill="black", font=font, align="center")
                photo = ImageTk.PhotoImage(placeholder_img)


            # Create a frame for the card to layer image and text
            card_frame = Frame(self.card_gallery_inner_frame, bg=self.listbox_bg, relief=tk.RAISED, borderwidth=2)
            card_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            # Create a label for the image background
            image_display_label = Label(card_frame, image=photo, bg=self.listbox_bg)
            image_display_label.image = photo # Keep a reference to prevent garbage collection
            image_display_label.pack(fill=tk.BOTH, expand=True)

            # Create a label for the folder name, placed BELOW the image, within the card_frame
            folder_name_label = Label(card_frame, text=folder_name, bg=self.button_bg, fg="white", font=("Arial", 10, "bold"),
                                      wraplength=self.card_thumbnail_size[0] - 20)
            folder_name_label.pack(pady=(0,5), fill=tk.X)

            # Bind click event to the entire card frame and its child elements for robustness
            card_frame.bind("<Button-1>", lambda e, name=folder_name: self.load_folder_from_card(name))
            image_display_label.bind("<Button-1>", lambda e, name=folder_name: self.load_folder_from_card(name))
            folder_name_label.bind("<Button-1>", lambda e, name=folder_name: self.load_folder_from_card(name))

            self.card_buttons.append(card_frame) # Store the card frame (acting as a button)

            col += 1
            if col >= num_columns:
                col = 0
                row += 1
        
        # After populating, ensure the inner frame's size is updated for scrolling
        self.card_gallery_canvas.update_idletasks() # Force redraw
        self.card_gallery_canvas.configure(scrollregion=self.card_gallery_canvas.bbox("all"))
        self.update_pagination_buttons() # Update button states and page info

    def configure_card_gallery_canvas(self, event):
        """Configures the scroll region for the card gallery canvas."""
        self.card_gallery_canvas.configure(scrollregion=self.card_gallery_canvas.bbox("all"))

    def update_pagination_buttons(self):
        """Updates the state of pagination buttons and page info label."""
        self.prev_page_button.config(state=tk.NORMAL if self.current_card_page > 1 else tk.DISABLED)
        self.next_page_button.config(state=tk.NORMAL if self.current_card_page < self.total_card_pages else tk.DISABLED)
        self.page_info_label.config(text=f"Page {self.current_card_page}/{self.total_card_pages}")

    def go_to_prev_card_page(self):
        """Navigates to the previous page of folder cards."""
        if self.current_card_page > 1:
            self.current_card_page -= 1
            self.populate_card_gallery(self.filtered_folders_for_pagination, self.current_card_page)

    def go_to_next_card_page(self):
        """Navigates to the next page of folder cards."""
        if self.current_card_page < self.total_card_pages:
            self.current_card_page += 1
            self.populate_card_gallery(self.filtered_folders_for_pagination, self.current_card_page)


    def load_folder_from_card(self, folder_name):
        """
        Loads images for a folder when its card is clicked.
        This simulates selecting the folder from the listbox.
        """
        # Find the full path for the given folder_name
        full_folder_path = None
        for base_dir in self.BASE_DIRS:
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
            potential_path = os.path.join(full_base_dir, folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                full_folder_path = potential_path
                break
        
        if not full_folder_path:
            messagebox.showerror("Error", f"Could not find full path for folder: {folder_name}")
            return

        self.image_paths = sorted([os.path.join(full_folder_path, f) for f in os.listdir(full_folder_path) if
                                   f.lower().endswith(self.IMAGE_EXTENSIONS)], key=natural_sort_key)

        if self.image_paths:
            self.current_index = 0
            self.update_image_count()
            self.show_image()
            self.load_tags()
            self.load_notes()
            self.load_image_note()
            # Simulate selection in listbox for consistent state (optional, but good practice if other functions rely on it)
            try:
                listbox_index = self.folder_listbox.get(0, tk.END).index(folder_name)
                self.folder_listbox.selection_clear(0, tk.END)
                self.folder_listbox.selection_set(listbox_index)
                self.folder_listbox.activate(listbox_index)
            except ValueError:
                # Folder might not be in the current listbox view if filtered
                pass
            self.load_gallery_images(full_folder_path)
        else:
            self.clear_image()
            self.update_image_count()
            self.gallery_images = []
            self.load_gallery_images(full_folder_path)


    def load_images(self, event=None):
        """
        Loads images from the currently selected folder in the listbox.
        """
        selected_folder_index = self.folder_listbox.curselection()
        if not selected_folder_index:
            return

        selected_folder_name = self.folder_listbox.get(selected_folder_index[0])

        full_folder_path = None
        for base_dir in self.BASE_DIRS:
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
            potential_path = os.path.join(full_base_dir, selected_folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                full_folder_path = potential_path
                break

        if not full_folder_path:
            print(f"Error: Could not find full path for folder name {selected_folder_name}")
            return

        self.image_paths = sorted([os.path.join(full_folder_path, f) for f in os.listdir(full_folder_path) if
                                   f.lower().endswith(self.IMAGE_EXTENSIONS)], key=natural_sort_key)

        if self.image_paths:
            self.current_index = 0
            self.update_image_count()
            self.show_image()
            self.load_tags()
            self.load_notes()
            self.load_image_note()
            self.folder_listbox.selection_set(selected_folder_index)
            self.load_gallery_images(full_folder_path)
        else:
            self.clear_image()
            self.update_image_count()
            self.folder_listbox.selection_set(selected_folder_index)
            self.gallery_images = []
            self.load_gallery_images(full_folder_path)

    def show_image(self):
        """Displays the image at `self.current_index` on the canvas."""
        if self.image_paths:
            try:
                image_path = self.image_paths[self.current_index]
                self.original_image = Image.open(image_path)
                self.zoom_level = 1.0
                self.image_x = 0
                self.image_y = 0
                self.resize_image()
                self.update_selected_image_label()
                self.reset_selection()
                self.perform_ocr()
                self.load_image_note()
                self.update_gallery_selection()
            except IndexError:
                print("IndexError in show_image: current_index is out of range.")
                if self.image_paths:
                    self.current_index = 0
                    self.show_image()
                else:
                    self.clear_image()
            except Exception as e:
                print(f"Error displaying image: {e}")
                self.clear_image()

    def clear_image(self):
        """Clears the image from the canvas."""
        if self.canvas_image_id:
            self.image_canvas.delete(self.canvas_image_id)
            self.canvas_image_id = None
        self.current_image = None
        self.original_image = None

    def next_image(self, event=None):
        """Navigates to the next image in the current folder."""
        if self.image_paths:
            self.current_index = (self.current_index + 1) % len(self.image_paths)
            self.show_image()
            self.load_tags()
            self.load_notes()
            self.load_image_note()

    def prev_image(self, event=None):
        """Navigates to the previous image in the current folder."""
        if self.image_paths:
            self.current_index = (self.current_index - 1) % len(self.image_paths)
            self.show_image()
            self.load_tags()
            self.load_notes()
            self.load_image_note()

    def go_to_image(self):
        """Prompts user to go to a specific image by number."""
        if not self.image_paths:
            return

        num_images = len(self.image_paths)
        input_value = simpledialog.askinteger("Go to Image", f"Enter image number (1-{num_images}):",
                                            parent=self.root, minvalue=1, maxvalue=num_images)
        if input_value is not None:
            target_index = input_value - 1
            if 0 <= target_index < num_images:
                self.current_index = target_index
                self.show_image()
                self.load_tags()
                self.load_notes()
                self.load_image_note()

    def edit_image(self, event=None):
        """Opens the current image in MS Paint (Windows only)."""
        if self.image_paths:
            try:
                # Use 'start' command for broader compatibility on Windows to open with default app
                subprocess.Popen(['start', self.image_paths[self.current_index]], shell=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open image for editing: {e}")

    def update_image_count(self):
        """Updates the total image count label."""
        total_images = len(self.image_paths)
        self.image_count_label.config(text=f"T: {total_images}")
        self.update_selected_image_label()

    def update_selected_image_label(self):
        """Updates the current image index label."""
        if self.image_paths:
            self.selected_image_label.config(text=f"s: {self.current_index + 1}/{len(self.image_paths)}")
        else:
            self.selected_image_label.config(text="s: 0/0")

    def update_zoom(self):
        """Applies the current zoom level to the image and updates the canvas."""
        if self.original_image:
            try:
                width = int(self.original_image.width * self.zoom_level)
                height = int(self.original_image.height * self.zoom_level)
                resized_image = self.original_image.resize((width, height), Image.LANCZOS)
                self.current_image = ImageTk.PhotoImage(resized_image)
                self.update_image()
            except Exception as e:
                print(f"Error zooming image: {e}")
                messagebox.showerror("Error", f"Zoom error: {e}")

    def zoom_with_scroll(self, event):
        """Handles zooming in/out based on mouse scroll wheel."""
        if self.original_image:
            zoom_factor = 1.0
            if event.num == 4 or event.delta > 0: # Scroll up
                zoom_factor = 1.1
            elif event.num == 5 or event.delta < 0: # Scroll down
                zoom_factor = 0.9
            
            if zoom_factor != 1.0:
                self.zoom_level *= zoom_factor
                self.zoom_level = max(0.1, min(self.zoom_level, 10.0)) # Limit zoom range
                self.update_zoom()

    def update_image(self):
        """Redraws the image on the canvas with current position and zoom."""
        if self.current_image:
            canvas_width = self.image_canvas.winfo_width()
            canvas_height = self.image_canvas.winfo_height()

            width = self.current_image.width()
            height = self.current_image.height()

            # Calculate center offset plus pan offset
            x_offset = (canvas_width - width) // 2 + self.image_x
            y_offset = (canvas_height - height) // 2 + self.image_y

            self.image_canvas.delete(self.canvas_image_id) # Delete old image
            self.canvas_image_id = self.image_canvas.create_image(x_offset, y_offset, anchor=tk.NW,
                                                                   image=self.current_image)
            self.image_canvas.lower(self.canvas_image_id) # Ensure image is below selection rectangle

    def start_pan(self, event):
        """Initializes panning when mouse button 1 is pressed."""
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def pan_image(self, event):
        """Updates image position while mouse is dragged (panning)."""
        if self.pan_start_x is not None and self.pan_start_y is not None:
            delta_x = event.x - self.pan_start_x
            delta_y = event.y - self.pan_start_y

            self.image_x += delta_x
            self.image_y += delta_y

            self.pan_start_x = event.x
            self.pan_start_y = event.y

            self.update_image()

    def end_pan(self, event):
        """Resets pan start coordinates when mouse button 1 is released."""
        self.pan_start_x = None
        self.pan_start_y = None

    def update_mouse_position(self, event):
        """Updates internal mouse coordinates (currently not used for display)."""
        self.mouse_x = event.x
        self.mouse_y = event.y

    def start_selection(self, event):
        """Starts drawing a selection rectangle for OCR."""
        self.selection_start_x = self.image_canvas.canvasx(event.x) # Convert window coords to canvas coords
        self.selection_start_y = self.image_canvas.canvasy(event.y)

        if self.selection_rectangle:
            self.image_canvas.delete(self.selection_rectangle)
            self.selection_rectangle = None

    def update_selection(self, event):
        """Updates the selection rectangle as the mouse is dragged."""
        cur_x = self.image_canvas.canvasx(event.x)
        cur_y = self.image_canvas.canvasy(event.y)

        if self.selection_rectangle:
            self.image_canvas.delete(self.selection_rectangle)

        self.selection_rectangle = self.image_canvas.create_rectangle(
            self.selection_start_x, self.selection_start_y, cur_x, cur_y,
            outline="red", width=2
        )

    def end_selection(self, event):
        """Ends the selection and triggers OCR on the selected region."""
        self.selection_end_x = self.image_canvas.canvasx(event.x)
        self.selection_end_y = self.image_canvas.canvasy(event.y)
        self.perform_ocr() # Perform OCR on the selected region

    def reset_selection(self):
        """Removes the selection rectangle from the canvas."""
        self.selection_start_x = None
        self.selection_start_y = None
        self.selection_end_x = None
        self.selection_end_y = None
        if self.selection_rectangle:
            self.image_canvas.delete(self.selection_rectangle)
            self.selection_rectangle = None

    def enhance_image(self, image):
        """Applies grayscale, contrast, and sharpness enhancements for better OCR."""
        enhanced_image = image.convert('L') # Convert to grayscale
        enhancer = ImageEnhance.Contrast(enhanced_image)
        enhanced_image = enhancer.enhance(2) # Increase contrast
        enhancer = ImageEnhance.Sharpness(enhanced_image)
        enhanced_image = enhancer.enhance(2) # Increase sharpness
        return enhanced_image

    def open_tag_editor(self):
        """Opens a Toplevel window for editing folder tags."""
        if self.tag_window and tk.Toplevel.winfo_exists(self.tag_window):
            self.tag_window.focus()
            return

        self.tag_window = Toplevel(self.root)
        self.tag_window.title("Edit Tags")
        self.tag_window.geometry("400x300")
        self.tag_window.attributes('-topmost', True) # Keep on top

        self.tag_text = Text(self.tag_window, bg='white', fg='black', font=("Arial", 12))
        self.tag_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tag_scrollbar = Scrollbar(self.tag_window, orient=tk.VERTICAL)
        self.tag_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tag_text.config(yscrollcommand=self.tag_scrollbar.set)
        self.tag_scrollbar.config(command=self.tag_text.yview)

        self.tag_text.bind("<KeyRelease>", self.auto_save_tags) # Auto-save on key release

        self.load_tags_into_text() # Load existing tags

        self.tag_window.protocol("WM_DELETE_WINDOW", self.on_tag_window_close)

    def load_tags_into_text(self):
        """Inserts `self.current_tags` into the tag editor text widget."""
        self.tag_text.delete("1.0", tk.END)
        self.tag_text.insert("1.0", "\n".join(self.current_tags))

    def auto_save_tags(self, event=None):
        """Automatically saves tags to 'tags.txt' in the current folder."""
        selected_folder_index = self.folder_listbox.curselection()
        if not selected_folder_index:
            return

        selected_folder_name = self.folder_listbox.get(selected_folder_index[0])

        full_folder_path = None
        for base_dir in self.BASE_DIRS:
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
            potential_path = os.path.join(full_base_dir, selected_folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                full_folder_path = potential_path
                break

        if not full_folder_path:
            print(f"Error: Could not find full path for folder name {selected_folder_name}")
            return

        tags_file_path = os.path.join(full_folder_path, "tags.txt")

        if self.tag_window and tk.Toplevel.winfo_exists(self.tag_window):
            tags = self.tag_text.get("1.0", tk.END).strip()
        else:
            return

        try:
            with open(tags_file_path, "w") as f:
                f.write(tags)
            self.current_tags = [tag.strip() for tag in tags.splitlines() if tag.strip()]
        except Exception as e:
            print(f"Error saving tags automatically: {e}")

    def load_tags(self):
        """Loads tags from 'tags.txt' in the current folder."""
        selected_folder_index = self.folder_listbox.curselection()
        if not selected_folder_index:
            return

        selected_folder_name = self.folder_listbox.get(selected_folder_index[0])

        full_folder_path = None
        for base_dir in self.BASE_DIRS:
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
            potential_path = os.path.join(full_base_dir, selected_folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                full_folder_path = potential_path
                break

        if not full_folder_path:
            print(f"Error: Could not find full path for folder name {selected_folder_name}")
            return

        tags_file_path = os.path.join(full_folder_path, "tags.txt")

        self.current_tags = []
        if os.path.exists(tags_file_path):
            try:
                with open(tags_file_path, "r") as f:
                    tags = f.read().strip()
                    self.current_tags = [tag.strip() for tag in tags.splitlines() if tag.strip()]
            except Exception as e:
                print(f"Error loading tags: {e}")

        if self.tag_window and tk.Toplevel.winfo_exists(self.tag_window):
            self.load_tags_into_text()

    def on_tag_window_close(self):
        """Destroys the tag editor window when closed."""
        self.tag_window.destroy()
        self.tag_window = None

    def on_folder_select(self, event=None):
        """Callback when a folder is selected in the listbox."""
        self.load_tags()
        self.load_notes()
        self.load_image_note()
        self.load_images() # Auto load images for selected folder

    def open_ocr_popup(self, init_call=False):
        """Opens a Toplevel window to display extracted OCR text."""
        if self.ocr_window and tk.Toplevel.winfo_exists(self.ocr_window):
            self.ocr_window.focus()
            return

        self.ocr_window = Toplevel(self.root)
        self.ocr_window.title("Extracted Text (OCR)")
        self.ocr_window.geometry("600x400")
        self.ocr_window.attributes('-topmost', True)

        self.ocr_text_widget = Text(self.ocr_window, bg='white', fg='black', font=("Arial", 12))
        self.ocr_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.ocr_scrollbar = Scrollbar(self.ocr_window, orient=tk.VERTICAL)
        self.ocr_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ocr_text_widget.config(yscrollcommand=self.ocr_scrollbar.set)
        self.ocr_scrollbar.config(command=self.ocr_text_widget.yview)

        # Do not close on startup if init_call is True
        if not init_call:
            self.ocr_window.protocol("WM_DELETE_WINDOW", self.on_ocr_window_close)

    def perform_ocr(self):
        """Performs OCR on the selected region of the current image."""
        if not self.original_image:
            if self.ocr_window and tk.Toplevel.winfo_exists(self.ocr_window):
                self.ocr_text_widget.delete("1.0", tk.END)
            return

        # Ensure there is a valid selection before performing OCR
        if not all([self.selection_start_x, self.selection_start_y, self.selection_end_x, self.selection_end_y]):
            if self.ocr_window and tk.Toplevel.winfo_exists(self.ocr_window):
                self.ocr_text_widget.delete("1.0", tk.END)
                self.ocr_text_widget.insert("1.0", "Select a region for OCR.") # Added message for clarity
            return

        # Get selection coordinates relative to the canvas
        x0 = min(self.selection_start_x, self.selection_end_x)
        y0 = min(self.selection_start_y, self.selection_end_y)
        x1 = max(self.selection_start_x, self.selection_end_x)
        y1 = max(self.selection_start_y, self.selection_end_y)
        
        try:
            # Calculate image's actual position on canvas relative to its top-left
            # This is needed to map canvas selection to original image pixels
            img_width_on_canvas = self.original_image.width * self.zoom_level
            img_height_on_canvas = self.original_image.height * self.zoom_level
            canvas_width = self.image_canvas.winfo_width()
            canvas_height = self.image_canvas.winfo_height()

            # The current image_x/image_y are *additional* offsets from the centered position
            # So, the image's top-left on the canvas is:
            # (canvas_width - img_width_on_canvas) / 2 + self.image_x
            # (canvas_height - img_height_on_canvas) / 2 + self.image_y
            
            x_offset_on_canvas = (canvas_width - img_width_on_canvas) / 2 + self.image_x
            y_offset_on_canvas = (canvas_height - img_height_on_canvas) / 2 + self.image_y

            # Convert canvas selection coordinates to image pixel coordinates
            # (selected_canvas_coord - image_canvas_offset) / zoom_level
            img_x0 = max(0, (x0 - x_offset_on_canvas) / self.zoom_level)
            img_y0 = max(0, (y0 - y_offset_on_canvas) / self.zoom_level)
            img_x1 = min(self.original_image.width, (x1 - x_offset_on_canvas) / self.zoom_level)
            img_y1 = min(self.original_image.height, (y1 - y_offset_on_canvas) / self.zoom_level)

            # Ensure coordinates are integers for cropping
            img_x0, img_y0, img_x1, img_y1 = int(img_x0), int(img_y0), int(img_x1), int(img_y1)

            # Ensure valid crop box (width and height > 0)
            if img_x1 <= img_x0 or img_y1 <= img_y0:
                print("OCR selection is too small or invalid.")
                if self.ocr_window and tk.Toplevel.winfo_exists(self.ocr_window):
                    self.ocr_text_widget.delete("1.0", tk.END)
                    self.ocr_text_widget.insert("1.0", "Invalid selection for OCR (too small).")
                return

            cropped_image = self.original_image.crop((img_x0, img_y0, img_x1, img_y1))
            enhanced_image = self.enhance_image(cropped_image)

            # Set Tesseract executable path (IMPORTANT: update this to your installation)
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
            text = pytesseract.image_to_string(enhanced_image)

            if self.ocr_window and tk.Toplevel.winfo_exists(self.ocr_window):
                self.ocr_text_widget.delete("1.0", tk.END)
                self.ocr_text_widget.insert("1.0", text)

        except Exception as e:
            print(f"OCR Error: {e}")
            if self.ocr_window and tk.Toplevel.winfo_exists(self.ocr_window):
                self.ocr_text_widget.delete("1.0", tk.END)
                self.ocr_text_widget.insert("1.0", f"Error during OCR: {e}")

    def on_ocr_window_close(self):
        """Destroys the OCR window when closed."""
        if self.ocr_window:
            self.ocr_window.destroy()
            self.ocr_window = None

    def open_notes_editor(self):
        """Opens a Toplevel window for editing folder-level notes."""
        if self.notes_window and tk.Toplevel.winfo_exists(self.notes_window):
            self.notes_window.focus()
            return

        self.notes_window = Toplevel(self.root)
        self.notes_window.title("Edit Notes")
        self.notes_window.geometry("600x400") # Increased size for toolbar
        self.notes_window.attributes('-topmost', True)

        # Toolbar Frame
        toolbar_frame = Frame(self.notes_window, bd=1, relief=tk.RAISED, bg=self.bg_color)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)

        # Button Styling for toolbar
        toolbar_button_style = {'bg': self.button_bg, 'fg': self.button_fg, 'font': ("Arial", 10), 'borderwidth': 1,
                                'relief': tk.RAISED, 'padx': 2, 'pady': 2}

        # Toolbar Buttons
        Button(toolbar_frame, text="B", command=lambda: self.apply_format(self.notes_text, "bold"), **toolbar_button_style).pack(side=tk.LEFT, padx=1, pady=1)
        Button(toolbar_frame, text="I", command=lambda: self.apply_format(self.notes_text, "italic"), **toolbar_button_style).pack(side=tk.LEFT, padx=1, pady=1)
        Button(toolbar_frame, text="U", command=lambda: self.apply_format(self.notes_text, "underline"), **toolbar_button_style).pack(side=tk.LEFT, padx=1, pady=1)
        Button(toolbar_frame, text="H1", command=lambda: self.apply_header_style(self.notes_text, "h1"), **toolbar_button_style).pack(side=tk.LEFT, padx=1, pady=1)
        Button(toolbar_frame, text="Table", command=lambda: self.insert_table(self.notes_text), **toolbar_button_style).pack(side=tk.LEFT, padx=1, pady=1)


        self.notes_text = Text(self.notes_window, bg='white', fg='black', font=("Arial", 12))
        self.notes_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.notes_scrollbar = Scrollbar(self.notes_window, orient=tk.VERTICAL)
        self.notes_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.notes_text.config(yscrollcommand=self.notes_scrollbar.set)
        self.notes_scrollbar.config(command=self.notes_text.yview)

        # Configure tags for RTL/LTR and formatting
        self.notes_text.tag_configure("rtl", justify='right')
        self.notes_text.tag_configure("ltr", justify='left')
        self.notes_text.tag_configure("bold", font=("Arial", 12, "bold"))
        self.notes_text.tag_configure("italic", font=("Arial", 12, "italic"))
        self.notes_text.tag_configure("underline", underline=True)
        self.notes_text.tag_configure("h1", font=("Arial", 18, "bold")) # Example header style


        self.notes_text.bind("<KeyRelease>", self.auto_save_notes)
        self.notes_text.bind("<KeyRelease>", lambda event: self.apply_rtl_ltrl_to_notes(self.notes_text), add="+")


        self.load_notes_into_text()

        self.notes_window.protocol("WM_DELETE_WINDOW", self.on_notes_window_close)
        self.notes_window.bind("<Left>", self.prev_image) # Allow image navigation from notes window
        self.notes_window.bind("<Right>", self.next_image)

    def load_notes_into_text(self):
        """Inserts notes from 'notes.txt' into the notes editor text widget."""
        if not self.notes_window or not tk.Toplevel.winfo_exists(self.notes_window):
            return

        self.notes_text.delete("1.0", tk.END)
        folder_index = self.folder_listbox.curselection()
        if folder_index:
            selected_folder_name = self.folder_listbox.get(folder_index[0])

            full_folder_path = None
            for base_dir in self.BASE_DIRS:
                full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
                potential_path = os.path.join(full_base_dir, selected_folder_name)
                if os.path.exists(potential_path) and os.path.isdir(potential_path):
                    full_folder_path = potential_path
                    break

            if not full_folder_path:
                print(f"Error: Could not find full path for folder name {selected_folder_name}")
                return

            notes_file_path = os.path.join(full_folder_path, "notes.txt")
            if os.path.exists(notes_file_path):
                try:
                    with open(notes_file_path, "r", encoding="utf-8") as f:
                        notes = f.read()
                    self.notes_text.insert("1.0", notes)
                    self.apply_rtl_ltrl_to_notes(self.notes_text) # Apply RTL/LTR on load
                except Exception as e:
                    print(f"Error loading notes: {e}")

    def auto_save_notes(self, event=None):
        """Automatically saves notes to 'notes.txt' in the current folder."""
        selected_folder_index = self.folder_listbox.curselection()
        if not selected_folder_index:
            return

        selected_folder_name = self.folder_listbox.get(selected_folder_index[0])

        full_folder_path = None
        for base_dir in self.BASE_DIRS:
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
            potential_path = os.path.join(full_base_dir, selected_folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                full_folder_path = potential_path
                break

        if not full_folder_path:
            print(f"Error: Could not find full path for folder name {selected_folder_name}")
            return

        notes_file_path = os.path.join(full_folder_path, "notes.txt")

        if self.notes_window and tk.Toplevel.winfo_exists(self.notes_window):
            # Removed .strip() to ensure all content, including blank lines, is saved
            notes = self.notes_text.get("1.0", tk.END)
        else:
            return

        try:
            with open(notes_file_path, "w", encoding="utf-8") as f: # Ensure UTF-8 encoding for Arabic
                f.write(notes)
        except Exception as e:
            print(f"Error saving notes automatically: {e}")

    def load_notes(self):
        """Loads notes from 'notes.txt' and updates the notes editor if open."""
        folder_index = self.folder_listbox.curselection()
        if folder_index:
            selected_folder_name = self.folder_listbox.get(folder_index[0])

            full_folder_path = None
            for base_dir in self.BASE_DIRS:
                full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
                potential_path = os.path.join(full_base_dir, selected_folder_name)
                if os.path.exists(potential_path) and os.path.isdir(potential_path):
                    full_folder_path = potential_path
                    break

            if not full_folder_path:
                print(f"Error: Could not find full path for folder name {selected_folder_name}")
                return

            notes_file_path = os.path.join(full_folder_path, "notes.txt")

            if os.path.exists(notes_file_path):
                try:
                    with open(notes_file_path, "r", encoding="utf-8") as f:
                        notes = f.read().strip()
                except Exception as e:
                    print(f"Error loading notes: {e}")

            if self.notes_window and tk.Toplevel.winfo_exists(self.notes_window):
                self.load_notes_into_text()

    def on_notes_window_close(self):
        """Destroys the notes editor window when closed."""
        self.notes_window.destroy()
        self.notes_window = None
        self.notes_text = None # Clear reference

    def load_gallery_images(self, folder_path):
        """
        Loads image filenames from the given folder for the thumbnail gallery.
        Also loads attachment texts for searching.
        """
        try:
            self.gallery_images = sorted([f for f in os.listdir(folder_path) if
                                           f.lower().endswith(self.IMAGE_EXTENSIONS)], key=natural_sort_key)
        except Exception as e:
            print(f"Error loading gallery images: {e}")
            self.gallery_images = []

        self.load_attachment_texts(folder_path) # Load texts for search filtering

        if self.gallery_visible:
            self.populate_gallery() # Re-populate gallery if visible

    def toggle_gallery(self):
        """Toggles the visibility of the image thumbnail gallery."""
        if self.gallery_visible:
            self.hide_gallery()
        else:
            self.show_gallery()

    def show_gallery(self):
        """Shows the image thumbnail gallery."""
        if not self.gallery_images and not self.folder_listbox.curselection():
            # If no images and no folder selected, don't show gallery
            messagebox.showinfo("Info", "No images to display in the gallery for the current folder.")
            return

        self.populate_gallery() # Populate before showing
        self.gallery_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5, before=self.image_canvas)
        self.gallery_visible = True
        self.resize_image() # Resize main image canvas to fit remaining space

    def hide_gallery(self):
        """Hides the image thumbnail gallery."""
        self.gallery_frame.pack_forget()
        self.gallery_visible = False
        self.resize_image() # Resize main image canvas to fill full space

    def configure_gallery_canvas(self, event):
        """Configures the scroll region for the image thumbnail gallery canvas."""
        self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))

    def scroll_gallery(self, event):
        """Handles scrolling for the image thumbnail gallery."""
        if event.num == 4 or event.delta > 0:
            self.gallery_canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.gallery_canvas.yview_scroll(1, "units")
        else:
            self.gallery_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def populate_gallery(self):
        """Populates the image thumbnail gallery with images from the current folder, applying search filter."""
        # Clear existing buttons
        for button in self.gallery_buttons:
            button.destroy()
        self.gallery_buttons = []
        self.selected_gallery_button = None

        selected_folder_index = self.folder_listbox.curselection()
        if not selected_folder_index:
            print("No folder selected in populate_gallery, skipping thumbnail loading.")
            return

        selected_folder_name = self.folder_listbox.get(selected_folder_index[0])

        full_folder_path = None
        for base_dir in self.BASE_DIRS:
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
            potential_path = os.path.join(full_base_dir, selected_folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                full_folder_path = potential_path
                break

        if not full_folder_path:
            print(f"Error: Could not find full path for folder name {selected_folder_name}")
            return

        # Apply gallery search filter
        search_text = self.gallery_search_var.get().lower()
        search_words = search_text.split()
        
        images_to_display = []
        if not search_text:
            images_to_display = self.gallery_images # Use all loaded images if no search
        else:
            for image_name in self.gallery_images:
                text_content = self.attachment_texts.get(image_name, "")
                if (all(word in image_name.lower() for word in search_words) or
                    all(word in text_content for word in search_words)):
                    images_to_display.append(image_name)

        num_columns = 3 # Display thumbnails in 3 columns
        row = 0
        col = 0

        for i, image_name in enumerate(images_to_display): # Iterate over the filtered/displayable images
            try:
                image_path = os.path.join(full_folder_path, image_name)
                img = Image.open(image_path)
                img.thumbnail(self.thumbnail_size) # Resize to thumbnail size
                photo = ImageTk.PhotoImage(img)

                # The command lambda needs to map back to the original index in `self.image_paths`
                # (the full list of images for the folder) because `self.current_index` refers to that list.
                # So we need to find the original index of `image_name` within `self.image_paths`.
                
                try:
                    original_image_path_in_main_list = os.path.join(full_folder_path, image_name)
                    original_index_in_image_paths = self.image_paths.index(original_image_path_in_main_list)
                except ValueError:
                    print(f"Warning: Image {image_name} from gallery not found in main image_paths. Skipping thumbnail.")
                    continue


                button = Button(self.gallery_inner_frame, image=photo, borderwidth=0,
                                command=lambda idx=original_index_in_image_paths: self.on_gallery_image_select_index(idx))
                button.image = photo # Keep reference to prevent garbage collection
                button.grid(row=row, column=col, padx=5, pady=5)
                self.gallery_buttons.append(button)
                col += 1
                if col >= num_columns:
                    col = 0
                    row += 1
            except Exception as e:
                print(f"Error loading thumbnail for {image_name}: {e}")

        self.gallery_canvas.update_idletasks()
        self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
        self.update_gallery_selection()

    def on_gallery_image_select_index(self, index):
        """Callback when a thumbnail in the image gallery is clicked."""
        try:
            self.gallery_index = index

            selected_folder_index = self.folder_listbox.curselection()
            if not selected_folder_index:
                print("No folder selected when trying to select gallery image.")
                return

            selected_folder_name = self.folder_listbox.get(selected_folder_index[0])

            full_folder_path = None
            for base_dir in self.BASE_DIRS:
                full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
                potential_path = os.path.join(full_base_dir, selected_folder_name)
                if os.path.exists(potential_path) and os.path.isdir(potential_path):
                    full_folder_path = potential_path
                    break

            if not full_folder_path:
                print(f"Error: Could not find full path for folder name {selected_folder_name}")
                return

            # Construct the image path using the actual full folder path
            # IMPORTANT: We need to use the image name from the `images_to_display` list for this function
            # However, `on_gallery_image_select_index` is called with the `original_index_in_image_paths`
            # which refers to `self.image_paths`. So we can directly use that index.
            image_path = self.image_paths[index] # Use the passed index directly with self.image_paths
            
            # Find the index of this image in the main image_paths list
            if image_path in self.image_paths: # This check is redundant if using index directly
                self.current_index = index # Directly set current_index to the passed index
                self.show_image()
                self.load_tags()
                self.load_notes()
                self.load_image_note()
            else:
                print(f"Warning: Selected gallery image '{image_path}' not found in current image_paths (should not happen).")
        except Exception as e:
            print(f"Error gallery image selection: {e}")

    def update_gallery_selection(self):
        """Highlights the currently displayed image's thumbnail in the gallery."""
        if not self.gallery_visible or not self.gallery_buttons:
            return

        # Reset previously selected button
        if self.selected_gallery_button:
            self.selected_gallery_button.config(relief=tk.RAISED, borderwidth=0)

        # Find the corresponding button and highlight it
        try:
            if self.image_paths: # Ensure there's a current image path
                image_path = self.image_paths[self.current_index]
                image_name = os.path.basename(image_path)
                
                # We need to find the index of the current image within the *currently displayed* gallery images.
                # The `populate_gallery` function created buttons based on `images_to_display`.
                # We can either iterate through `images_to_display` or ensure `gallery_buttons` stores a mapping.
                # For simplicity, let's re-filter `self.gallery_images` to get the `images_to_display` list again.

                search_text = self.gallery_search_var.get().lower()
                search_words = search_text.split()
                
                images_currently_displayed = []
                if not search_text:
                    images_currently_displayed = self.gallery_images
                else:
                    for gal_image_name in self.gallery_images:
                        text_content = self.attachment_texts.get(gal_image_name, "")
                        if (all(word in gal_image_name.lower() for word in search_words) or
                            all(word in text_content for word in search_words)):
                            images_currently_displayed.append(gal_image_name)

                if image_name in images_currently_displayed:
                    index_in_currently_displayed = images_currently_displayed.index(image_name)
                    if index_in_currently_displayed < len(self.gallery_buttons):
                        self.selected_gallery_button = self.gallery_buttons[index_in_currently_displayed]
                        self.selected_gallery_button.config(relief=tk.SUNKEN, borderwidth=2, highlightbackground="red", highlightcolor="red")
                    else:
                        self.selected_gallery_button = None # Button not found for current image
                else:
                    self.selected_gallery_button = None # Current image not in currently displayed gallery images
            else:
                self.selected_gallery_button = None # No current image to select
        except IndexError:
            print("IndexError in update_gallery_selection: current_index is out of range.")
            self.selected_gallery_button = None
        except ValueError: # Occurs if image_name not found in images_currently_displayed
            print(f"ValueError in update_gallery_selection: Image not found in currently displayed gallery list.")
            self.selected_gallery_button = None

    def open_in_explorer(self):
        """Opens the currently selected folder in the file explorer, cross-platform."""
        selected_folder_index = self.folder_listbox.curselection()
        if not selected_folder_index:
            messagebox.showinfo("Info", "No folder selected.")
            return

        selected_folder_name = self.folder_listbox.get(selected_folder_index[0])

        full_folder_path = None
        for base_dir in self.BASE_DIRS:
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
            potential_path = os.path.join(full_base_dir, selected_folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                full_folder_path = potential_path
                break

        if not full_folder_path:
            print(f"Error: Could not find full path for folder name {selected_folder_name}")
            return

        if os.path.exists(full_folder_path):
            try:
                if platform.system() == "Windows":
                    os.startfile(full_folder_path)
                elif platform.system() == "Darwin": # macOS
                    subprocess.Popen(['open', full_folder_path])
                else: # Linux and other Unix-like systems
                    subprocess.Popen(['xdg-open', full_folder_path])
                messagebox.showinfo("Success", f"Opened folder in explorer: {full_folder_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open folder in explorer: {e}")
        else:
            messagebox.showerror("Error", "Folder does not exist.")

    def create_new_folder(self):
        """Creates a new subfolder within the selected base directory."""
        new_folder_name = self.new_folder_entry.get().strip()
        if not new_folder_name:
            messagebox.showinfo("Info", "Please enter a folder name.")
            return

        selected_dir_name = self.selected_base_dir_var.get()

        if selected_dir_name == "All":
            messagebox.showinfo("Info", "Please select a specific base directory from the dropdown to create a folder.")
            return

        selected_base_dir_path = None
        for base_dir in self.BASE_DIRS:
            if os.path.basename(base_dir) == selected_dir_name:
                selected_base_dir_path = base_dir
                break
        
        if not selected_base_dir_path:
            messagebox.showerror("Error", "Could not determine the selected base directory from the dropdown.")
            return

        full_base_dir = selected_base_dir_path if os.path.isabs(selected_base_dir_path) else os.path.abspath(selected_base_dir_path)
        new_folder_path = os.path.join(full_base_dir, new_folder_name)

        try:
            os.makedirs(new_folder_path, exist_ok=False) # exist_ok=False prevents overwriting
            messagebox.showinfo("Success", f"Folder '{new_folder_name}' created successfully in '{os.path.basename(full_base_dir)}'.")
            self.load_folders() # Reload folders to update list/cards
            self.new_folder_entry.delete(0, tk.END)
            self.process_and_move_screenshots(new_folder_path) # Process, resize, and move screenshots
        except FileExistsError:
            messagebox.showerror("Error", "Folder with that name already exists.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not create folder: {e}")

    def process_and_move_screenshots(self, dest_folder, quality=80):
        """
        Processes (resizes/converts to WebP) and moves image files
        from the designated SCREENSHOTS_DIR to the destination folder.
        Original files in SCREENSHOTS_DIR are deleted.
        """
        if not os.path.exists(self.SCREENSHOTS_DIR):
            messagebox.showinfo("Info", "Screenshots directory does not exist or is not configured.")
            return

        image_files = [f for f in os.listdir(self.SCREENSHOTS_DIR) if
                       f.lower().endswith(tuple(ext for ext in self.IMAGE_EXTENSIONS if ext != 'webp'))] # Only process non-webp

        if not image_files:
            messagebox.showinfo("Info", "No supported images (non-WebP) found in the configured screenshots directory to process.")
            return

        processed_count = 0
        deleted_count = 0
        skipped_count = 0

        for filename in image_files:
            source_path = os.path.join(self.SCREENSHOTS_DIR, filename)
            name, _ = os.path.splitext(filename)
            new_file_path = os.path.join(dest_folder, f"{name}.webp") # Always save as WebP

            if os.path.exists(new_file_path):
                messagebox.showwarning("File Exists", f"Skipping '{filename}'. A WebP file named '{name}.webp' already exists in the destination. Original will not be deleted.")
                skipped_count += 1
                continue

            if self.compress_image(source_path, new_file_path, quality):
                processed_count += 1
                try:
                    os.remove(source_path) # Delete original only if compression was successful
                    deleted_count += 1
                    print(f"Deleted original image: {source_path}")
                except Exception as e:
                    print(f"Error deleting original image {source_path}: {e}")
                    messagebox.showwarning("Deletion Error", f"Could not delete original image {filename}: {e}")
            else:
                skipped_count += 1 # Image compression failed or was skipped

        messagebox.showinfo("Image Processing",
                            f"Finished processing images from '{os.path.basename(self.SCREENSHOTS_DIR)}'.\n"
                            f"Converted and Moved (WebP created): {processed_count}\n"
                            f"Originals Deleted: {deleted_count}\n"
                            f"Skipped/Failed: {skipped_count}")
        
        self.load_folders() # Reload folders (and implicitly images for the current folder)
        self.load_images() # Refresh current folder view if it's the destination
        self.load_gallery_images(dest_folder) # Refresh gallery

    def copy_path_to_clipboard(self):
        """Copies the full path of the selected folder to the clipboard."""
        selected_folder_index = self.folder_listbox.curselection()
        if not selected_folder_index:
            messagebox.showinfo("Info", "No folder selected.")
            return

        selected_folder_name = self.folder_listbox.get(selected_folder_index[0])

        full_folder_path = None
        for base_dir in self.BASE_DIRS:
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
            potential_path = os.path.join(full_base_dir, selected_folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                full_folder_path = potential_path
                break

        if not full_folder_path:
            print(f"Error: Could not find full path for folder name {selected_folder_name}")
            return

        if os.path.exists(full_folder_path):
            try:
                pyperclip.copy(full_folder_path) # Use pyperclip for cross-platform clipboard
                messagebox.showinfo("Success", "Folder path copied to clipboard.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not copy path to clipboard: {e}")
        else:
            messagebox.showerror("Error", "Folder does not exist.")

    def resize_image(self, event=None):
        """
        Resizes the current image to fit the canvas, maintaining aspect ratio.
        Called on canvas resize or when a new image is loaded.
        """
        if self.original_image:
            canvas_width = self.image_canvas.winfo_width()
            canvas_height = self.image_canvas.winfo_height()

            img_width, img_height = self.original_image.size

            # Calculate new dimensions to fit within canvas while maintaining aspect ratio
            # This is independent of self.zoom_level; update_zoom handles explicit zooming
            # This function primarily fits the image to the available canvas space
            canvas_ratio = canvas_width / canvas_height
            img_ratio = img_width / img_height

            if canvas_ratio > img_ratio:
                # Canvas is wider than image, fit to height
                new_height = canvas_height
                new_width = int(new_height * img_ratio)
            else:
                # Canvas is taller than image, fit to width
                new_width = canvas_width
                new_height = int(new_width * (1 / img_ratio))

            resized_image = self.original_image.resize((new_width, new_height), Image.LANCZOS)
            self.current_image = ImageTk.PhotoImage(resized_image)

            if self.canvas_image_id:
                self.image_canvas.delete(self.canvas_image_id)

            # Center the image on the canvas, applying pan offsets
            x_offset = (canvas_width - new_width) // 2 + self.image_x
            y_offset = (canvas_height - new_height) // 2 + self.image_y

            self.canvas_image_id = self.image_canvas.create_image(
                x_offset, y_offset,
                anchor=tk.NW,
                image=self.current_image
            )

    def open_image_note_editor(self):
        """Opens a Toplevel window for editing notes specific to the current image."""
        if not self.image_paths:
            return

        if self.image_note_window and tk.Toplevel.winfo_exists(self.image_note_window):
            self.image_note_window.focus()
            return

        self.image_note_window = Toplevel(self.root)
        self.image_note_window.title("Edit Image Note")
        self.image_note_window.geometry("600x400") # Increased size for toolbar
        self.image_note_window.attributes('-topmost', True)

        # Toolbar Frame
        toolbar_frame = Frame(self.image_note_window, bd=1, relief=tk.RAISED, bg=self.bg_color)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)

        # Button Styling for toolbar
        toolbar_button_style = {'bg': self.button_bg, 'fg': self.button_fg, 'font': ("Arial", 10), 'borderwidth': 1,
                                'relief': tk.RAISED, 'padx': 2, 'pady': 2}

        # Toolbar Buttons
        Button(toolbar_frame, text="B", command=lambda: self.apply_format(self.image_note_text, "bold"), **toolbar_button_style).pack(side=tk.LEFT, padx=1, pady=1)
        Button(toolbar_frame, text="I", command=lambda: self.apply_format(self.image_note_text, "italic"), **toolbar_button_style).pack(side=tk.LEFT, padx=1, pady=1)
        Button(toolbar_frame, text="U", command=lambda: self.apply_format(self.image_note_text, "underline"), **toolbar_button_style).pack(side=tk.LEFT, padx=1, pady=1)
        Button(toolbar_frame, text="H1", command=lambda: self.apply_header_style(self.image_note_text, "h1"), **toolbar_button_style).pack(side=tk.LEFT, padx=1, pady=1)
        Button(toolbar_frame, text="Table", command=lambda: self.insert_table(self.image_note_text), **toolbar_button_style).pack(side=tk.LEFT, padx=1, pady=1)


        self.image_note_text = Text(self.image_note_window, bg='white', fg='black', font=("Arial", 12))
        self.image_note_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.image_note_scrollbar = Scrollbar(self.image_note_window, orient=tk.VERTICAL)
        self.image_note_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.image_note_text.config(yscrollcommand=self.image_note_scrollbar.set)
        self.image_note_scrollbar.config(command=self.image_note_text.yview)

        # Configure tags for RTL/LTR and formatting
        self.image_note_text.tag_configure("rtl", justify='right')
        self.image_note_text.tag_configure("ltr", justify='left')
        self.image_note_text.tag_configure("bold", font=("Arial", 12, "bold"))
        self.image_note_text.tag_configure("italic", font=("Arial", 12, "italic"))
        self.image_note_text.tag_configure("underline", underline=True)
        self.image_note_text.tag_configure("h1", font=("Arial", 18, "bold")) # Example header style


        self.image_note_text.bind("<KeyRelease>", self.auto_save_image_note)
        self.image_note_text.bind("<KeyRelease>", lambda event: self.apply_rtl_ltrl_to_notes(self.image_note_text), add="+")

        self.load_image_note_into_text() # Load existing image note

        self.image_note_window.protocol("WM_DELETE_WINDOW", self.on_image_note_window_close)
        self.image_note_window.bind("<Left>", self.prev_image) # Allow navigation from this window
        self.image_note_window.bind("<Right>", self.next_image)

    def load_image_note_into_text(self):
        """Loads the note for the current image into the image note editor."""
        if not self.image_note_window or not tk.Toplevel.winfo_exists(self.image_note_window):
            return

        self.image_note_text.delete("1.0", tk.END)
        note_text = self.load_image_note() # Get note content
        self.image_note_text.insert("1.0", note_text)
        self.apply_rtl_ltrl_to_notes(self.image_note_text) # Apply RTL/LTR on load

    def auto_save_image_note(self, event=None):
        """Automatically saves the current image note."""
        if not self.image_paths:
            return

        if self.image_note_window and tk.Toplevel.winfo_exists(self.image_note_window):
            # Removed .strip() to ensure all content, including blank lines, is saved
            note_text = self.image_note_text.get("1.0", tk.END)
        else:
            return

        self.save_image_note(note_text)

    def get_attachment_dir(self):
        """Returns the path to the 'attachments' subfolder for the current image's directory."""
        if not self.image_paths or self.current_index >= len(self.image_paths):
            return None

        image_dir = os.path.dirname(self.image_paths[self.current_index])
        attachment_dir = os.path.join(image_dir, self.ATTACHMENTS_DIR_NAME)

        # Create the directory if it doesn't exist
        if not os.path.exists(attachment_dir):
            try:
                os.makedirs(attachment_dir)
            except Exception as e:
                print(f"Error creating attachment directory: {e}")
                return None
        return attachment_dir

    def load_image_note(self):
        """Loads the note specific to the current image from its attachment file."""
        attachment_dir = self.get_attachment_dir()
        if not attachment_dir:
            return ""

        image_filename = os.path.basename(self.image_paths[self.current_index])
        image_name_without_extension = os.path.splitext(image_filename)[0]
        note_filename = f"{image_name_without_extension}.txt" # Note file named after image
        note_path = os.path.join(attachment_dir, note_filename)

        try:
            if os.path.exists(note_path):
                with open(note_path, "r", encoding="utf-8") as f:
                    note_text = f.read()
                return note_text
            else:
                return ""
        except Exception as e:
            print(f"Error loading image note from '{note_path}': {e}")
            return ""

    def save_image_note(self, note_text):
        """Saves the note for the current image to its attachment file."""
        attachment_dir = self.get_attachment_dir()
        if not attachment_dir:
            return

        image_filename = os.path.basename(self.image_paths[self.current_index])
        image_name_without_extension = os.path.splitext(image_filename)[0]
        note_filename = f"{image_name_without_extension}.txt"
        note_path = os.path.join(attachment_dir, note_filename)

        try:
            with open(note_path, "w", encoding="utf-8") as f: # Ensure UTF-8 encoding for Arabic
                f.write(note_text)
        except Exception as e:
            print(f"Error saving image note to '{note_path}': {e}")

    def on_image_note_window_close(self):
        """Destroys the image note editor window when closed."""
        self.image_note_window.destroy()
        self.image_note_window = None
        self.image_note_text = None # Clear reference

    def add_images_to_selected_folder(self, quality=80):
        """
        Resizes and converts images from SCREENSHOTS_DIR to WebP,
        renaming them sequentially (Screenshot_X.webp), and moves them
        to the selected folder. Original files in SCREENSHOTS_DIR are deleted.
        """
        selected_folder_index = self.folder_listbox.curselection()
        if not selected_folder_index:
            messagebox.showinfo("Info", "No folder selected in the listbox to add images to.")
            return

        selected_folder_name = self.folder_listbox.get(selected_folder_index[0])

        full_destination_path = None
        for base_dir in self.BASE_DIRS:
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
            potential_path = os.path.join(full_base_dir, selected_folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                full_destination_path = potential_path
                break

        if not full_destination_path:
            print(f"Error: Could not find full path for folder name {selected_folder_name}")
            return

        if not os.path.exists(self.SCREENSHOTS_DIR):
            messagebox.showinfo("Info", "The source screenshot directory does not exist or is not configured.")
            return

        # Get list of files to process (exclude existing webp files)
        image_files = [f for f in os.listdir(self.SCREENSHOTS_DIR) if
                       f.lower().endswith(tuple(ext for ext in self.IMAGE_EXTENSIONS if ext != 'webp'))]

        if not image_files:
            messagebox.showinfo("Info", "No supported images (non-WebP) found in the source screenshot directory to add.")
            return

        processed_count = 0
        deleted_count = 0
        skipped_count = 0

        # Find the highest existing "Screenshot_X" number in the destination folder
        highest_number = 0
        for filename in os.listdir(full_destination_path):
            name, ext = os.path.splitext(filename)
            match = re.match(r"Screenshot_(\d+)", name, re.IGNORECASE)
            if match:
                try:
                    number = int(match.group(1))
                    highest_number = max(highest_number, number)
                except ValueError:
                    pass

        next_number = highest_number + 1

        for filename in image_files:
            source_path = os.path.join(self.SCREENSHOTS_DIR, filename)
            
            # New filename will always be .webp
            new_filename = f"Screenshot_{next_number}.webp"
            destination_path = os.path.join(full_destination_path, new_filename)

            if os.path.exists(destination_path):
                messagebox.showwarning("File Exists", f"Skipping '{filename}'. A file named '{new_filename}' already exists after renaming attempt. Original will not be deleted.")
                skipped_count += 1
                continue

            if self.compress_image(source_path, destination_path, quality):
                processed_count += 1
                try:
                    os.remove(source_path) # Delete original only if compression was successful
                    deleted_count += 1
                    print(f"Deleted original image: {source_path}")
                except Exception as e:
                    print(f"Error deleting original image {source_path}: {e}")
                    messagebox.showwarning("Deletion Error", f"Could not delete original image {filename}: {e}")
            else:
                skipped_count += 1 # Image compression failed or was skipped
            
            next_number += 1 # Increment for the next image, regardless of success to avoid name collisions

        message = f"Successfully processed and added {processed_count} images to '{os.path.basename(full_destination_path)}'."
        if skipped_count > 0:
            message += f" {skipped_count} images were skipped/failed."
        messagebox.showinfo("Add Images", message)
        
        # Reload images and gallery for the current folder
        self.load_images()
        self.load_gallery_images(full_destination_path)

    def load_attachment_texts(self, folder_path):
        """Loads text content from .txt files in the 'attachments' subfolder for searching."""
        attachment_dir = os.path.join(folder_path, self.ATTACHMENTS_DIR_NAME)
        self.attachment_texts = {} # Clear existing texts

        if not os.path.exists(attachment_dir):
            return

        for filename in os.listdir(attachment_dir):
            if filename.lower().endswith(".txt"):
                filepath = os.path.join(attachment_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        text = f.read().lower()
                        image_name_prefix = os.path.splitext(filename)[0]
                        # Associate the text with all possible image extensions
                        for ext in self.IMAGE_EXTENSIONS:
                            potential_image_name = f"{image_name_prefix}.{ext}"
                            if potential_image_name in self.gallery_images:
                                self.attachment_texts[potential_image_name] = text
                                break # Found a matching image, no need to check other extensions
                except Exception as e:
                    print(f"Error reading attachment text from '{filename}': {e}")

    def update_gallery_search(self, event=None):
        """Filters the image thumbnail gallery based on text in attachment notes."""
        # No need to build `filtered_images` here, just call populate_gallery
        # populate_gallery will now handle the internal filtering.
        self.populate_gallery() 

    def compress_image(self, image_path, save_path, quality=80):
        """
        Opens an image, converts it to WebP format, and saves it with specified quality.
        """
        try:
            with Image.open(image_path) as img:
                # Ensure the image is in RGB mode before saving as WebP, for broader compatibility
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(save_path, "WEBP", quality=quality, lossless=False, method=6) # method=6 is highest quality
                print(f"Compressed image saved at: {save_path}")
                return True
        except Exception as e:
            print(f"Error compressing {image_path}: {e}")
            messagebox.showerror("Compression Error", f"Failed to compress {os.path.basename(image_path)}: {e}")
            return False

    def resize_images_in_current_folder(self, quality=80):
        """
        Resizes and converts all supported non-WebP images in the currently selected folder to WebP,
        and then deletes the original image file.
        """
        selected_folder_index = self.folder_listbox.curselection()
        if not selected_folder_index:
            messagebox.showinfo("Info", "Please select a folder first to resize images.")
            return

        selected_folder_name = self.folder_listbox.get(selected_folder_index[0])
        full_folder_path = None

        for base_dir in self.BASE_DIRS:
            full_base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
            potential_path = os.path.join(full_base_dir, selected_folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                full_folder_path = potential_path
                break

        if not full_folder_path:
            messagebox.showerror("Error", f"Could not find full path for folder name {selected_folder_name}")
            return

        processed_count = 0
        deleted_count = 0
        skipped_count = 0

        # Get list of files to process (exclude existing webp files)
        files_to_process = [f for f in os.listdir(full_folder_path) if
                            f.lower().endswith(tuple(ext for ext in self.IMAGE_EXTENSIONS if ext != 'webp'))]

        if not files_to_process:
            messagebox.showinfo("Image Resizing", "No supported images (non-WebP) found for resizing in this folder.")
            return

        for filename in files_to_process:
            file_path = os.path.join(full_folder_path, filename)

            name, ext = os.path.splitext(filename)
            new_file_path = os.path.join(full_folder_path, f"{name}.webp")

            if os.path.exists(new_file_path):
                messagebox.showwarning("File Exists", f"Skipping '{filename}'. A WebP file named '{name}.webp' already exists. The original will not be deleted.")
                skipped_count += 1
                continue

            if self.compress_image(file_path, new_file_path, quality):
                processed_count += 1
                try:
                    os.remove(file_path) # Delete original only if compression was successful
                    deleted_count += 1
                    print(f"Deleted original image: {file_path}")
                except Exception as e:
                    print(f"Error deleting original image {file_path}: {e}")
                    messagebox.showwarning("Deletion Error", f"Could not delete original image {filename}: {e}")
            else:
                skipped_count += 1 # Image compression failed or was skipped

        messagebox.showinfo("Image Resizing",
                            f"Finished resizing images in '{selected_folder_name}'.\n"
                            f"Converted and Deleted Originals: {deleted_count}\n"
                            f"Processed (WebP created): {processed_count}\n"
                            f"Skipped/Failed: {skipped_count}")

        # Reload images to show new compressed files in the gallery and main view
        self.load_images()

    def is_arabic(self, text):
        """Checks if a string contains Arabic characters."""
        # Arabic characters range from U+0600 to U+06FF
        return any('\u0600' <= char <= '\u06FF' for char in text)

    def apply_rtl_ltrl_to_notes(self, text_widget):
        """
        Applies RTL or LTR justification and reordering to each line
        in the given Text widget based on content.
        """
        if bidi_alg is None: # Check if bidi_alg was successfully imported
            return

        # Clear existing tags to prevent conflicts
        text_widget.tag_remove("rtl", "1.0", tk.END)
        text_widget.tag_remove("ltr", "1.0", tk.END)

        content = text_widget.get("1.0", tk.END).strip()
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            start_index = f"{line_num}.0"
            end_index = f"{line_num}.end"

            if self.is_arabic(line):
                # Apply RTL tag for Arabic lines
                text_widget.tag_add("rtl", start_index, end_index)
                # Reorder the text visually using bidi_alg for display
                # Note: This changes the visual representation but not the underlying string in the widget.
                # Tkinter's Text widget doesn't directly support complex bidi layout natively.
                # The tag_configure 'justify' helps with alignment.
                # For true bidi, a custom widget or a different GUI toolkit might be needed.
                # However, for simple line-by-line justification, this approach works.
                # To actually change the text in the widget, you'd need to delete and reinsert.
                # For now, we rely on 'justify' and the user seeing the correct direction when typing.
            else:
                # Apply LTR tag for English lines
                text_widget.tag_add("ltr", start_index, end_index)

    def apply_format(self, text_widget, format_type):
        """Applies or removes a text formatting tag (bold, italic, underline)."""
        try:
            current_selection = text_widget.tag_ranges(tk.SEL)
            if not current_selection:
                return # No text selected

            start, end = current_selection

            # Check if the format is already applied to the entire selection
            # If it is, remove it; otherwise, apply it.
            if text_widget.tag_names(start) and format_type in text_widget.tag_names(start):
                text_widget.tag_remove(format_type, start, end)
            else:
                text_widget.tag_add(format_type, start, end)
            
            # Ensure the text widget retains focus after formatting
            text_widget.focus_set()

        except tk.TclError as e:
            print(f"Error applying format: {e}")
            messagebox.showerror("Formatting Error", f"Could not apply format: {e}")

    def apply_header_style(self, text_widget, header_type):
        """Applies a header style to the selected text (placeholder)."""
        try:
            current_selection = text_widget.tag_ranges(tk.SEL)
            if not current_selection:
                return # No text selected

            start, end = current_selection

            # Remove other header tags if present to avoid conflicts
            for tag in ["h1", "h2", "h3"]: # Add more header tags as needed
                if tag != header_type and text_widget.tag_names(start) and tag in text_widget.tag_names(start):
                    text_widget.tag_remove(tag, start, end)

            # Toggle the header style
            if text_widget.tag_names(start) and header_type in text_widget.tag_names(start):
                text_widget.tag_remove(header_type, start, end)
            else:
                text_widget.tag_add(header_type, start, end)
            
            text_widget.focus_set()

        except tk.TclError as e:
            print(f"Error applying header style: {e}")
            messagebox.showerror("Header Error", f"Could not apply header style: {e}")

    def insert_table(self, text_widget):
        """Inserts a simple placeholder for a table (advanced functionality would be complex)."""
        # For a full table, you'd need to:
        # 1. Create a custom widget or use a library that supports tables.
        # 2. Implement logic for rows, columns, cell editing, etc.
        # This is a very basic text-based representation.
        try:
            table_text = "\n" + "-"*30 + "\n"
            table_text += "| Header 1 | Header 2 |\n"
            table_text += "|----------|----------|\n"
            table_text += "| Data 1   | Data 2   |\n"
            table_text += "| Data 3   | Data 4   |\n"
            table_text += "-"*30 + "\n"
            text_widget.insert(tk.INSERT, table_text)
            text_widget.focus_set()
        except tk.TclError as e:
            print(f"Error inserting table: {e}")
            messagebox.showerror("Table Error", f"Could not insert table: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageGallery(root)
    root.mainloop()

