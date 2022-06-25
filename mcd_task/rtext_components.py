from mcdreforged.api.rtext import *

from mcd_task.task_manager import Task
from mcd_task.global_variables import GlobalVariables
from mcd_task.constants import *
from collections import namedtuple
from collections import namedtuple

from mcdreforged.api.rtext import *

from mcd_task.constants import *
from mcd_task.global_variables import GlobalVariables
from mcd_task.task_manager import Task

TypeItems = namedtuple('TypeItems', ["name", 'hover_tr_key', 'cmd_fmt'])


class EditButtonType:
    rename = TypeItems('name', 'rename_task_hover', PREFIX + " rename {} ")
    desc = TypeItems("desc", "edit_task_hover", PREFIX + " change {} ")
    priority = TypeItems("priority", "priority_hover", PREFIX + " priority {} ")
    deadline = TypeItems("deadline", "set_ddl_hover", PREFIX + " deadline {} ")


def tr(key: str, *args, **kwargs):
    return GlobalVariables.tr(key, *args, **kwargs)


def indent_text(indent: int) -> str:
    ret = ''
    for num in range(indent):
        ret += ' '
    return ret


def list_done_task_button():
    return tr('done_task_button').c(RAction.run_command, f'{PREFIX} list-done').h(
        tr('done_task_hover')).set_color(RColor.dark_gray)


def done_button(task: Task):
    # Done button
    click_event_to_do = 'undone' if task.is_done else 'done'
    return RText("⬛" if task.done else "⬜", RColor.dark_gray if task.done else RColor.white).h(
        tr(f"mark_task_{click_event_to_do}_hover")).c(
        RAction.run_command, "{} {} {}".format(PREFIX, click_event_to_do, task.titles)
    )


def add_task_button(title: str = None):
    # Add button
    title_path = '' if title in ['', None] else '{}.'.format(title)
    return RText('[+]', RColor.light_purple, RStyle.bold).c(
        RAction.suggest_command, '{} add {}'.format(PREFIX, title_path)).h(
        tr(f"add{'' if title is None else '_sub'}_task_hover")
    )


def edit_button(task: Task, button_type: TypeItems = EditButtonType.rename):
    return RText("  [✎]").h(tr(button_type.hover_tr_key)).c(RAction.suggest_command, button_type.cmd_fmt.format(task.titles))


def title_text(task: Task, display_full_path=False, with_edit_button=False, indent=4, display_not_empty_mark=False,
               include_sub=True):
    edit = ''
    if with_edit_button:
        edit = edit_button(task)
    target_title, title_text_list = task.titles.copy(), []
    while True:
        if target_title.is_empty:
            break
        if not display_full_path and len(title_text_list) == 1:
            break
        this_title_full = str(target_title)
        this_title = target_title.pop_tail()
        title_text_list.append(
            RText(this_title,
                  RColor.gray if GlobalVariables.task_manager[this_title_full].is_done else RColor.yellow).c(
                RAction.run_command, f'{PREFIX} detail {this_title_full}').h(tr('info_task_hover', this_title_full))
        )
    title_text_list.reverse()
    title = RText.join('§7.§r', title_text_list)
    if display_not_empty_mark:
        if task.is_not_empty or (include_sub and len(task.sub_tasks) > 0):
            title += ' §f[...]'
    return indent_text(indent) + done_button(task) + ' ' + title + edit


# !!task detail <titles> components
def info_elements(task: Task, button_type: TypeItems = EditButtonType.desc, indent=4):
    return indent_text(indent) + tr(f'detail_{button_type.name}', task.get_elements(button_type.name)).h(
        tr(button_type.hover_tr_key)).c(
        RAction.suggest_command, button_type.cmd_fmt.format(task.titles))


def info_responsibles_headline(task: Task):
    return tr('detail_res').c(
        RAction.suggest_command, '{} res {} '.format(PREFIX, task.titles)).h(tr(f"add_res_hover"))


def single_responsible(task: Task, player: str, indent=8, removed=False):
    text = indent_text(indent) + RText(
        player, RColor.dark_gray if removed else RColor.dark_aqua, RStyle.strikethrough if removed else None).h(
        tr('info_player_hover')).c(
        RAction.run_command, f'{PREFIX} player {player}') + ' '
    if not removed:
        text += RText('[-]', RColor.aqua, RStyle.bold).c(
            RAction.run_command, f'{PREFIX} unres {task.titles} {player}').h(tr('rm_res_hover', player))
    return text


def info_responsibles(task: Task, indent=4):
    text = indent_text(indent) + info_responsibles_headline(task)
    for player in task.responsibles:
        text += '\n' + single_responsible(task, player, indent=indent + 4)
    return text


def sub_task_title_text(task: Task, indent=4):
    text = []
    for sub in task.sorted_sub_tasks:
        text.append(indent_text(indent) + title_text(sub))
        if len(sub.sub_tasks) > 0:
            text.append(sub_task_title_text(sub, indent + 4))
    return RTextBase.join('\n', text)


def info_sub_tasks(task: Task, indent=4):
    text = indent_text(indent) + tr('detail_sub') + ' ' + add_task_button(str(task.titles))
    if len(task.sub_tasks) > 0:
        text += '\n' + sub_task_title_text(task, indent=indent + 4)
    return text
