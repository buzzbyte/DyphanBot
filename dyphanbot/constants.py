import os

# Codebase info
CB_NAME = "DyphanBot"

# Root directory
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Data directories the program could look into
DATA_DIRS = [
    "~/.dyphan",
    "~/.config/dyphan"
]

# Possible plugin directories
PLUGIN_DIRS = [os.path.join(ROOT_DIR, "plugins")]
PLUGIN_DIRS += [os.path.join(os.path.expanduser(ddir), "plugins") for ddir in DATA_DIRS]
print("PLUGIN_DIRS = ",PLUGIN_DIRS)
