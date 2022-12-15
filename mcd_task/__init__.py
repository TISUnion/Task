from mcd_task.command_actions import *
from mcd_task.global_variables import GlobalVariables
from mcd_task.task_manager import *
from mcd_task.constants import PLAYER_RENAMED, DATA_FOLDER
from mcd_task.config import Config

from parse import parse


def on_info(server: PluginServerInterface, info: Info):
    if info.is_from_server and GlobalVariables.config["detect_player_rename"]:
        psd = parse(PLAYER_RENAMED, info.content)
        if psd is not None:
            inherit_responsible(info, **psd.named)

    if info.is_user and DEBUG_MODE:
        if info.content.startswith('!!task debug '):
            info.cancel_send_to_server()
            args = info.content.split(' ')
            if args[2] == 'base-title':
                info.get_command_source().reply('Manager title is {}'.format(GlobalVariables.task_manager.title))
            elif args[2] == 'full-path' and len(args) == 4:
                info.get_command_source().reply(GlobalVariables.task_manager[args[3]].titles)
            elif args[2] == 'player-join':
                on_player_joined(server, info.player, info)
            elif args[2] == 'player-renamed' and len(args) == 5:
                inherit_responsible(info, old_name=args[3], new_name=args[4], debug=True)
            elif args[2] == 'taskmgr-data' and len(args) == 3:
                GlobalVariables.debug(str(GlobalVariables.task_manager.serialize()))
            elif args[2] == 'seek-no-father' and len(args) == 3:
                GlobalVariables.debug(str(GlobalVariables.task_manager.seek_no_father_nodes()))
            elif args[2] == 'detail' and len(args) == 4:
                GlobalVariables.debug(str(GlobalVariables.task_manager[args[3]].titles))


def on_player_joined(server: PluginServerInterface, player: str, info: Info):
    player_tasks = []
    now_time = float(time.time())
    for t in GlobalVariables.task_manager.responsible_manager[player]:  # type: Task
        task = GlobalVariables.task_manager[t.titles]
        if not task.is_done and now_time > task.deadline != 0:
            player_tasks.append(task)
    if len(player_tasks) > 0:
        task_timed_out(server, player, player_tasks)


def on_load(server: PluginServerInterface, prev_module):
    if prev_module is not None:
        pass
    GlobalVariables.set_config(Config.load(server))
    GlobalVariables.setup_task_manager(TaskManager.load())
    register_cmd_tree(server)
    server.register_help_message(PREFIX, server.tr("mcd_task.mcdr_help"))


def on_unload(*args, **kwargs):
    GlobalVariables.logger.unset_file()
