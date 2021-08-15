import os
import typing

from mcd_task.task_manager import TaskManager
from mcd_task.config import Config

if typing.TYPE_CHECKING:
    from mcdreforged.api.types import PluginServerInterface
    from mcdreforged.utils.logger import MCDReforgedLogger

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
RESG_PATH = os.path.join(DATA_FOLDER, "player_group.json")
# Log file path
LOG_PATH = os.path.join(DATA_FOLDER, "logs", "task.log")

# If this is True, will output debug log in server console
DEBUG_MODE = False

# Supported languages
LANGUAGES = ["en_us", "zh_cn"]

# |=================================|
# |   Global varibles and methods   |
# |=================================|


class root:
    task_manager = TaskManager()
    config = Config()
    server = None                   # type: typing.Optional[PluginServerInterface]
    logger = None                   # type: typing.Optional[MCDReforgedLogger]

    @classmethod
    def debug(cls, *msg, option=None):
        cls.logger.debug(*msg, option, no_check=DEBUG_MODE)

    @classmethod
    def tr(cls, key: typing.Optional[str], *args, lang: typing.Optional[str] = None, fallback: str = 'en_us'):
        return cls.server.tr(key, language=lang, fallback_language=fallback).format(*args)

    @classmethod
    def set_server(cls, server: PluginServerInterface):
        cls.server = server
        cls.logger = server.logger

    @classmethod
    def setup_logger(cls):
        if not os.path.isdir(os.path.dirname(LOG_PATH)):
            os.makedirs(os.path.dirname(LOG_PATH))
        cls.logger.set_file(LOG_PATH)
