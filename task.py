# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import json
import os
import codecs
import sys
import copy

sys.path.append('plugins/')
import stext as st

if sys.version_info.major == 3:
    unicode = str

FILE_PATH = "./plugins/task/mc_task.json"
help_msg = '''------MCD TASK插件------
§a命令帮助如下:§r
§6!!task help§r 显示帮助信息
§6!!task list§r 显示任务列表
§6!!task detail [任务名称]§r 查看任务详细信息
§6!!task detail-all§r 查看所有任务详细信息
§6!!task add [任务名称] [任务描述(可选)]§r 添加任务
§6!!task del [任务名称]§r 删除任务
§6!!task rename [旧任务名称] [新任务名称]§r 重命名任务
§6!!task change [任务名称] [新任务描述]§r 修改任务描述
§6!!task done [任务名称]§r 标注任务为已完成
§6!!task undone [任务名称]§r 标注任务为未完成
§c注: 可用鼠标点击任务查看详情，或点击加号快速添加新任务§r
注: 上述所有 §6[任务名称]§r 可以用 §6[任务名称].[子任务名称]§r 的形式来访问子任务
例: (若已经有 §e女巫塔§r 任务, 可使用以下命令添加子任务)
    §6!!task add 女巫塔.铺地板 挂机铺黑色玻璃§r
--------------------------------'''

debug_mode = False


class TaskRoot(object):
    root = None  # type: Task


def onServerInfo(server, info):
    if not info.isPlayer:
        return

    command, option, args = parsed_info(info.content)
    if command != '!!task':
        return

    tasks = tasks_from_json_file()
    TaskRoot.root = tasks

    e = Executor(tasks, server, info.player, option, args)
    e.execute()

    save_tasks(tasks)


def on_info(server, info):
    info2 = copy.deepcopy(info)
    info2.isPlayer = info2.is_player
    onServerInfo(server, info2)


def on_load(server, old):
    server.add_help_message('!!task', '工程任务进度管理')


def parsed_info(content):
    try:
        c = content.decode('utf-8')
    except:
        c = content
    tokens = c.split()
    length = len(tokens)

    command = tokens[0]
    option = tokens[1] if length >= 2 else None
    args = tokens[2:] if length >= 3 else []
    return command, option, args


class Executor(object):
    def __init__(self, tasks, server, player, option, args):
        self.tasks = tasks  # type: Task
        self.server = server
        self.player = player
        self.option = option
        self.args = args

    def show(self, msg):
        st.show_to_player(self.server, self.player, msg)

    def execute(self):
        try:
            self.execute_option()
        except TaskNotFoundError as e:
            self.task_not_found(e.title)

    def execute_option(self):
        ops = {
            None: self.op_list,
            'help': self.op_help,
            'add': self.op_add,
            'detail': self.op_detail,
            'list': self.op_list,
            'detail-all': self.op_detail_all,
            'del': self.op_delete,
            'rename': self.op_rename,
            'change': self.op_change_description,
            'done': self.op_done,
            'undone': self.op_undone,
            'list-done': self.op_list_done,
        }
        if self.option in ops:
            ops[self.option](*self.args)
        else:
            self.op_invalid()

    def task_not_found(self, title):
        msg = TaskView.task_not_found(title)
        self.show(msg)

    def op_invalid(self):
        msg = st.SText("无效命令, 请用 !!task help 获取帮助")
        self.show(msg)

    def op_help(self):
        msg = st.SText(help_msg)
        self.show(msg)

    def op_add(self, titles='', *description):
        # type: (unicode, unicode) -> None
        ts = TitleList(titles)
        # title为空退出方法
        if titles == "":
            return
        
        if len(description) == 0:
            description = ['']
        description_merged = ""
        for desc in description:
            description_merged += desc + " "
        #剔除最后一个多余的空格
        description_merged = description_merged[0:len(description_merged) - 1]
        self.tasks.add_task(ts.copy(), description_merged)

        msg = TaskView.task_added(ts.copy())
        self.show(msg)

    def op_detail(self, titles):
        # type: (unicode) -> None
        ts = TitleList(titles)
        msg = TaskView.task_detail(ts)
        self.show(msg)

    def op_list(self, dummy=None):
        # dummy 是为了方便统一调用的假参数
        msg = TaskView.task_list()
        self.show(msg)

    def op_detail_all(self, dummy=None):
        # dummy 是为了方便统一调用的假参数
        msg = TaskView.task_detail_all()
        self.show(msg)

    def op_delete(self, titles):
        # type: (unicode) -> None
        ts = TitleList(titles)
        self.tasks.delete_task(ts.copy())

        msg = TaskView.task_deleted(ts.copy())
        self.show(msg)

    def op_rename(self, titles, new_title):
        # type: (unicode, unicode) -> None
        ts = TitleList(titles)
        self.tasks.rename_task(ts.copy(), new_title)

        msg = TaskView.task_renamed(ts.copy(), new_title)
        self.show(msg)

    def op_done(self, titles):
        # type: (unicode) -> None
        ts = TitleList(titles)
        self.tasks.done_task(ts.copy())

        msg = TaskView.task_done(ts.copy())
        self.show(msg)

    def op_undone(self, titles):
        # type: (unicode) -> None
        ts = TitleList(titles)
        self.tasks.undone_task(ts.copy())

        msg = TaskView.task_undone(ts.copy())
        self.show(msg)

    def op_change_description(self, titles="", *description):
        # type: (unicode, unicode) -> None
        ts = TitleList(titles)
        # title为空退出方法
        if titles == "":
            return
        
        if len(description) == 0:
            description = ['']
        description_merged = ""
        for desc in description:
            description_merged += desc + " "
        #剔除最后一个多余的空格
        description_merged = description_merged[0:len(description_merged) - 1]
        self.tasks.change_task_description(ts.copy(), description_merged)

        msg = TaskView.task_description_changed(ts.copy())
        self.show(msg)

    def op_list_done(self, dummy=None):
        msg = TaskView.task_list_done()
        self.show(msg)


class TaskView(object):
    @staticmethod
    def task_not_found(title):
        # type: (unicode) -> st.STextList
        m1 = st.SText(text="未找到任务 ")
        m2 = st.SText(text="{t}".format(t=title), color=st.SColor.yellow)
        msg = st.STextList(m1, m2)
        return msg

    @staticmethod
    def task_added(titles):
        # type: (TitleList) -> st.STextList
        title_text = "添加成功，任务详细信息"
        root_title_list = titles.copy()
        root_title_list.pop_tail()
        main_title = TaskView._task_detail_main_title(root_title_list.copy(), title_text)

        if root_title_list.is_empty():
            detail = TaskView._task_detail(titles.copy(), indent=2)
        else:
            detail = TaskView._task_detail(root_title_list.copy(), indent=2)

        msg = st.STextList()
        msg.extend(main_title)
        msg.extend(detail)
        return msg

    @staticmethod
    def task_detail(titles):
        # type: (TitleList) -> st.STextList
        title_text = "任务详细信息"
        main_title = TaskView._task_detail_main_title(titles, title_text)
        detail = TaskView._task_detail(titles, indent=4)

        msg = st.STextList()
        msg.extend(main_title)
        msg.extend(detail)
        return msg

    @staticmethod
    def task_list():
        # type: () -> st.STextList
        title_text = "搬砖信息列表"
        titles = TitleList()
        main_title = TaskView._task_detail_main_title(titles, title_text)
        detail = TaskView._task_list_undone()
        more_button = TaskView._task_list_show_undone()

        msg = st.STextList()
        msg.extend(main_title)
        msg.extend(detail)
        msg.extend(more_button)
        return msg

    @staticmethod
    def task_list_done():
        # type: () -> st.STextList
        title_text = "已完成任务列表"
        titles = TitleList()
        main_title = TaskView._task_detail_main_title(titles, title_text)
        detail = TaskView._task_list_done()

        msg = st.STextList()
        msg.extend(main_title)
        msg.extend(detail)
        return msg

    @staticmethod
    def task_detail_all():
        # type: () -> st.STextList
        title_text = "搬砖信息详细信息"
        titles = TitleList()
        main_title = TaskView._task_detail_main_title(titles, title_text)

        subs = TaskView._task_detail_sub_tasks(titles, indent=0)

        msg = st.STextList()
        msg.extend(main_title)
        msg.extend(subs)
        return msg

    @staticmethod
    def task_deleted(titles):
        space = st.SText.space()
        m1 = st.SText("任务")
        task = st.SText(unicode(titles), color=st.SColor.yellow)
        m2 = st.SText("已删除")
        msg = st.STextList(m1, space, task, space, m2)
        return msg

    @staticmethod
    def task_renamed(titles, new_title):
        new_titles = titles.copy()
        new_titles.pop_tail()
        new_titles.append(new_title)

        msg = TaskView.task_detail(new_titles.copy())
        return msg

    @staticmethod
    def task_done(titles):
        # type: (TitleList) -> st.STextList
        if len(titles.titles) > 1:
            top_title = titles.peek_head()
            return TaskView.task_detail(TitleList(top_title))
        else:
            return TaskView.task_list()

    @staticmethod
    def task_undone(titles):
        # type: (TitleList) -> st.STextList
        if len(titles.titles) > 1:
            top_title = titles.peek_head()
            return TaskView.task_detail(TitleList(top_title))
        else:
            return TaskView.task_list()

    @staticmethod
    def task_description_changed(titles):
        msg = TaskView.task_detail(titles.copy())
        return msg

    @staticmethod
    def _task_list():
        r = st.STextList()
        root = TaskRoot.root
        undones, dones = root.split_sub_tasks_by_done()
        # 逆序输出，最后创建的在最上面
        for t in reversed(undones):
            ts = TitleList(t.title)
            item = TaskView._task_detail_title(ts, indent=4)
            r.extend(item)
        for t in reversed(dones):
            ts = TitleList(t.title)
            item = TaskView._task_detail_title(ts, indent=4)
            r.extend(item)
        return r

    @staticmethod
    def _task_list_undone():
        r = st.STextList()
        root = TaskRoot.root
        undones, dones = root.split_sub_tasks_by_done()

        for t in reversed(undones):
            ts = TitleList(t.title)
            item = TaskView._task_detail_title(ts, indent=4)
            r.extend(item)
        return r

    @staticmethod
    def _task_list_done():
        r = st.STextList()
        root = TaskRoot.root
        undones, dones = root.split_sub_tasks_by_done()

        for t in reversed(dones):
            ts = TitleList(t.title)
            item = TaskView._task_detail_title(ts, indent=4)
            r.extend(item)
        return r

    @staticmethod
    def _task_list_show_undone():
        ind = st.SText.indent(4)
        newline = st.SText.newline()

        text = "[已完成任务...]"
        msg = st.SText(text, color=st.SColor.darkGray)

        hover_text = "点击以查看已完成任务"
        hover = st.SText(hover_text)
        msg.hover_text = hover

        command = "!!task list-done"
        msg.set_click_command(command)

        r = st.STextList()
        r.append(ind, msg, newline)
        return r

    @staticmethod
    def _task_detail_main_title(titles, title_text):
        # type: (TitleList, unicode) -> st.STextList
        main_title = st.SText(
            title_text,
            color=st.SColor.green,
            styles=[st.SStyle.bold]
        )
        add = TaskView._task_detail_button_add(titles.copy())

        msg = st.STextList(main_title, add)
        msg.append(st.SText.newline())
        return msg

    @staticmethod
    def _task_detail(titles, indent=0):
        detail_top = TaskView._task_detail_top_task(titles, indent=indent)
        detail_subs = TaskView._task_detail_sub_tasks(titles, indent=indent)

        r = st.STextList()
        r.extend(detail_top)
        r.extend(detail_subs)
        return r

    @staticmethod
    def _task_detail_sub(titles, indent=0):
        # type: (TitleList, int) -> st.STextList
        title = TaskView._task_detail_title(titles.copy(), indent=indent)
        subs = TaskView._task_detail_sub_tasks(titles.copy(), indent)

        r = st.STextList()
        r.extend(title)
        r.extend(subs)
        return r

    @staticmethod
    def _task_detail_top_task(titles, indent=4):
        # type: (TitleList, int) -> st.STextList
        ts = titles
        t = Task.task_by_title_list(ts)

        title = TaskView._task_detail_title(
            ts,
            indent=indent,
            button_show_desc=False,
            button_edit_title=True,
        )
        desc = TaskView._task_detail_description(ts, indent=indent+3)

        r = st.STextList()
        r.extend(title)
        r.extend(desc)
        return r

    @staticmethod
    def _task_detail_title(titles, indent=0, button_show_desc=True, button_edit_title=False):
        # type: (TitleList, int, bool, bool) -> st.STextList
        ind = st.SText.indent(indent)
        space = st.SText.space()
        newline = st.SText.newline()

        t = Task.task_by_title_list(titles)
        ts = titles

        icon = TaskView._task_detail_icon_done(ts.copy(), t.done)
        title = TaskView._task_detail_title_text(ts.copy(), t.done)

        show_desc = st.SText()
        if t.description != '' and button_show_desc:
            show_desc = TaskView._task_detail_button_show_description(ts.copy())

        edit_title = st.SText()
        if button_edit_title:
            edit_title = TaskView._task_detail_icon_edit_title(ts.copy())

        r = st.STextList(ind, icon, space, title, space, show_desc, edit_title, newline)
        return r

    @staticmethod
    def _task_detail_icon_done(titles, done):
        # type: (TitleList, bool) -> st.SText
        icon_done = st.SText("⬛", color=st.SColor.darkGray)
        icon_undone = st.SText("⬜", color=st.SColor.white)
        icon = icon_done if done else icon_undone

        done_text = "未完成" if done else "完成"
        hover_prefix = st.SText("将任务标记为")
        hover_done = st.SText(done_text, st.SColor.yellow)
        hover = st.STextList(hover_prefix, hover_done)
        icon.hover_text = hover

        option = 'undone' if done else 'done'
        command = "!!task {} {}".format(option, unicode(titles))
        icon.set_click_command(command)

        return icon

    @staticmethod
    def _task_detail_icon_edit_title(titles):
        # type: (TitleList) -> st.SText
        icon = st.SText("✎", color=st.SColor.white)

        hover = st.SText("修改任务标题")
        icon.hover_text = hover

        suggest = "!!task rename {} ".format(unicode(titles))
        icon.set_click_suggest(suggest)

        return icon

    @staticmethod
    def _task_detail_icon_edit_desc(titles):
        # type: (TitleList) -> st.SText
        icon = st.SText("✎", color=st.SColor.white)

        hover = st.SText("修改任务描述")
        icon.hover_text = hover

        suggest = "!!task change {} ".format(unicode(titles))
        icon.set_click_suggest(suggest)

        return icon

    @staticmethod
    def _task_detail_title_text(titles, done):
        # type: (TitleList, bool) -> st.SText
        title = titles.peek_tail()
        styles = [st.SStyle.strikethrough] if done else None
        color = st.SColor.darkGray if done else st.SColor.yellow
        r = st.SText(title, color=color, styles=styles)

        h1 = st.SText("点击以查看")
        h2 = st.SText("任务详情", st.SColor.yellow)
        hover = st.STextList(h1, h2)
        r.hover_text = hover

        command = "!!task detail {}".format(unicode(titles))
        r.set_click_command(command)
        return r

    @staticmethod
    def _task_detail_description(titles, indent=0):
        # type: (TitleList, int) -> st.STextList
        ind = st.SText.indent(indent)
        space = st.SText.space()
        newline = st.SText.newline()

        task = Task.task_by_title_list(titles.copy())

        r = st.STextList()
        if task.description != '':
            d = st.SText(task.description, color=st.SColor.gray)
            edit = TaskView._task_detail_icon_edit_desc(titles)
            r.append(ind, d, space, edit, newline)
        return r

    @staticmethod
    def _task_detail_sub_tasks(titles, indent=0):
        # type: (TitleList, int) -> st.STextList
        task = Task.task_by_title_list(titles)
        undones, dones = task.split_sub_tasks_by_done()
        r = st.STextList()

        indent += 4
        # 逆序输出，最后创建的在最上面
        for t in reversed(undones):
            ts = titles.copy()
            ts.append(t.title)
            sub = TaskView._task_detail_sub(ts, indent=indent)
            r.extend(sub)
        for t in reversed(dones):
            ts = titles.copy()
            ts.append(t.title)
            sub = TaskView._task_detail_sub(ts, indent=indent)
            r.extend(sub)
        return r

    @staticmethod
    def _task_detail_button_add(titles):
        # type: (TitleList) -> st.SText
        add = st.SText("[+]", color=st.SColor.red)

        h1 = st.SText("点击以快速")
        h2 = st.SText("添加子任务", color=st.SColor.yellow)
        add_hover = st.STextList(h1, h2)
        add.hover_text = add_hover

        ts = unicode(titles)
        if ts != '':
            suggest = "!!task add {}.".format(ts)
        else:
            suggest = "!!task add "
        add.set_click_suggest(suggest)

        return add

    @staticmethod
    def _task_detail_button_show_description(titles):
        # type: (TitleList) -> st.SText
        show = st.SText("[…]", color=st.SColor.white)

        h1 = st.SText("点击以查看")
        h2 = st.SText("任务描述", color=st.SColor.yellow)
        add_hover = st.STextList(h1, h2)
        show.hover_text = add_hover

        command = "!!task detail {}".format(unicode(titles))
        show.set_click_command(command)

        return show


class Task(object):
    def __init__(self, title, description):
        self.title = title
        self.done = False
        self.description = description
        self.sub_tasks = []

    def option_clear(self):
        if not debug_mode:
            return
        self.title = ''
        self.done = False
        self.description = ''
        self.sub_tasks = []

    def add_task(self, titles, description=''):
        # type: (TitleList, unicode) -> None
        new_task_title = titles.pop_tail()
        new_task = Task(new_task_title, description)

        parent_of_new = self.task_by_title_list(titles)
        parent_of_new.sub_tasks.append(new_task)

    def _sub_task_by_title(self, title):
        # type: (unicode) -> Task
        for t in self.sub_tasks:
            if t.title == title:
                return t
        raise TaskNotFoundError(title)

    @staticmethod
    def task_by_title_list(titles):
        # type: (TitleList) -> Task
        # 为了简化逻辑，用全局变量保存根
        root = TaskRoot.root
        task = root
        for title in titles.titles:
            task = task._sub_task_by_title(title)
        return task

    def delete_task(self, titles):
        # type: (TitleList) -> None
        title_to_delete = titles.pop_tail()
        parent_task = Task.task_by_title_list(titles)
        task = parent_task._sub_task_by_title(title_to_delete)
        parent_task.sub_tasks.remove(task)

    def rename_task(self, titles, new_title):
        # type: (TitleList, unicode) -> None
        task = Task.task_by_title_list(titles)
        task.title = new_title

    def change_task_description(self, titles, description):
        # type: (TitleList, unicode) -> None
        task = Task.task_by_title_list(titles)
        task.description = description

    def done_task(self, titles):
        t = Task.task_by_title_list(titles)
        t.done = True

    def undone_task(self, titles):
        t = Task.task_by_title_list(titles)
        t.done = False

    def split_sub_tasks_by_done(self):
        undones = []
        dones = []
        for t in self.sub_tasks:
            if t.done:
                dones.append(t)
            else:
                undones.append(t)
        return undones, dones

    def to_json_object(self):
        result = self.__dict__.copy()
        sub_tasks = result['sub_tasks'][:]
        result['sub_tasks'] = [s.to_json_object() for s in sub_tasks]
        return result

    @staticmethod
    def from_dict(data):
        t = Task.empty_task()
        t.__dict__ = data
        t.sub_tasks = [
            Task.from_dict(dt) for dt in data['sub_tasks']
        ]
        return t

    @staticmethod
    def empty_task():
        return Task('', '')


class TitleList(object):
    def __init__(self, titles=None):
        if titles is None:
            self.titles = []
        else:
            self.titles = titles.split('.')  # type: list

    def pop_head(self):
        # type: () -> unicode
        return self.titles.pop(0)

    def pop_tail(self):
        # type: () -> unicode
        return self.titles.pop()

    def peek_head(self):
        ts = self.titles
        if len(ts) > 0:
            return self.titles[0]
        else:
            return None

    def peek_tail(self):
        # type: () -> unicode
        return self.titles[-1]

    def copy(self):
        r = TitleList()
        r.titles = self.titles[:]
        return r

    def append(self, title):
        # type: (unicode) -> None
        self.titles.append(title)

    def is_empty(self):
        return len(self.titles) == 0

    def __unicode__(self):
        # type: () -> unicode
        r = '.'.join(self.titles)
        return r

    def __str__(self):
        # type: () -> unicode
        return self.__unicode__()


class TaskNotFoundError(Exception):
    def __init__(self, title):
        self.title = title


def init_json_file(filename, init_value):
    if not os.path.isdir(os.path.dirname(filename)):
        os.makedirs(os.path.dirname(filename))
    with codecs.open(filename, "w", encoding='utf-8') as f:
        s = json.dumps(init_value, indent=4)
        f.write(s)


def data_from_json_file(filename, init_value):
    if not os.path.exists(filename):
        init_json_file(filename, init_value)
    with codecs.open(filename, "r", encoding='utf-8') as f:
        data = json.load(f)
    return data


def save_data_as_json_file(data, filename):
    with codecs.open(filename, "w", encoding='utf-8') as f:
        json_data = json.dumps(data, indent=4)
        f.write(json_data)


def init_tasks_dict():
    tasks = Task.empty_task()
    return tasks.to_json_object()


def tasks_from_json_file():
    init_value = init_tasks_dict()
    task_dict = data_from_json_file(FILE_PATH, init_value)
    return Task.from_dict(task_dict)


def save_tasks(tasks):
    save_data_as_json_file(tasks.to_json_object(), FILE_PATH)