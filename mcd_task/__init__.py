from parse import parse

from mcd_task.command_actions import *
from mcd_task.task_manager import *
from mcd_task.globals import *


def on_info(server: PluginServerInterface, info: Info):
    if info.is_from_server and root.config["detect_player_rename"]:
        psd = parse(PLAYER_RENAMED, info.content)
        if psd is not None:
            inherit_responsible(info, **psd.named)


def on_player_joined(server: PluginServerInterface, player: str, info: Info):
    player_tasks = []
    now_time = float(time.time())
    for t in root.task_manager.get_responsible_manager()[player]:
        task = root.task_manager[t]
        if not task.done and now_time > task.deadline:
            player_tasks.append(task)
    if len(player_tasks) > 0:
        task_timed_out(server, player, player_tasks)


def on_load(server: PluginServerInterface, prev_module):
    root.set_server(server)
    root.config.load(server)
    root.setup_logger()
    register_cmd_tree(server)
    server.register_help_message(PREFIX, server.tr("mcd_task.mcdr_help"))
