# -*- coding: utf-8 -*-


import json
import os
import traceback
import codecs


help_msg = u'''------MCD TASK插件------
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
注: 上述所有 §6[任务名称]§r 可以用 §6[任务名称].[子任务名称]§r 的形式来访问子任务
例: (若已经有 §e女巫塔§r 任务, 可使用以下命令添加子任务)
    §6!!task add 女巫塔.铺地板 挂机铺黑色玻璃§r
--------------------------------'''

debug_mode = False


def onServerInfo(server, info):
    if not info.isPlayer:
        return

    command, option, args = parsed_info(info.content)
    if command != '!!task':
        return

    tasks = tasks_from_json_file()

    e = Executor(tasks, server, info.player, option, args)
    e.execute()

    save_tasks(tasks)


def parsed_info(content):
    c = content.decode('utf-8')
    tokens = c.split()
    command = tokens[0]
    option = tokens[1:2]
    args = tokens[2:]
    return command, option, args


class Executor(object):
    def __init__(self, tasks, server, player, option, args):
        self.tasks = tasks
        self.server = server
        self.player = player
        self.option = option
        self.args = args

        self.options = [
            'add',
            'del',
            'rename',
            'change',
            'done',
            'undone',
            'detail',
            'list',
        ]

    def tell(self, message):
        for line in message.splitlines():
            if line.startswith(u'/tellraw'.encode('utf-8')):
                line = line.replace('{player}', self.player)
                line = line.encode('utf-8')
                self.server.execute(line)
            else:
                if isinstance(line, unicode):
                    line = line.encode('utf-8')
                self.server.tell(self.player, line)


    def execute(self):
        if self.no_option(self.option):
            self.tell(help_msg)
        else:
            self.option = self.option[0]
            try:
                self.execute_option()
            except TaskNotFoundError as e:
                msg = "未找到任务 §e{t}".format(t=e.title)
                self.tell(msg)
            except:
                # FIXME: empty except for stacktrace echo
                f = traceback.format_exc()
                self.tell(f)

    def no_option(self, option):
        return len(option) == 0

    def execute_option(self):
        if self.option == 'help':
            self.tell(help_msg)
        elif self.option in self.options:
            method_args = self.args_for_invoke(self.args)
            method_name = "option_" + self.option.replace('-', '_')
            method = getattr(self.tasks, method_name)
            msg = method(*method_args)
            if msg:
                self.tell(msg)
        else:
            msg = "无效命令, 请用 !!task help 获取帮助"
            self.tell(msg)

    def args_for_invoke(self, args):
        if args:
            title_arg = args[0]
            titles = title_arg.split('.')
            rest_args = args[1:]
            result = [titles] + rest_args
        else:
            result = []
        return result


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

    def option_add(self, titles, description=''):
        title = titles.pop()
        sub_task = Task(title, description)

        t = self.step_down(titles)
        t.sub_tasks.append(sub_task)
        return "添加成功"

    def option_del(self, titles):
        title = titles.pop()

        t = self.step_down(titles)
        st = t.search(title)
        t.sub_tasks.remove(st)
        return "删除成功"

    def option_rename(self, titles, new_name):
        t = self.step_down(titles)
        t.name = new_name
        return "已重命名任务"

    def option_done(self, titles):
        t = self.step_down(titles)
        t.done = True
        return "已标记任务为完成"

    def option_undone(self, titles):
        t = self.step_down(titles)
        t.done = False
        return "已标记任务为未完成"

    def option_change(self, titles, description=''):
        t = self.step_down(titles)
        t.description = description
        return "已修改任务描述"

    def step_down(self, titles):
        if len(titles) == 0:
            return self
        else:
            title = titles.pop(0)
            s = self.search(title)
            return s.step_down(titles)

    def search(self, title):
        for t in self.sub_tasks:
            if t.title == title:
                return t
        raise TaskNotFoundError(title)

    def to_dict(self):
        result = self.__dict__.copy()
        sub_tasks = result['sub_tasks'][:]
        result['sub_tasks'] = [
            s.to_dict() for s in sub_tasks
        ]
        return result

    # def option_list(self):
    #     s = u"§a搬砖信息列表:§r \n"
    #     for t in self.sub_tasks:
    #         s += u"  - §e{title}§r\n".format(title=t.title_with_mark())
    #     return s

    def option_list(self):
        list = [
            u'"§a搬砖信息列表:§r"',
            u'{"text":"[+]","color":"red","clickEvent":{"action":"suggest_command","value":"!!task add "},"hoverEvent":{"action":"show_text","value":{"text":"","extra":[{"text":"点击以快速添加任务"}]}}}',
        ]
        template = u'{"text":"{title}\\n","color":"yellow","clickEvent":{"action":"run_command","value":"!!task detail {title}"},"hoverEvent":{"action":"show_text","value":{"text":"","extra":[{"text":"点击以查看任务详情"}]}}}'
        for t in self.sub_tasks:
            newline = u'"\\n"'
            list.append(newline)

            dash = u'"- "'
            list.append(dash)

            title = t.title_with_mark()
            item = u'{"text":"' \
                + title \
                + u'","color":"yellow","clickEvent":{"action":"run_command","value":"!!task detail ' \
                + t.title \
                + u'"},"hoverEvent":{"action":"show_text","value":{"text":"","extra":[{"text":"点击以查看任务详情"}]}}}'
            list.append(item)

        s = self.tellraw_from_list(list)
        return s

    def tellraw_from_list(self, list):
        s = u"/tellraw {player} [" + ','.join(list) + u"]"
        s.replace(u"'", '')
        return s

    # def option_detail(self, titles):
    #     t = self.step_down(titles)
    #     return t.detail_inner(ind='')

    def option_detail(self, titles):
        t = self.step_down(titles[:])

        details = t.detail_inner(titles, ind='')
        return self.tellraw_from_list(details)

    def detail_inner(self, titles=[], ind=''):
        if ind:
            list = ['"\\n"']
        else:
            list = []

        title = u'"{ind}- §e{t}§r"'.format(ind=ind, t=self.title_with_mark())
        list.append(title)

        if titles:
            # ts = [t.decode('utf-8') for t in titles]
            add = u'{"text":"[+]","color":"red","clickEvent":{"action":"suggest_command","value":"!!task add {titles}"},"hoverEvent":{"action":"show_text","value":{"text":"","extra":[{"text":"点击以快速添加子任务"}]}}}'
            add = add.replace('{titles}', '.'.join(titles) + '.')
            list.append(add)

        ind = ind + '  '
        if self.description:
            list.append(u'"\\n"')
            list.append(u'"{ind}§7{d}§7"'.format(ind=ind, d=self.description))

        ind = ind + '  '
        for t in self.sub_tasks:
            list.extend(t.detail_inner(ind=ind))

        return list

    # def option_detail_all(self):
    #     s = ''
    #     for t in self.sub_tasks:
    #         s += t.detail_inner(ind='')
    #     return s

    # def detail_inner(self, ind=''):
    #     s = u'{ind}- §e{t}§r\n'.format(ind=ind, t=self.title_with_mark())
    #     ind = ind + '  '
    #     if self.description:
    #         s += u'{ind}§7{d}§7\n'.format(ind=ind, d=self.description)
    #
    #     ind = ind + '  '
    #     for t in self.sub_tasks:
    #         s += t.detail_inner(ind)
    #
    #     return s

    def title_with_mark(self):
        if self.done:
            return u"§m{t}§r".format(t=self.title)
        else:
            return self.title

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


class TaskNotFoundError(Exception):
    def __init__(self, title):
        self.title = title


def init_json_file(filename, init_value):
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
    return tasks.to_dict()


def tasks_from_json_file():
    init_value = init_tasks_dict()
    task_dict = data_from_json_file("mc_task.json", init_value)
    return Task.from_dict(task_dict)


def save_tasks(tasks):
    save_data_as_json_file(tasks.to_dict(), "mc_task.json")
