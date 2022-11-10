import time
from typing import Optional, Union, List

from mcdreforged.api.all import *

from mcd_task.global_variables import GlobalVariables
from mcd_task.constants import PREFIX, DEBUG_MODE
from mcd_task.exceptions import TaskNotFound
from mcd_task.task_manager import Task
from mcd_task.utils import formatted_time, source_name, TitleList
from mcd_task.rtext_components import tr, info_elements, title_text, info_responsibles, add_task_button, \
    EditButtonType, info_sub_tasks, sub_task_title_text


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
        permed_literal('list-all').runs(lambda src: all_tasks_detail(src)),
        permed_literal('add').then(
            ensure_task_not_exist_quotable_text().runs(lambda src, ctx: add_task(src, ctx['title'])).then(
                GreedyText('description').runs(lambda src, ctx: add_task(src, ctx['title'], ctx['description']))
            )
        ),
        permed_literal('remove', 'rm', 'delete', 'del').then(
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
                Literal('clear').runs(lambda src, ctx: clear_task_deadline(src, ctx['title']))
            ).then(
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
                Literal('-all').runs(lambda src, ctx: rm_all_responsible(src, ctx['title']))
            ).then(
                GreedyText("players").runs(lambda src, ctx: rm_responsible(src, ctx['title'], ctx['players']))
            )
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
    ))


def task_already_exist(source: CommandSource):
    source.reply(tr("task_already_exist").set_color(RColor.red).c(RAction.run_command, f'{PREFIX} list').h(
        tr("task_not_found_hover", PREFIX)
    ))


def illegal_call(source: CommandSource):
    source.reply(tr('illegal_call').set_color(RColor.red))


# Info
def info_player(source: CommandSource, name: str) -> None:
    tasks = list(GlobalVariables.task_manager.responsible_manager[name])
    text = [
        tr("player_tasks_title", name, str(len(tasks))).set_color(RColor.green).set_styles(RStyle.bold),
    ]
    for task in tasks:
        text.append(title_text(task, display_full_path=True, display_not_empty_mark=True))
    source.reply(RText.join('\n', text))


def info_task(source: CommandSource, title: str, headline_override: Union[None, str, RTextBase] = None) -> None:
    # Get task instance
    try:
        target_task = GlobalVariables.task_manager[title]
    except TaskNotFound:
        task_not_found(source)
        if DEBUG_MODE:
            raise
        return

    # Task detail text
    headline = tr("info_task_title")
    if isinstance(headline_override, str):
        headline = tr(headline_override)
    if isinstance(headline_override, RTextBase):
        headline = headline_override
    headline.set_color(RColor.green).set_styles(RStyle.bold)
    task_title_text = title_text(target_task, display_full_path=True, with_edit_button=True)
    info_desc = info_elements(target_task)
    info_ddl = info_elements(target_task, EditButtonType.deadline)
    info_priority = info_elements(target_task, EditButtonType.priority)
    info_res = info_responsibles(target_task)
    info_sub = info_sub_tasks(target_task)

    # Show task text
    source.reply(RText.join('\n', [headline, task_title_text, info_desc, info_ddl, info_priority, info_res, info_sub]))


# Others
def list_task(source: CommandSource):
    headline = tr('list_task_title').set_styles(RStyle.bold).set_color(
        RColor.green) + ' ' + add_task_button()
    task_list_text = []
    for task in GlobalVariables.task_manager.sorted_sub_tasks:
        task_list_text.append(title_text(task, display_not_empty_mark=True))
    task_list_text = RTextBase.join('\n', task_list_text)
    text = [headline, task_list_text]
    source.reply(RText.join('\n', text))


def set_task_deadline(source: CommandSource, titles: str, ddl: str) -> None:
    deadline = float(time.time()) + float(ddl) * 3600 * 24
    GlobalVariables.task_manager.set_deadline(TitleList(titles), deadline)
    info_task(source, titles, headline_override=tr("ddl_set"))
    GlobalVariables.log(
        f"{source_name(source)} set task {titles} deadline to {formatted_time(deadline, locale='en_us')}"
    )


def clear_task_deadline(source: CommandSource, titles: str):
    GlobalVariables.task_manager.set_deadline(TitleList(titles), 0)
    info_task(source, titles, headline_override=tr('ddl_cleared'))
    GlobalVariables.log(
        f"{source_name(source)} removed task {titles} deadline"
    )


def task_overview(source: CommandSource):
    GlobalVariables.debug('Running overview...')
    headline = tr('overview_headline').set_styles(RStyle.bold).set_color(RColor.green) + ' ' + add_task_button()

    # Get task instances
    deadline_approaching = GlobalVariables.task_manager.seek_for_item_with_deadline_approaching()
    GlobalVariables.debug(deadline_approaching)
    max_length = GlobalVariables.config.overview_maximum_task_amount
    priority_amount = max_length - len(deadline_approaching)
    with_priorities = []
    if priority_amount > 0:
        with_priorities = GlobalVariables.task_manager.seek_for_item_with_priority()

    # Found no matched task handle
    if len(deadline_approaching) == 0 and len(with_priorities) == 0:
        task_text = tr('no_priority').set_color(RColor.yellow)
    # Organize task texts
    else:
        task_texts = {}
        for task in deadline_approaching:
            if len(task_texts) >= GlobalVariables.config.overview_maximum_task_amount:
                break
            task_texts[task.titles] = RText('[!] ', RColor.red).h(
                tr('date_approaching', formatted_time(task.deadline))
            ) + title_text(task, display_full_path=True)
        for task in with_priorities:
            if len(task_texts) >= GlobalVariables.config.overview_maximum_task_amount:
                break
            if task.title not in task_texts.keys():
                task_texts[task.titles] = RText('[!] ', RColor.gold).h(
                    tr('has_a_high_priority', task.priority)
                ) + title_text(task, display_full_path=True)
        task_text = RTextBase.join('\n', task_texts.values())

    help_message = tr('overview_help', PREFIX).set_translator(GlobalVariables.htr)

    source.reply(RTextBase.join('\n', [headline, task_text, help_message]))


def set_task_priority(source: CommandSource, titles: str, priority: Optional[int] = None):
    GlobalVariables.task_manager.set_priority(TitleList(titles), priority)
    info_task(source, titles, headline_override=tr('priority_set'))
    GlobalVariables.log(f"{source_name(source)} set task {titles} priority to {priority}")


def reload_self(source: CommandSource):
    server = GlobalVariables.server
    server.reload_plugin(server.get_self_metadata().id)
    source.reply(tr('reloaded'))


def show_help(source: CommandSource):
    meta = GlobalVariables.server.get_self_metadata()
    ver = '.'.join(map(lambda x: str(x), meta.version.component))
    if meta.version.pre is not None:
        ver += '-' + str(meta.version.pre)
    source.reply(tr('help_msg', pre=PREFIX, name=meta.name, ver=ver).set_translator(GlobalVariables.htr))


def add_task(source: CommandSource, titles: str, desc: str = ''):
    titles = TitleList(titles)
    titles_for_text = titles.copy()

    GlobalVariables.task_manager.add_task(titles, desc=desc)
    info_task(source, title=str(titles_for_text), headline_override=tr("new_task_created"))
    GlobalVariables.log(f"{source_name(source)} created new task named {str(titles_for_text)}")


def all_tasks_detail(source: CommandSource):
    task_details = [tr("detailed_info_task_title").set_color(RColor.green).set_styles(RStyle.bold) + ' ' +
                    add_task_button()]
    for task in GlobalVariables.task_manager.sorted_sub_tasks:
        task_details.append(title_text(task, include_sub=False, display_not_empty_mark=True))
        if len(task.sub_tasks) > 0:
            task_details.append(sub_task_title_text(task, indent=8))
    source.reply(RTextBase.join('\n', task_details))


def remove_task(source: CommandSource, titles: str):
    GlobalVariables.task_manager.delete_task(TitleList(titles))
    source.reply(tr("mcd_task.deleted_task", "§e{}§r".format(titles)))
    GlobalVariables.log(f"{source_name(source)} deleted task {titles}")


def rename_task(source: CommandSource, old_titles: str, new_title: str) -> None:
    if '.' in list(new_title):
        source.reply(tr("mcd_task.illegal_title_with_dot", new_title))
        return
    GlobalVariables.task_manager.rename_task(TitleList(old_titles), new_title)
    new_titles = TitleList(old_titles)
    new_titles.pop_tail()
    new_titles.append(new_title)
    info_task(source, title=str(new_titles), headline_override=tr("mcd_task.task_renamed", old_titles))
    GlobalVariables.log(f"{source_name(source)} renamed {old_titles} to {str(new_titles)}")


def edit_desc(source: CommandSource, titles: str, desc: str) -> None:
    GlobalVariables.task_manager.edit_desc(TitleList(titles), desc)
    info_task(source, title=titles, headline_override='changed_desc_title')
    GlobalVariables.log(f"{source_name(source)} changed task {titles} description to {desc}")


def set_done(source: CommandSource, titles: str) -> None:
    GlobalVariables.task_manager.done_task(TitleList(titles))
    info_task(source, title=titles, headline_override='done_task_title')
    GlobalVariables.log(f"{source_name(source)} marked task {titles} as done")


def set_undone(source: CommandSource, titles: str) -> None:
    GlobalVariables.task_manager.undone_task(TitleList(titles))
    info_task(source, title=titles, headline_override='undone_task_title')
    GlobalVariables.log(f"{source_name(source)} marked task {titles} as undone")


def set_responsible(source: CommandSource, titles: str, players: Optional[str] = None) -> None:
    if players is None:
        if isinstance(source, PlayerCommandSource):
            players = source.player
        else:
            illegal_call(source)
            return
    players = players.split(' ')
    num = GlobalVariables.task_manager.set_responsible(TitleList(titles), *players)
    info_task(source, titles, headline_override=tr("mcd_task.added_responsibles_title", num))
    GlobalVariables.log(f"{source_name(source)} added responsibles for task {str(titles)}: {str(players)}")


def rm_responsible(source: CommandSource, titles: str, players: Optional[str] = None) -> None:
    if players is None:
        if isinstance(source, PlayerCommandSource):
            players = source.player
        else:
            illegal_call(source)
            return
    players = players.split(' ')
    removed = GlobalVariables.task_manager.rm_responsible(TitleList(titles), *players)
    num = len(removed)
    info_task(source, titles, headline_override=tr("mcd_task.removed_responsibles_title", num))
    GlobalVariables.log(f"{source_name(source)} removed responsibles for task {str(titles)}: {str(players)}")


def rm_all_responsible(source: CommandSource, titles: str):
    players = GlobalVariables.task_manager.responsible_manager.get_responsibles(titles)
    rm_responsible(source, titles, players=' '.join(players))


def inherit_responsible(info: Info, old_name: str, new_name: str, debug=False):
    manager = GlobalVariables.task_manager.responsible_manager
    if old_name in manager.player_work.keys():
        manager.rename_player(old_name, new_name)
        num = len(manager[new_name])
        info.get_server().tell(new_name, tr("mcd_task.on_player_renamed", num))
        GlobalVariables.logger.debug(tr("mcd_task.on_player_renamed", num), no_check=debug)
        GlobalVariables.log(f"Detected player rename {old_name} -> {new_name}. Inherited {num} task(s)")


def task_timed_out(server: PluginServerInterface, player: str, player_tasks: List[Task]):
    text = [tr("on_player_joined", len(player_tasks)).set_color(RColor.red).set_styles(RStyle.bold)]
    for t in player_tasks:
        text.append(title_text(t, display_full_path=True, display_not_empty_mark=True))
    server.tell(player, RTextBase.join('\n', text))
