import logging
import os.path
import re
import types
from typing import Optional, Union, TYPE_CHECKING
from mcdreforged.api.all import RTextBase, RTextList, RText, RAction, ServerInterface, MCDReforgedLogger

from mcd_task.config import Config
from mcd_task.constants import LOG_PATH, PREFIX, DEBUG_MODE, DATA_FOLDER


if TYPE_CHECKING:
    from mcd_task.task_manager import TaskManager


def inject_set_file_method(logger: MCDReforgedLogger):
    logger.set_file(LOG_PATH)
    return logger


class GlobalVariables:
    task_manager: Optional["TaskManager"] = None
    server = ServerInterface.get_instance()
    logger = None
    if server is not None:
        server = server.as_plugin_server_interface()
        logger = inject_set_file_method(server.logger)
    config = None

    @classmethod
    def log(cls, msg):
        cls.logger.info(msg)

    @classmethod
    def debug(cls, msg):
        cls.logger.debug(msg, no_check=DEBUG_MODE)

    @classmethod
    def tr(cls, key: Optional[str], *args, **kwargs):
        if not key.startswith('mcd_task.'):
            key = f"mcd_task.{key}"
        return cls.server.rtr(key, *args, **kwargs)

    @classmethod
    def htr(cls, key: str, *args, language=None, **kwargs) -> Union[str, RTextBase]:
        help_message, help_msg_rtext = cls.server.tr(key, *args, language=language, **kwargs), RTextList()
        if not isinstance(help_message, str):
            cls.logger.error('Error translate text "{}"'.format(key))
            return key
        for line in help_message.splitlines():
            result = re.search(r'(?<=§7){}[\S ]*?(?=§)'.format(PREFIX), line)
            if result is not None:
                cmd = result.group().strip() + ' '
                help_msg_rtext.append(RText(line).c(RAction.suggest_command, cmd).h(
                    cls.tr("mcd_task.help_msg_suggest_hover", cmd.strip())))
            else:
                help_msg_rtext.append(line)
            if line != help_message.splitlines()[-1]:
                help_msg_rtext.append('\n')
        return help_msg_rtext

    @classmethod
    def set_config(cls, cfg: 'Config'):
        cls.config = cfg

    @classmethod
    def setup_task_manager(cls, task_manager: 'TaskManager'):
        cls.task_manager = task_manager
