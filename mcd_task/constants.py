import os

# |=============================|
# |   Plugin global constants   |
# |=============================|


# Command prefix
PREFIX = "!!task"

# Data folder
DATA_FOLDER = "./config/task"
if not os.path.isdir(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)
# Config file path
CONFIG_PATH = os.path.join(DATA_FOLDER, "config.json")
# Task file path
TASK_PATH = os.path.join(DATA_FOLDER, "mc_task.json")
# Task path for old version of this plugin
TASK_PATH_PREV = "./plugins/task/mc_task.json"
# Responsible Group file path
RESG_PATH = os.path.join(DATA_FOLDER, "responsible.json")
# Log file path
LOG_PATH = os.path.join(DATA_FOLDER, "logs", "task.log")

# If this is True, will enable some debug options
DEBUG_MODE = False

# Supported languages
LANGUAGES = ["en_us", "zh_cn"]

# Player change name info format
PLAYER_RENAMED = "{new_name} (formerly known as {old_name}) joined the game"
