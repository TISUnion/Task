from parse import parse

from mcd_task.command_actions import *
from mcd_task.task_manager import *
from mcd_task.constants import PLAYER_RENAMED, DATA_FOLDER


def on_info(server: PluginServerInterface, info: Info):
    if info.is_from_server and root.config["detect_player_rename"]:
        psd = parse(PLAYER_RENAMED, info.content)
        if psd is not None:
            inherit_responsible(info, **psd.named)
    server.as_plugin_server_interface()

    if info.is_user and DEBUG_MODE:
        if info.content.startswith('!!task debug '):
            info.cancel_send_to_server()
            args = info.content.split(' ')
            if args[2] == 'base-title':
                info.get_command_source().reply('Manager title is {}'.format(root.task_manager.title))
            elif args[2] == 'full-path' and len(args) == 4:
                info.get_command_source().reply(root.task_manager[args[3]].full_path())


def on_player_joined(server: PluginServerInterface, player: str, info: Info):
    player_tasks = []
    now_time = float(time.time())
    for t in root.task_manager.get_responsible_manager()[player]:
        task = root.task_manager[t]
        if not task.done and now_time > task.deadline:
            player_tasks.append(task)
    if len(player_tasks) > 0:
        task_timed_out(server, player, player_tasks)
    info.get_server()


def on_load(server: PluginServerInterface, prev_module):
    if prev_module is not None:
        pass
    if not os.path.isdir(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    root.set_server(server)
    root.setup_logger()
    root.setup_task_manager(TaskManager())
    register_cmd_tree(server)
    server.register_help_message(PREFIX, server.tr("mcd_task.mcdr_help"))
