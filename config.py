import os

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SONGS_FOLDER = os.path.join(BASE_DIR, "audio")
TOKEN_FILE = 'tokens.json'

# --- System Settings ---
DEFAULT_VOLUME = 1500 # Start with a good default volume
MIN_VOLUME = 50
MAX_VOLUME = 25000
VOLUME_STEP = 10

# --- Discord Setup ---
SUPPORTED_COMMANDS = [
    '!u', '!load', 
    '!1', '!ja', '!p', '!p 2', '!s', '!l', '!loop', 
    '!vol', '!volup', '!voldown', '!status', '!check', '!songs'
]