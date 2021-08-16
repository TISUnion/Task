import os

# |=============================|
# |   Plugin global constants   |
# |=============================|


# Command prefix
PREFIX = "!!task"

# Data folder
DATA_FOLDER = "./config/task"
# Config file path
CONFIG_PATH = os.path.join(DATA_FOLDER, "config.json")
# Default config file path in this bundle
DEFAULT_CONFIG_PATH = "resources/default_config.json"
# Task file path
TASK_PATH = os.path.join(DATA_FOLDER, "mc_task.json")
# Task path for old version of this plugin
TASK_PATH_PREV = "./plugins/task/mc_task.json"
# Responsible Group file path
RESG_PATH = os.path.join(DATA_FOLDER, "responsible.json")
# Log file path
LOG_PATH = os.path.join(DATA_FOLDER, "logs", "task.log")

# If this is True, will output debug log in server console
DEBUG_MODE = False

# Supported languages
LANGUAGES = ["en_us", "zh_cn"]

# Player change name info format
PLAYER_RENAMED = "{new_name} (formerly known as {old_name}) joined the game"