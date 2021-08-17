import re
import time

from typing import Callable, Any, Optional, Union, List, Iterable
from mcdreforged.api.all import *

from mcd_task.constants import PREFIX, DEBUG_MODE
from mcd_task.task_manager import TitleList, TaskNotFoundError, root, TaskBase, Task


# ===============================
# |    Register Command Tree    |
# ===============================


def register_cmd_tree(server: PluginServerInterface):
    def pliteral(*literal: str) -> Literal:
        lvl = root.config['permission.{}'.format(literal[0])]
        lvl = lvl if isinstance(lvl, int) else 0
        return Literal(literal).requires(
            lambda src: src.has_permission(lvl),
            failure_message_getter=lambda: server.tr('mcd_task.perm_denied').format(lvl)
        )

    def exe(func: Callable[[CommandSource, str], Any]):
        return lambda src, ctx: func(src, **ctx)

    server.register_command(
        Literal(PREFIX).runs(list_task).then(
            pliteral("list").runs(list_task)
        ).then(
            pliteral("help").runs(show_help)
        ).then(
            pliteral("detail").then(
                QuotableText("title").runs(exe(info_task)))
        ).then(
            pliteral("detail-all").runs(all_tasks_detail)
        ).then(
            pliteral("list-done").runs(list_done)
        ).then(
            pliteral("add").then(
                QuotableText("titles").runs(exe(add_task)).then(
                    GreedyText("desc").runs(exe(add_task))))
        ).then(
            pliteral("del").then(
                QuotableText("titles").runs(exe(remove_task)))
        ).then(
            pliteral("rename").then(
                QuotableText("old_titles").then(
                    QuotableText("new_title").runs(exe(rename_task))))
        ).then(
            pliteral("change").then(
                QuotableText("titles").then(
                    GreedyText("desc").runs(exe(edit_desc))))
        ).then(
            pliteral("done").then(
                QuotableText("titles").runs(exe(set_done)))
        ).then(
            pliteral("undone").then(
                QuotableText("titles").runs(exe(set_undone)))
        ).then(
            pliteral("deadline").then(
                QuotableText("titles").then(
                    Float("ddl").runs(exe(set_task_deadline))))
        ).then(
            pliteral("player").then(
                QuotableText("name").runs(exe(info_player)))
        ).then(
            pliteral("responsible", "res").then(
                QuotableText("titles").runs(exe(set_responsible)).then(
                    GreedyText("players").runs(exe(set_responsible))))
        ).then(
            pliteral("unresponsible", "unres").then(
                QuotableText("titles").runs(exe(rm_responsible)).then(
                    GreedyText("players").runs(exe(rm_responsible))))
        ).then(
            pliteral("list-responsibles", "list-res").then(
                QuotableText("titles").runs(exe(list_responsible)))
        ).on_child_error(CommandError, cmd_error, handled=True)
    )


# =================================
# |    Text process ultilities    |
# =================================


def tr(key: str, *args, lang=None):
    """
    Translate shortcut
    :param key:
    :param args:
    :param lang:
    :return:
    """
    return root.tr(key, *args, lang=lang)


def rclick(msg: str, hover: str, cmd: str, action: RAction = RAction.run_command,
           color: Optional[RColor] = None, style: Optional[RStyle] = None) -> RText:
    """
    RText shortcut with click events
    :param msg:
    :param hover:
    :param cmd:
    :param action:
    :param color:
    :param style:
    :return:
    """
    return RText(msg, color, style).h(hover).c(action, cmd)


def _player_info_simple(name: str, indent=8, removed=False) -> RTextList:
    """
    Player text with click events in a line
    :param name:
    :param indent:
    :param removed:
    :return:
    """
    return _indent_text(indent) + rclick(
        name, tr("mcd_task.info_player_hover"),
        "{} player {}".format(PREFIX, name),
        color=RColor.gold if not removed else RColor.dark_red,
        style=RStyle.strikethrough if removed else None
    )


def _task_info_simple(raw_titles: Union[TitleList, str],
                      full=False, sub=False, done=False, idt=None,
                      desc=False, desc_text: Optional[str] = None,
                      ddl=None):
    titles_commands = str(raw_titles).strip('.')
    titles = str(raw_titles) if full else TitleList(raw_titles).tail
    # Indent text
    if idt is None:
        idt = 8 if sub else 4
    indent = _indent_text(indent=idt)

    # Done button
    done_button = rclick(
        "⬛", tr("mcd_task.mark_task_undone_hover"),
        "{} undone {}".format(PREFIX, titles_commands),
        color=RColor.dark_gray
    )
    undone_button = rclick(
        "⬜", tr("mcd_task.mark_task_done_hover"),
        "{} done {}".format(PREFIX, titles_commands),
        color=RColor.white
    )
    button = done_button if done else undone_button

    # Task title
    title_text = rclick(
        titles, tr("mcd_task.info_task_hover"),
        "{} detail {}".format(PREFIX, titles_commands),
        color=RColor.dark_gray if done else RColor.yellow
    )

    # Rename task
    rename_task_button = rclick(
        "[✎]", tr("mcd_task.rename_task_hover"),
        "{} rename {} ".format(PREFIX, titles_commands),
        action=RAction.suggest_command
    ) if not sub else ''

    # Description
    if desc_text is not None or ddl is not None:
        if desc:
            description = RTextList()
            if desc_text is not None:
                description.append(
                    '\n', _indent_text(idt),
                    RText(desc_text, color=RColor.gray), ' ',
                    rclick(
                        "[✎]", tr("mcd_task.edit_task_hover"),
                        "{} change {} ".format(PREFIX, titles_commands),
                        action=RAction.suggest_command
                    ), ' ')
            if ddl is not None:
                if desc_text is None:
                    description.append('\n', _indent_text(idt))
                description.append(
                    rclick(
                        formatted_time(ddl), tr("mcd_task.set_ddl_hover"),
                        "{} deadline {} ".format(PREFIX, titles_commands),
                        action=RAction.suggest_command, color=RColor.gold
                    )
                )
        else:
            description = RTextList(
                rclick(
                    "[...]", tr("mcd_task.show_desc_hover"),
                    "{} detail {} ".format(PREFIX, titles_commands)
                )
            )
    else:
        description = ''

    return RTextList(
        indent, button, ' ', title_text, ' ', rename_task_button, description
    )


def _task_info_flexible(title: Union[TitleList, str], sub=False, idt=4):
    title = TitleList(title)
    target_task = root.task_manager[title]  # type: TaskBase
    desc = target_task.description
    text = RTextList(
        '\n',
        _task_info_simple(
            target_task.full_path(), sub=sub, done=target_task.done,
            idt=idt, desc=not sub, desc_text=desc if desc != '' else None,
            ddl=target_task.deadline if target_task.deadline != 0 else None
        )
    )
    if len(target_task.sub_tasks) == 0:
        return text
    for t in target_task.sub_tasks:
        text.append(
            _task_info_flexible(t.full_path(), sub=True, idt=idt + 4)
        )
    return text


def _indent_text(indent: int) -> str:
    """
    Get actual indent strings from integer
    :param indent:
    :return:
    """
    ret = ''
    for num in range(indent):
        ret += ' '
    return ret


def formatted_time(timestamp: float, locale: Optional[str] = None) -> str:
    """
    Format time text with specified locale
    :param timestamp:
    :param locale:
    :return:
    """
    return time.strftime(tr("mcd_task.time_format", lang=locale), time.localtime(timestamp))


def _add_task_button(title: str = None):
    # Add button
    title_path = '' if title in ['', None] else '{}.'.format(title)
    return rclick(
        '[+]', tr("mcd_task.add_task_hover"), '{} add {}'.format(PREFIX, title_path),
        action=RAction.suggest_command, color=RColor.red, style=RStyle.bold
    )


def _info_task(title: Optional[str] = None, done=False) -> Optional[RTextList]:
    target_task = None
    if title is not None:
        title = title.strip(".")
        try:
            target_task = root.task_manager[title]
        except TaskNotFoundError:
            target_task = None  # type: Optional[TaskBase]

    text = RTextList()

    # Task tree
    if target_task is None:
        for t in root.task_manager.split_sub_tasks_by_done()[0 if not done else 1]:  # type: Task
            text.append('\n', _task_info_simple(t.full_path(), sub=True, done=t.done, desc=False, idt=4,
                                                desc_text=t.description if t.description != '' else None))
        if not done:
            text.append(
                '\n', _indent_text(4),
                rclick(tr("mcd_task.done_task_button"), tr("mcd_task.done_task_hover"), "{} list-done".format(PREFIX),
                       color=RColor.dark_gray)
            )
    else:
        text.append(_task_info_flexible(target_task.full_path(), sub=False))
    return text


def _source_name(source: CommandSource):
    if isinstance(source, PlayerCommandSource):
        return source.player
    else:
        return source.__class__.__name__


# =========================
# |    Command Actions    |
# =========================

# Errors
def cmd_error(source: CommandSource):
    source.reply(
        rclick(tr("mcd_task.cmd_error"), tr("mcd_task.get_help"), "{} help".format(PREFIX), color=RColor.red)
    )


def task_not_found(source: CommandSource):
    source.reply(
        rclick(tr("mcd_task.task_not_found"), tr("mcd_task.task_not_found_hover", PREFIX), PREFIX, color=RColor.red)
    )


def task_already_exist(source: CommandSource):
    source.reply(
        rclick(tr("mcd_task.task_already_exist"), tr("mcd_task.task_not_found_hover", PREFIX), PREFIX, color=RColor.red)
    )


def illegal_call(source: CommandSource):
    source.reply(
        RText(tr("mcd_task.illegal_call"), color=RColor.red)
    )


# Infos
def info_player(source: CommandSource, name: str) -> None:
    tasks = root.task_manager.get_responsible_manager()[name]
    text = RTextList(
        RText(tr("mcd_task.player_tasks_title", name, str(len(tasks))), color=RColor.green, styles=RStyle.bold),
    )
    for t in tasks:
        tdone = root.task_manager[t].done
        text.append('\n', _task_info_simple(t, full=True, done=tdone, idt=4, sub=False))

    source.reply(text)


def info_task(source: CommandSource, title: Optional[str] = None, prefix=None, done=False) -> None:
    # Task list
    try:
        task_list = _info_task(title, done=done)
    except TaskNotFoundError:
        task_not_found(source)
        if DEBUG_MODE:
            raise
        return

    # Prefix text
    if prefix is None:
        prefix = tr("mcd_task.info_task_title" if title is None else "mcd_task.info_task_single_title")
    pref_text = RText(prefix, color=RColor.green, styles=RStyle.bold)

    add_button = _add_task_button(title)

    text = RTextList(pref_text, add_button, task_list)
    if text is not None:
        source.reply(text)


# Others
def set_task_deadline(source: CommandSource, titles: str, ddl: str) -> None:
    if not root.task_manager.exists(TitleList(titles)):
        task_not_found(source)
        return
    deadline = float(time.time()) + float(ddl) * 3600 * 24
    root.task_manager.set_deadline(TitleList(titles), deadline)
    source.reply(
        tr("mcd_task.ddl_set", titles,
           ddl, formatted_time(deadline))
    )
    root.log(f"{_source_name(source)} set task deadline to {formatted_time(deadline, locale='en_us')}")


def list_task(source: CommandSource):
    info_task(source)


def show_help(source: CommandSource):
    meta = source.get_server().get_plugin_metadata('mcd_task')
    help_message = source.get_server().tr('mcd_task.help_msg').format(PREFIX, meta.name, str(meta.version))
    help_msg_rtext = ''
    symbol = 0
    for line in help_message.splitlines():
        if help_msg_rtext != '':
            help_msg_rtext += '\n'
        result = re.search(r'(?<=§7){}[\S ]*?(?=§)'.format(PREFIX), line)
        if result is not None and symbol != 2:
            cmd = result.group().strip() + ' '
            help_msg_rtext += RText(line).c(RAction.suggest_command, cmd).h(
                tr("mcd_task.help_msg_suggest_hover", cmd.strip()))
            symbol = 1
        else:
            help_msg_rtext += line
            if symbol == 1:
                symbol += 1
    source.reply(help_msg_rtext)


def add_task(source: CommandSource, titles: str, desc: str = ''):
    titles = TitleList(titles)
    titles_for_text = titles.copy()
    if not root.task_manager.exists(titles):
        root.task_manager.add_task(titles, desc=desc)
        info_task(source, title=titles_for_text.head, prefix=tr("mcd_task.new_task_created"))
        root.log(f"{_source_name(source)} created new task named {str(titles_for_text)}")
    else:
        task_already_exist(source)


def all_tasks_detail(source: CommandSource):
    task_details = RTextList()
    for task in root.task_manager.sub_tasks:
        task_details.append(_task_info_flexible(task.full_path(), sub=False, idt=4))
    prefix = RText(tr("mcd_task.detailed_info_task_title"), color=RColor.green, styles=RStyle.bold)
    add_button = _add_task_button()
    source.reply(prefix + add_button + task_details)


def remove_task(source: CommandSource, titles: str):
    if not root.task_manager.exists(TitleList(titles)):
        task_not_found(source)
        return
    root.task_manager.delete_task(TitleList(titles))
    source.reply(tr("mcd_task.deleted_task", "§e{}§r".format(titles)))
    root.log(f"{_source_name(source)} deleted task {titles}")


def rename_task(source: CommandSource, old_titles: str, new_title: str) -> None:
    if not root.task_manager.exists(TitleList(old_titles)):
        task_not_found(source)
        return
    if '.' in list(new_title):
        source.reply(tr("mcd_task.illegal_title_with_dot", new_title))
        return
    root.task_manager.rename_task(TitleList(old_titles), new_title)
    new_titles = TitleList(old_titles)
    new_titles.pop_tail()
    new_titles.append(new_title)
    info_task(source, title=str(new_titles), prefix=tr("mcd_task.task_renamed", old_titles, str(new_titles)))
    root.log(f"{_source_name(source)} renamed {old_titles} to {str(new_titles)}")


def edit_desc(source: CommandSource, titles: str, desc: str) -> None:
    title_list = TitleList(titles)
    if not root.task_manager.exists(title_list):
        task_not_found(source)
        return
    root.task_manager.edit_desc(title_list, desc)
    info_task(source, title=titles)
    root.log(f"{_source_name(source)} changed task {titles} description to {desc}")


def set_done(source: CommandSource, titles: str) -> None:
    if not root.task_manager.exists(TitleList(titles)):
        task_not_found(source)
        return
    root.task_manager.done_task(TitleList(titles))
    info_task(source, title=titles)
    root.log(f"{_source_name(source)} marked task {titles} as done")


def set_undone(source: CommandSource, titles: str) -> None:
    if not root.task_manager.exists(TitleList(titles)):
        task_not_found(source)
        return
    root.task_manager.undone_task(TitleList(titles))
    info_task(source, title=titles)
    root.log(f"{_source_name(source)} marked task {titles} as undone")


def list_done(source: CommandSource):
    info_task(source, prefix=tr("mcd_task.done_task_list_title"), done=True)


def set_responsible(source: CommandSource, titles: str, players: Optional[str] = None) -> None:
    if not root.task_manager.exists(TitleList(titles)):
        task_not_found(source)
        return
    if players is None:
        if isinstance(source, PlayerCommandSource):
            players = source.player
        else:
            illegal_call(source)
            return
    players = players.split(' ')
    num = root.task_manager.set_responsible(TitleList(titles), *players)
    list_responsible(source, titles, prefix=tr("mcd_task.added_responsibles_title", num))
    root.log(f"{_source_name(source)} added responsibles for task {str(titles)}: {str(players)}")


def rm_responsible(source: CommandSource, titles: str, players: Optional[str] = None) -> None:
    if not root.task_manager.exists(TitleList(titles)):
        task_not_found(source)
        return
    if players is None:
        if isinstance(source, PlayerCommandSource):
            players = source.player
        else:
            illegal_call(source)
            return
    players = players.split('.')
    removed = root.task_manager.rm_responsible(TitleList(titles), *players)
    num = len(removed)
    list_responsible(source, titles, player_removed=removed,
                     prefix=tr("mcd_task.removed_responsibles_title", num))
    root.log(f"{_source_name(source)} removed responsibles for task {str}: {str(players)}")


def list_responsible(source: CommandSource, titles: str, player_removed=None, prefix=None) -> None:
    if not root.task_manager.exists(TitleList(titles)):
        task_not_found(source)
        return
    if player_removed is None:
        player_removed = []
    player_list = root.task_manager.get_responsible_manager().get_responsibles(titles)
    num = len(player_list)
    task_done = root.task_manager[titles].done
    text = RTextList(
        RText(tr("mcd_task.list_responsible_title", num) if prefix is None else prefix, RColor.green, RStyle.bold),
        '\n', _task_info_simple(titles, full=True, sub=True, done=task_done, idt=4)
    )
    for p in player_list:
        text.append(
            '\n',
            _player_info_simple(p, indent=8)
        )
    if player_removed is not None:
        for p in player_removed:
            text.append(
                '\n',
                _player_info_simple(p, indent=8, removed=True)
            )
    source.reply(text)


def inherit_responsible(info: Info, old_name: str, new_name: str, debug=False):
    resm = root.task_manager.get_responsible_manager()
    resm.rename_player(old_name, new_name)
    num = len(resm[new_name])
    info.get_server().tell(new_name, tr("mcd_task.on_player_renamed", num))
    root.logger.debug(tr("mcd_task.on_player_renamed", num), no_check=debug)
    root.log(f"Detected player rename {old_name} -> {new_name}. Inherited {num} task(s)")


def task_timed_out(server: PluginServerInterface, player: str, player_tasks: List[TaskBase]):
    text = RTextList(RText(tr("mcd_task.on_player_joined", len(player_tasks)), color=RColor.red, styles=RStyle.bold))
    for t in player_tasks:
        text.append('\n', _task_info_simple(t.full_path(), full=True, sub=True, done=t.done, idt=4))
    server.tell(player, text)
