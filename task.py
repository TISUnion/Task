# -*- coding: utf-8 -*-


import json
import os
import traceback


help_msg = '''------MCD TASK插件------
命令帮助如下:
!!task help 显示帮助信息
!!task list 显示任务列表
!!task detail [任务名称] 查看任务详细信息
!!task add [任务名称] [任务描述] 添加任务
!!task del [任务名称] 删除任务
!!task rename [旧任务名称] [新任务名称] 重命名任务
!!task change [任务名称] [新任务描述] 修改任务描述
!!task done [任务名称] 标注任务为已完成
!!task undone [任务名称] 标注任务为未完成
注: 上述所有 [任务名称] 可以用 [任务名称].[子任务名称] 的形式来访问子任务
例: !!task add 女巫塔.铺地板 挂机铺黑色玻璃
--------------------------------'''


def onServerInfo(server, info):
    if not info.isPlayer:
        return

    command, option, args = parsed_info(info.content)
    if command != '!!task':
        return

    task(server, info.player, option, args)


def task(server, player, option, args):
    def tell_task_not_found(title):
        server.tell("未找到任务 §e\"{t}\" ".format(t=title))

    if len(option) == 0:
        tell_player(server, player, help_msg)
    else:
        option = option[0]

    tasks = tasks_from_json_file()
    task_options = {
        'add': lambda ts, d: tasks.add(ts, d),
        'del': lambda ts: tasks.remove(ts),
        'rename': lambda ts, new: tasks.rename(ts, new),
        'change': lambda ts, new: tasks.change_description(ts, new),
        'done': lambda ts: tasks.mark_done(ts),
        'undone': lambda ts: tasks.mark_undone(ts),
    }
    try:
        if option == 'help':
            tell_player(server, player, help_msg)
        elif option == 'list':
            msg = "任务列表如下：\n" + tasks.list()
            tell_player(server, player, msg)
        elif option in task_options.keys():
            titles = titles_from_arg(args[0])
            rest_args = args[1:]

            args_to_invoke = [titles] + rest_args
            task_options[option](*args_to_invoke)
        else:
            msg = "无效命令, 请用 !!task help 获取帮助"
            tell_player(server, player, msg)
    except TaskNotFoundError as e:
        tell_task_not_found(e.title)
    except:
        f = traceback.format_exc()
        tell_player(server, player, f)


def tell_player(server, player, message):
    for line in message.splitlines():
        server.tell(player, line)


def titles_from_arg(arg):
    return arg.split('.')


def parsed_info(content):
    tokens = content.split()
    command = tokens[0]
    option = tokens[1:2]
    args = tokens[2:]
    return command, option, args


class Task(object):
    def __init__(self, title, description):
        self.title = title
        self.done = False
        self.description = description
        self.sub_tasks = []

    def add(self, titles, description):
        title = titles.pop()
        sub_task = Task(title, description)

        t = self.step_down(titles)
        t.sub_tasks.append(sub_task)

    def remove(self, titles):
        title = titles.pop()

        t = self.step_down(titles)
        st = t.search(title)
        t.sub_tasks.remove(st)

    def rename(self, titles, new_name):
        t = self.step_down(titles)
        t.name = new_name

    def mark_done(self, titles):
        t = self.step_down(titles)
        t.done = True

    def mark_undone(self, titles):
        t = self.step_down(titles)
        t.done = False

    def change_description(self, titles, description):
        t = self.step_down(titles)
        t.description = description

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

    def list(self):
        s = ""
        for t in self.sub_tasks:
            s += "- {title}\n".format(title=t.title)
        return s

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


def log(*args):
    print(*args)


def init_json_file(filename, init_value):
    with open(filename, "w") as f:
        s = json.dumps(init_value)
        f.write(s)


def data_from_json_file(filename, init_value):
    if not os.path.exists(filename):
        init_json_file(filename, init_value)
    with open(filename, "r") as f:
        data = json.load(f)
    return data


def save_data_as_json_file(data, filename):
    with open(filename, "w") as f:
        json_data = json.dumps(data, indent=4)
        f.write(json_data)


def init_tasks_dict():
    tasks = Task.empty_task()
    return tasks.to_dict()


def tasks_from_json_file():
    init_value = init_tasks_dict()
    return data_from_json_file("mc_task.json", init_value)


def save_tasks(tasks):
    save_data_as_json_file(tasks, "mc_task.json")


if __name__ == "__main__":
    tasks = Task('', '')
    tasks.add(['test1'], 'for test')
    tasks.add(['test1', 'test11'], 'for test11')

    d = tasks.to_dict()
    save_tasks(d)

    tasks.remove(['test1', 'test11'])
