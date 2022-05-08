import time
from typing import Optional, Union, List

from mcdreforged.api.all import *

from mcd_task.global_variables import GlobalVariables
from mcd_task.constants import PREFIX, DEBUG_MODE
from mcd_task.exceptions import TaskNotFound
from mcd_task.task_manager import TitleList, TaskBase, Task


# ===============================
# |    Register Command Tree    |
# ===============================


def register_cmd_tree(server: PluginServerInterface):
    def permed_literal(*literal: str) -> Literal:
        lvl = GlobalVariables.config.get_permission(literal[0])
        lvl = lvl if isinstance(lvl, int) else 0
        return Literal(literal).requires(
            lambda src: src.has_permission(lvl),
            failure_message_getter=lambda: server.rtr('mcd_task.perm_denied', lvl)
        )

    def ensure_task_exist_quotable_text(title: str = 'title'):
        return QuotableText(title).requires(
            lambda src, ctx: GlobalVariables.task_manager.exists(TitleList(ctx[title])),
            lambda: tr("mcd_task.task_not_found").h(
                tr("mcd_task.task_not_found_hover", PREFIX)).c(
                RAction.run_command, f'{PREFIX} list').set_color(
                RColor.red
            )
        )

    def ensure_task_not_exist_quotable_text(title: str = 'title'):
        def ensure_not_exist(source: CommandSource, context: CommandContext):
            return not GlobalVariables.task_manager.exists(TitleList(context[title]))

        return QuotableText(title).requires(
            ensure_not_exist,
            lambda: tr("mcd_task.task_already_exist").h(
                tr("mcd_task.task_not_found_hover", PREFIX)).c(
                RAction.run_command, f'{PREFIX} list').set_color(
                RColor.red
            )
        )

    root_func = task_overview if GlobalVariables.config.default_overview_instead_of_list else list_task
    root_node = Literal(PREFIX).runs(lambda src: root_func(src))
    nodes = [
        permed_literal('overview').runs(lambda src: task_overview(src)),
        permed_literal('list').runs(lambda src: list_task(src)),
        permed_literal('help').runs(lambda src: show_help(src)),
        permed_literal('detail').then(
            ensure_task_exist_quotable_text().runs(lambda src, ctx: info_task(src, title=ctx['title']))
        ),
        permed_literal('detail-all').runs(lambda src: all_tasks_detail(src)),
        permed_literal('list-done').runs(lambda src: list_done(src)),
        permed_literal('add').then(
            ensure_task_not_exist_quotable_text().runs(lambda src, ctx: add_task(src, ctx['title'])).then(
                GreedyText('description').runs(lambda src, ctx: add_task(src, ctx['title'], ctx['description']))
            )
        ),
        permed_literal('remove', 'rm').then(
            ensure_task_exist_quotable_text().runs(lambda src, ctx: remove_task(src, ctx['title']))
        ),
        permed_literal('rename').then(
            ensure_task_exist_quotable_text('old_titles').then(
                QuotableText('new_title').runs(lambda src, ctx: rename_task(src, ctx['old_titles'], ctx['new_title']))
            )
        ),
        permed_literal('change').then(
            ensure_task_exist_quotable_text().then(
                GreedyText('description').runs(lambda src, ctx: edit_desc(src, ctx['title'], ctx['description']))
            )
        ),
        permed_literal('done').then(
            ensure_task_exist_quotable_text().runs(lambda src, ctx: set_done(src, ctx['title']))
        ),
        permed_literal('undone').then(
            ensure_task_exist_quotable_text().runs(lambda src, ctx: set_undone(src, ctx['title']))
        ),
        permed_literal('deadline').then(
            ensure_task_exist_quotable_text().then(
                Number('days').runs(lambda src, ctx: set_task_deadline(src, ctx['title'], ctx['days']))
            )
        ),
        permed_literal('player').then(
            QuotableText('name').runs(lambda src, ctx: info_player(src, ctx['name']))
        ),
        permed_literal("responsible", "res").then(
            ensure_task_exist_quotable_text().runs(lambda src, ctx: set_responsible(src, ctx['title'])).then(
                GreedyText("players").runs(lambda src, ctx: set_responsible(src, ctx['title'], ctx['players']))
            )
        ),
        permed_literal("unresponsible", "unres").then(
            ensure_task_exist_quotable_text().runs(lambda src, ctx: rm_responsible(src, ctx['title'])).then(
                GreedyText("players").runs(lambda src, ctx: rm_responsible(src, ctx['title'], ctx['players']))
            )
        ),
        permed_literal("list-responsibles", "list-res").then(
            ensure_task_exist_quotable_text().runs(lambda src, ctx: list_responsible(src, ctx['title']))
        ),
        permed_literal('priority').then(
            ensure_task_exist_quotable_text().then(
                Literal('clear').runs(lambda src, ctx: set_task_priority(src, ctx['title']))
            ).then(
                Integer('priority').runs(lambda src, ctx: set_task_priority(src, ctx['title'], ctx['priority']))
            )
        ),
        permed_literal('reload').runs(lambda src: reload_self(src))
    ]
    for node in nodes:
        GlobalVariables.debug(f'Registered cmd "{PREFIX} {list(node.literals)[0]}"')
        root_node.then(node)
    server.register_command(root_node)


# =================================
# |    Text process utilities    |
# =================================


def tr(key: str, *args, **kwargs):
    """
    Translate shortcut
    :param key:
    :param args:
    :param kwargs:
    :return:
    """
    return GlobalVariables.tr(key, *args, **kwargs)


def rclick(msg: Union[RTextMCDRTranslation, str], hover: str, cmd: str, action: RAction = RAction.run_command,
           color: Optional[RColor] = None, style: Optional[RStyle] = None) -> RTextBase:
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
    if isinstance(msg, RTextMCDRTranslation):
        rt = msg.h(hover).c(action, cmd)
        if color is not None:
            rt.set_color(color)
        if style is not None:
            rt.set_styles(style)
        return rt
    return RText(msg, color, style).h(hover).c(action, cmd)


def _player_info_simple(name: str, indent=8, removed=False) -> RTextList:
    """
    Generate player text with click events in a line
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
                      ddl=None, priority=None):
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
    if desc_text is not None or ddl is not None or priority is not None:
        if desc:
            description = ['']
            if desc_text is not None:
                description.append(RTextList(
                    _indent_text(idt),
                    RText(desc_text, color=RColor.gray), ' ',
                    rclick(
                        "[✎]", tr("mcd_task.edit_task_hover"),
                        "{} change {} ".format(PREFIX, titles_commands),
                        action=RAction.suggest_command
                    ), ' '
                ))
            if ddl is not None:
                description.append(RTextList(
                    _indent_text(idt),
                    rclick(
                        formatted_time(ddl), tr("mcd_task.set_ddl_hover"),
                        "{} deadline {} ".format(PREFIX, titles_commands),
                        action=RAction.suggest_command, color=RColor.red
                    )
                ))
            if priority is not None:
                description.append(RTextList(
                    _indent_text(idt),
                    tr('mcd_task.detail_priority', priority).set_color(RColor.gold).c(
                        RAction.suggest_command, "{} priority {} ".format(PREFIX, titles_commands)).h(
                        tr('mcd_task.priority_hover')
                    )
                ))
            description = RTextBase.join('\n', description)
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
    target_task = GlobalVariables.task_manager[title]  # type: TaskBase
    desc = target_task.description
    text = RTextList(
        '\n',
        _task_info_simple(
            target_task.full_path(), sub=sub, done=target_task.done,
            idt=idt, desc=not sub, desc_text=desc if desc != '' else None,
            ddl=target_task.deadline if target_task.deadline != 0 else None,
            priority=target_task.priority
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
    return time.strftime(GlobalVariables.server.tr("mcd_task.time_format", lang=locale), time.localtime(timestamp))


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
            target_task = GlobalVariables.task_manager[title]
        except TaskNotFound:
            target_task = None  # type: Optional[TaskBase]

    text = RTextList()

    # Task tree
    if target_task is None:
        for t in GlobalVariables.task_manager.split_sub_tasks_by_done()[0 if not done else 1]:  # type: Task
            text.append('\n', _task_info_simple(t.full_path(), sub=True, done=t.done, desc=False, idt=4,
                                                desc_text=t.description if t.description != '' else None))
        if not done:
            text.append(
                '\n', _indent_text(4),
                tr("mcd_task.done_task_button").set_hover_text(tr("mcd_task.done_task_hover")).set_click_event(
                    RAction.run_command, "{} list-done".format(PREFIX)).set_color(RColor.dark_gray)
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

list_cmd = f"{PREFIX} list"


# Errors
def cmd_error(source: CommandSource, exception: CommandError):
    if isinstance(exception, RequirementNotMet):
        if exception.has_custom_reason():
            source.reply(exception.get_reason().set_color(RColor.red))
            return
    source.reply(
        tr("mcd_task.cmd_error").set_color(RColor.red).h(
            tr("mcd_task.get_help")).c(RAction.run_command, "{} help".format(PREFIX))
    )


def task_not_found(source: CommandSource):
    source.reply(tr("mcd_task.task_not_found").h(tr("mcd_task.task_not_found_hover", list_cmd)).set_color(RColor.red).c(
        RAction.run_command, list_cmd
    )
    )


def task_already_exist(source: CommandSource):
    source.reply(tr("mcd_task.task_already_exist").set_color(RColor.red).c(RAction.run_command, f'{PREFIX} list').h(
        tr("mcd_task.task_not_found_hover", PREFIX)
    )
    )


def illegal_call(source: CommandSource):
    source.reply(tr('mcd_task.illegal_call').set_color(RColor.red))


# Info
def info_player(source: CommandSource, name: str) -> None:
    tasks = GlobalVariables.task_manager.get_responsible_manager()[name]
    text = RTextList(
        tr("mcd_task.player_tasks_title", name, str(len(tasks))).set_color(RColor.green).set_styles(RStyle.bold),
    )
    for t in tasks:
        task_status = GlobalVariables.task_manager[t].done
        text.append('\n', _task_info_simple(t, full=True, done=task_status, idt=4, sub=False))

    source.reply(text)


def info_task(source: CommandSource, title: Optional[str] = None, prefix=None, done=False) -> None:
    # Task list
    try:
        task_list = _info_task(title, done=done)
    except TaskNotFound:
        task_not_found(source)
        if DEBUG_MODE:
            raise
        return

    # Prefix text
    if prefix is None:
        prefix = tr("mcd_task.info_task_title" if title is None else "mcd_task.info_task_single_title"
                    ).set_color(RColor.green).set_styles(RStyle.bold)

    add_button = _add_task_button(title)

    text = RTextList(prefix, add_button, task_list)
    if text is not None:
        source.reply(text)


# Others
def set_task_deadline(source: CommandSource, titles: str, ddl: str) -> None:
    deadline = float(time.time()) + float(ddl) * 3600 * 24
    GlobalVariables.task_manager.set_deadline(TitleList(titles), deadline)
    source.reply(
        tr("mcd_task.ddl_set", titles, ddl, formatted_time(deadline)).set_color(RColor.green).set_styles(RStyle.bold)
    )
    GlobalVariables.log(
        f"{_source_name(source)} set task {titles} deadline to {formatted_time(deadline, locale='en_us')}"
    )


def list_task(source: CommandSource):
    info_task(source)


def task_overview(source: CommandSource):
    GlobalVariables.debug('Running overview...')
    headline = tr('mcd_task.overview_headline').set_styles(RStyle.bold).set_color(RColor.green)

    deadline_approaching = GlobalVariables.task_manager.seek_for_item_with_deadline_approaching()
    GlobalVariables.debug(deadline_approaching)
    max_length = GlobalVariables.config.overview_maximum_task_amount
    priority_amount = max_length - len(deadline_approaching)
    with_priorities = []
    if priority_amount > 0:
        with_priorities = GlobalVariables.task_manager.seek_for_item_with_priority()

    if len(deadline_approaching) == 0 and len(with_priorities) == 0:
        task_text = tr('mcd_task.no_priority').set_color(RColor.yellow)
    else:
        task_texts = {}
        for task in deadline_approaching:
            if len(task_texts) >= GlobalVariables.config.overview_maximum_task_amount:
                break
            task_texts[task.full_path()] = RText('[!] ', RColor.red).h(
                tr('mcd_task.date_approaching', formatted_time(task.deadline))
            ) + _task_info_simple(
                task.full_path(), full=True, done=task.done, idt=4, sub=False).set_color(
                RColor.red
            )
        for task in with_priorities:
            if len(task_texts) >= GlobalVariables.config.overview_maximum_task_amount:
                break
            if task.title not in task_texts.keys():
                task_texts[task.full_path()] = RText('[!] ', RColor.gold).h(
                    tr('mcd_task.has_a_high_priority', task.priority)
                ) + _task_info_simple(
                    task.full_path(), full=True, done=task.done, idt=4, sub=False).set_color(
                    RColor.gold
                )
        task_text = RTextBase.join('\n', task_texts.values())

    help_message = tr('mcd_task.overview_help', PREFIX).set_translator(GlobalVariables.htr)

    source.reply(RTextBase.join('\n', [headline, task_text, help_message]))


def set_task_priority(source: CommandSource, titles: str, priority: Optional[int] = None):
    GlobalVariables.task_manager.set_priority(TitleList(titles), priority)
    source.reply(tr('mcd_task.priority_set', titles, priority).set_color(RColor.green).set_styles(RStyle.bold))
    GlobalVariables.log(f"{_source_name(source)} set task {titles} priority to {priority}")


def reload_self(source: CommandSource):
    server = GlobalVariables.server
    server.reload_plugin(server.get_self_metadata().id)
    source.reply(tr('mcd_task.reloaded'))


def show_help(source: CommandSource):
    meta = GlobalVariables.server.get_self_metadata()
    source.reply(tr('mcd_task.help_msg', PREFIX, meta.name, meta.version).set_translator(GlobalVariables.htr))


def add_task(source: CommandSource, titles: str, desc: str = ''):
    titles = TitleList(titles)
    titles_for_text = titles.copy()
    GlobalVariables.debug(vars(GlobalVariables.task_manager))

    GlobalVariables.task_manager.add_task(titles, desc=desc)
    info_task(source, title=titles_for_text.head, prefix=tr(
        "mcd_task.new_task_created").set_color(RColor.green).set_styles(RStyle.bold))
    GlobalVariables.log(f"{_source_name(source)} created new task named {str(titles_for_text)}")


def all_tasks_detail(source: CommandSource):
    task_details = RTextList()
    for task in GlobalVariables.task_manager.sub_tasks:
        task_details.append(_task_info_flexible(task.full_path(), sub=False, idt=4))
    prefix = tr("mcd_task.detailed_info_task_title").set_color(RColor.green).set_styles(RStyle.bold)
    add_button = _add_task_button()
    source.reply(prefix + add_button + task_details)


def remove_task(source: CommandSource, titles: str):
    GlobalVariables.task_manager.delete_task(TitleList(titles))
    source.reply(tr("mcd_task.deleted_task", "§e{}§r".format(titles)))
    GlobalVariables.log(f"{_source_name(source)} deleted task {titles}")


def rename_task(source: CommandSource, old_titles: str, new_title: str) -> None:
    if '.' in list(new_title):
        source.reply(tr("mcd_task.illegal_title_with_dot", new_title))
        return
    GlobalVariables.task_manager.rename_task(TitleList(old_titles), new_title)
    new_titles = TitleList(old_titles)
    new_titles.pop_tail()
    new_titles.append(new_title)
    info_task(source, title=str(new_titles), prefix=tr("mcd_task.task_renamed", old_titles, str(new_titles)))
    GlobalVariables.log(f"{_source_name(source)} renamed {old_titles} to {str(new_titles)}")


def edit_desc(source: CommandSource, titles: str, desc: str) -> None:
    GlobalVariables.task_manager.edit_desc(TitleList(titles), desc)
    info_task(source, title=titles)
    GlobalVariables.log(f"{_source_name(source)} changed task {titles} description to {desc}")


def set_done(source: CommandSource, titles: str) -> None:
    GlobalVariables.task_manager.done_task(TitleList(titles))
    info_task(source, title=titles)
    GlobalVariables.log(f"{_source_name(source)} marked task {titles} as done")


def set_undone(source: CommandSource, titles: str) -> None:
    GlobalVariables.task_manager.undone_task(TitleList(titles))
    info_task(source, title=titles)
    GlobalVariables.log(f"{_source_name(source)} marked task {titles} as undone")


def list_done(source: CommandSource):
    info_task(source, prefix=tr("mcd_task.done_task_list_title"), done=True)


def set_responsible(source: CommandSource, titles: str, players: Optional[str] = None) -> None:
    if players is None:
        if isinstance(source, PlayerCommandSource):
            players = source.player
        else:
            illegal_call(source)
            return
    players = players.split(' ')
    num = GlobalVariables.task_manager.set_responsible(TitleList(titles), *players)
    list_responsible(source, titles, prefix=tr("mcd_task.added_responsibles_title", num))
    GlobalVariables.log(f"{_source_name(source)} added responsibles for task {str(titles)}: {str(players)}")


def rm_responsible(source: CommandSource, titles: str, players: Optional[str] = None) -> None:
    if players is None:
        if isinstance(source, PlayerCommandSource):
            players = source.player
        else:
            illegal_call(source)
            return
    players = players.split('.')
    removed = GlobalVariables.task_manager.rm_responsible(TitleList(titles), *players)
    num = len(removed)
    list_responsible(source, titles, player_removed=removed,
                     prefix=tr("mcd_task.removed_responsibles_title", num))
    GlobalVariables.log(f"{_source_name(source)} removed responsibles for task {str}: {str(players)}")


def list_responsible(source: CommandSource, titles: str,
                     player_removed=None, prefix: Optional[RTextMCDRTranslation] = None) -> None:
    if player_removed is None:
        player_removed = []
    player_list = GlobalVariables.task_manager.get_responsible_manager().get_responsibles(titles)
    num = len(player_list)
    task_done = GlobalVariables.task_manager[titles].done
    text = RTextList(
        (tr("mcd_task.list_responsible_title", num) if prefix is None else prefix).set_styles(
            RStyle.bold).set_color(RColor.green),
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
    resm = GlobalVariables.task_manager.get_responsible_manager()
    if old_name in resm.player_work.keys():
        resm.rename_player(old_name, new_name)
        num = len(resm[new_name])
        info.get_server().tell(new_name, tr("mcd_task.on_player_renamed", num))
        GlobalVariables.logger.debug(tr("mcd_task.on_player_renamed", num), no_check=debug)
        GlobalVariables.log(f"Detected player rename {old_name} -> {new_name}. Inherited {num} task(s)")


def task_timed_out(server: PluginServerInterface, player: str, player_tasks: List[TaskBase]):
    text = tr("mcd_task.on_player_joined", len(player_tasks)).set_color(RColor.red).set_styles(RStyle.bold)
    for t in player_tasks:
        text.append('\n', _task_info_simple(t.full_path(), full=True, sub=True, done=t.done, idt=4))
    server.tell(player, text)
