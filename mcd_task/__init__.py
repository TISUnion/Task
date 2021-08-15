from mcd_task.command_actions import *
from mcd_task.task_manager import *
from mcd_task.globals import *


def on_load(server: PluginServerInterface, prev_module):
    root.set_server(server)
    root.config.load(server)
    root.setup_logger()
    register_cmd_tree(server)
    server.register_help_message(PREFIX, server.tr("mcd_task.mcdr_help"))
