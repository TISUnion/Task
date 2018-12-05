# -*- coding: utf-8 -*-


import json
import os
import traceback
import codecs


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
    def tell(message):
        for line in message.splitlines():
            server.tell(player, line)

    # FIXME: implement a function to handle option array
    if len(option) == 0:
        tell(help_msg)
        return
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
            tell(help_msg)
        elif option == 'list':
            msg = u"搬砖信息列表: \n" + tasks.list()
            msg = msg.encode('utf-8')
            tell(msg)
        elif option == 'clear':
            save_tasks(tasks)
            with open("mc_task.json", 'w') as f:
                init_value = init_tasks_dict()
                f.write(json.dumps(init_value))
            tell("tasks 已清空")
        elif option in task_options.keys():
            titles = titles_from_arg(args[0])
            rest_args = args[1:]

            args_to_invoke = [titles] + rest_args
            msg = task_options[option](*args_to_invoke)
            if msg:
                tell(msg)
        else:
            msg = "无效命令, 请用 !!task help 获取帮助"
            tell(msg)
    except TaskNotFoundError as e:
        msg = "未找到任务 §e{t}".format(t=e.title)
        tell(msg)
    except:
        f = traceback.format_exc()
        tell(f)

    save_tasks(tasks)


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
        return "添加成功"

    def remove(self, titles):
        title = titles.pop()

        t = self.step_down(titles)
        st = t.search(title)
        t.sub_tasks.remove(st)
        return "删除成功"

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


def init_json_file(filename, init_value):
    with open(filename, "w") as f:
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


if __name__ == '__main__':
    tasks = tasks_from_json_file()
    tasks.add(['test'], 'for test')
    save_tasks(tasks)
    tasks.remove(['test'])
    tasks.remove(['test'])
