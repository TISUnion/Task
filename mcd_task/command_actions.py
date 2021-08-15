import re
import time

from typing import Callable, Any, Optional, Union
from mcdreforged.api.all import *

from mcd_task.globals import *
from mcd_task.task_manager import TitleList, TaskNotFoundError


# ===============================
# |    Register Command Tree    |
# ===============================


def register_cmd_tree(server: PluginServerInterface):
    def pliteral(literal: Union[set, str]) -> Literal:
        lvl = root.config['permission.{}'.format(literal)]
        lvl = lvl if isinstance(lvl, int) else 0
        return Literal(literal).requires(
            lambda src: src.has_permission(lvl),
            failure_message_getter=lambda: server.tr('mcd_task.perm_denied').format(lvl)
        )

    def exe(func: Callable[[CommandSource, str], Any]):
        return lambda src, **ctx: func(src, **ctx)

    server.register_command(
        Literal(PREFIX).on_child_error(CommandError, cmd_error, handled=True).runs(info_task).then(
            pliteral("list").runs(info_task)
        ).then(
            pliteral("help").runs(show_help)
        ).then(
            pliteral("detail").then(
                QuotableText("titles").runs(exe(info_task)))
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
            pliteral("group").then(
                Literal("info").then(
                    QuotableText("title").runs(exe(info_group))
                )
            ).then(
                Literal("create").then(
                    GreedyText("players").runs(exe(new_group)))
            ).then(
                Literal("rename").then(
                    QuotableText("old_title").then(
                        QuotableText("new_title").runs(exe(rename_group))))
            ).then(
                Literal("append").then(
                    QuotableText("title").then(
                        GreedyText("players").runs(exe(group_append_player))))
            ).then(
                Literal("remove").then(
                    QuotableText("title").then(
                        GreedyText("players").runs(exe(group_remove_player))))
            )
        ).then(
            pliteral("deadline").then(
                QuotableText("titles").then(
                    QuotableText("ddl")))
        ).then(
            pliteral("player").then(
                QuotableText("name").runs(exe(info_player)))
        ).then(
            pliteral({"res", "responsible"}).then(
                QuotableText("titles").runs(exe(set_responsible)).then(
                    GreedyText("players").runs(exe(set_responsible))))
        ).then(
            pliteral({"unres", "unresponsible"}).then(
                QuotableText("titles").runs(exe(set_responsible)).then(
                    GreedyText("players").runs(exe(set_responsible))))
        )
    )


# =================================
# |    Text process ultilities    |
# =================================


def tr(key: str, *args, **kwargs):
    """
    Translate shortcut
    :param key:
    :param args:
    :param kwargs:
    :return:
    """
    return root.tr(key, *args, **kwargs)


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


def _info_group(title: str, indent=4) -> RTextList:
    """
    Group text with click events in a line
    :param title:
    :param indent:
    :return:
    """
    return RTextList(
        _indent_text(indent),
        rclick(title, tr("mcd_task.info_group_hover"),
               '{} group info {}'.format(PREFIX, title), color=RColor.yellow),
        ' ',
        rclick("[✎]", tr("mcd_task.rename_group_hover"),
               '{} group rename {} '.format(PREFIX, title), color=RColor.white, action=RAction.suggest_command),
        ' ',
        rclick("[+]", tr("mcd_task.append_group_hover"),
               '{} group append {} '.format(PREFIX, title), color=RColor.red)
    )


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
        "{} player {}",
        color=RColor.gold if not removed else RColor.dark_red,
        style=RStyle.strikethrough if removed else None
    )


def _task_info_simple(raw_titles: Union[TitleList, str], sub=False, done=False, idt=None, desc=False) -> RTextList:
    """
    Task text with click events in a line
    :param raw_titles:
    :param sub:
    :param done:
    :return:
    """
    titles = str(raw_titles)
    # Indent text
    if idt is None:
        idt = 8 if sub else 4
    indent = _indent_text(indent=idt)

    # Done button
    done_button = rclick(
        "⬛", tr("mcd_task.mark_task_undone_hover"),
        "{} undone {}".format(PREFIX, titles),
        color=RColor.dark_gray
    )
    undone_button = rclick(
        "⬜", tr("mcd_task.mark_task_done_hover"),
        "{} done {}".format(PREFIX, titles),
        color=RColor.white
    )
    button = done_button if done else undone_button

    # Task title
    title_text = rclick(
        titles, tr("mcd_task.info_task_hover"),
        "{} info {}".format(PREFIX, titles),
        color=RColor.dark_gray if done else RColor.yellow
    )

    # Rename task
    rename_task_button = rclick(
        "[✎]", tr("mcd_task.rename_task_hover"),
        "{} rename {} ".format(PREFIX, titles),
        action=RAction.suggest_command
    ) if not sub else ''

    # Description
    desc_text = root.task_manager[titles].desc
    description = ''
    if desc_text != '':
        description = RTextList(
            '\n',
            RText(desc_text, color=RColor.light_gray),
            rclick(
                "[✎]", tr("mcd_task.edit_task_hover"),
                "{} change {} ".format(PREFIX, titles),
                action=RAction.suggest_command
            )) if desc else RTextList(
                ' ',
                rclick(
                    "[...]", tr("mcd_task.show_desc_hover"),
                    "{} detail {} ".format(PREFIX, titles),
                    action=RAction.suggest_command
                )
            )

    return RTextList(
        indent, button, title_text, rename_task_button, description
    )


def _task_info_flexible(title: Union[TitleList, str], sub=False, idt=4):
    title = TitleList(title)
    target_task = root.task_manager[title]
    text = RTextList('\n', _task_info_simple(title.tail, sub=sub, done=target_task.done, idt=idt, desc=not sub))
    for t in target_task.sub_tasks:
        text.append(
            '\n', _task_info_flexible(t.title, sub=True, idt=idt + 4)
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
    title_path = '' if title is None else '{}.'.format(title)
    return rclick(
        '[+]', tr("mcd_task.add_task_hover"), '{} add {}'.format(PREFIX, title_path),
        action=RAction.suggest_command, color=RColor.red, style=RStyle.bold
    )


def _info_task(source: CommandSource, title: Optional[str] = None, done=False) -> Optional[RTextList]:
    target_task = None
    if title is not None:
        title = title.strip(".")
        try:
            target_task = root.task_manager[title]
        except TaskNotFoundError:
            task_not_found(source)
            return None

    text = RTextList()

    # Task tree
    if target_task is None:
        for t in root.task_manager.split_sub_tasks_by_done()[0 if not done else 1]:
            text.append('\n', _task_info_simple(t.title, sub=True, done=t.done, idt=4))
        text.append(
            '\n', _indent_text(4),
            rclick(tr("mcd_task.done_task_button"), tr("mcd_task.done_task_hover"), "{} list-done",
                   color=RColor.dark_gray)
        )
    else:
        text.append(_task_info_flexible(target_task.title, sub=False))
    return text


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


# Infos
def info_player(source: CommandSource, name: str) -> None:
    tasks = root.task_manager.get_responsible_manager().get_player_tasks(name)
    text = RTextList(
        RText(tr("mcd_task.player_tasks_title", name, str(len(tasks))), color=RColor.green, styles=RColor.bold),
    )
    for t in tasks:
        tdone = root.task_manager[t].done
        text.append('\n', _task_info_simple(t, done=tdone, idt=4, sub=False, desc=False))

    groups = root.task_manager.get_responsible_manager().get_player_group_titles(name)
    text.append(
        RText(tr("mcd_task.player_groups_title", name, len(groups)), color=RColor.green, styles=RStyle.bold)
    )
    for gr in groups:
        text.append('\n', _info_group(gr))
    source.reply(text)


def info_group(source: CommandSource, title: str, prefix=None) -> None:
    text = RTextList(
        RText(tr("mcd_task.info_group") if prefix is None else prefix, color=RColor.green, styles=RStyle.bold),
        '\n',
        _info_group(title)
    )
    target_resg = root.task_manager.get_responsible_manager()[title]
    for player in target_resg.players:
        text.append('\n', _player_info_simple(player))
    # Current tasks
    if len(target_resg.tasks) == 0:
        text.append('\n' + tr("mcd_task.group_has_no_task"))
    else:
        text.append('\n' + tr("mcd_task.group_task_list_head"))
        for t in target_resg.tasks:
            task_done = root.task_manager[t].done
            text.append('\n', _task_info_simple(t, done=task_done))
    source.reply(text)


def info_task(source: CommandSource, title: Optional[str] = None, prefix=None, done=False) -> None:
    # Task list
    task_list = _info_task(source, title, done=done)
    if task_list is None:
        return

    # Prefix text
    if prefix is None:
        prefix = tr("mcd_task.task_info_list_title" if title is None else "mcd_task.info_task_single_title")
    pref_text = RText(prefix, color=RColor.green, styles=RStyle.bold)

    add_button = _add_task_button(title)

    text = RTextList(pref_text, add_button, task_list)
    if text is not None:
        source.reply(text)


# Others
def set_task_deadline(source: CommandSource, titles: str, ddl: str) -> None:
    try:
        target_task = root.task_manager[TitleList(titles)]
    except TaskNotFoundError:
        task_not_found(source)
        return
    try:
        period = float(ddl) * 3600 * 24
    except ValueError:
        errcmd = "{} deadline {} ".format(PREFIX, titles)
        source.reply(
            rclick(tr("mcd_task.invalid_number"),
                   tr("mcd_task.resuggest_cmd_hover", errcmd),
                   errcmd, color=RColor.red)
        )
    else:
        deadline = float(time.time()) + period
        target_task.set_deadline(deadline)
        source.reply(
            RText(tr("mcd_task.ddl_set",
                     str(target_task.full_path()), ddl, formatted_time(deadline)), color=RColor.yellow)
        )


def group_remove_player(source: CommandSource, title: str, players: str) -> None:
    resm = root.task_manager.get_responsible_manager()
    player_list = set(players.split(' '))
    removed = resm[title].remove(*player_list)
    text = RTextList(
        RText(tr("mcd_task.group_removed_player",
                 str(len(removed))), color=RColor.green, styles=RStyle.bold),
        _info_group(title, indent=4)
    )
    for p in resm[title].players:
        text.append('\n', _player_info_simple(p))
    for p in removed:
        text.append('\n', _player_info_simple(p, removed=True))
    source.reply(text)


def group_append_player(source: CommandSource, title: str, players: str):
    resm = root.task_manager.get_responsible_manager()
    player_list = set(players.split(' '))
    added = resm[title].append(*player_list)
    text = RTextList(
        RText(tr("mcd_task.group_appended_player", str(len(added))), color=RColor.green, styles=RStyle.bold),
        _info_group(title)
    )
    for p in resm[title].players:
        text.append('\n', _player_info_simple(p))
    source.reply(text)


def rename_group(source: CommandSource, old_tile: str, new_title: str):
    root.task_manager.get_responsible_manager().rename(TitleList(old_tile), TitleList(new_title))
    info_group(source, new_title, prefix=tr("mcd_task.group_renamed"))


def new_group(source: CommandSource, players: str):
    resm = root.task_manager.get_responsible_manager()
    title = resm.new(*list(players.split(' ')))
    target_resg = resm[title]
    text = RTextList(
        tr("mcd_task.group_added"),
        '\n',
        _info_group(title),
    )
    for player in target_resg.players:
        text.append('\n', _player_info_simple(player))
    source.reply(text)


def show_help(source: CommandSource):
    meta = source.get_server().get_plugin_metadata('mcd_task')
    help_message = source.get_server().tr('mcd_task.help_msg').format(PREFIX, meta.name, str(meta.version))
    help_msg_rtext = RTextList()
    for line in help_message.splitlines():
        result = re.search(r'(?<=§7){}[\S ]*?(?=§)'.format(PREFIX), line)
        if result is not None:
            cmd = result.group() + ' '
            help_msg_rtext.append(RText(line).c(RAction.suggest_command, cmd).h('点击以填入 §7{}§r'.format(cmd)))
        else:
            help_msg_rtext.append(line)
        if line != help_message.splitlines()[-1]:
            help_msg_rtext.append('\n')
    source.reply(help_msg_rtext)


def add_task(source: CommandSource, titles: str, desc: str = ''):
    titles = TitleList(titles)
    title = titles.pop_tail()
    father = root.task_manager[title]
    if title not in father.child_titles:
        father.add_task(titles.removed, desc=desc)
    else:
        task_already_exist(source)
        return
    info_task(source, title, tr("mcd_task.new_task_created"))


def all_tasks_detail(source: CommandSource):
    task_details = RTextList()
    for task in root.task_manager.sub_tasks:
        task_details.append(_task_info_flexible(task.title, sub=False, idt=4))
    prefix = RText(tr("mcd_task.detailed_info_task_title"), color=RColor.green, styles=RStyle.bold)
    add_button = _add_task_button()
    source.reply(prefix + add_button + task_details)


def remove_task(source: CommandSource, titles: str):
    root.task_manager.delete_task(TitleList(titles))
    source.reply(tr("mcd_task.deleted_task", "§e{}§r".format(titles)))


def rename_task(source: CommandSource, old_titles: str, new_title: str) -> None:
    if '.' in list(new_title):
        source.reply(tr("mcd_task.illegal_title_with_dot", new_title))
    root.task_manager.rename_task(TitleList(old_titles))
    new_titles = TitleList(old_titles)
    new_titles.pop_tail()
    new_titles.append(new_title)
    info_task(source, str(new_titles))


def edit_desc(source: CommandSource, titles: str, desc: str) -> None:
    title_list = TitleList(titles)
    root.task_manager.edit_desc(title_list, desc)
    info_task(source, titles)


def set_done(source: CommandSource, titles: str) -> None:
    root.task_manager.done_task(TitleList(titles))
    info_task(source, titles)


def set_undone(source: CommandSource, titles: str) -> None:
    root.task_manager.undone_task(TitleList(titles))
    info_task(source, titles)


def list_done(source: CommandSource):
    info_task(source, prefix=tr("mcd_task.done_task_list_title"), done=True)


def set_responsible(source: CommandSource, players: str) -> None:
    pass


def rm_responsible(source: CommandSource, players: str) -> None:
    pass
