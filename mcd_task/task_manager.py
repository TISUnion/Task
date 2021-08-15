import json

from typing import Optional, Dict, List, Union, Tuple, Any, TYPE_CHECKING, Set

from mcd_task.globals import *

if TYPE_CHECKING:
    from mcdreforged.api.types import MCDReforgedLogger


class ResponsibleManager:
    def __init__(self):
        self.path = RESG_PATH   # type: str
        self.player_work = {}   # type: Dict[str, Set[str]]

    def rename_player(self, old_name: str, new_name: str, should_save=True):
        value = self.player_work.pop(old_name)
        self.player_work[new_name] = value
        if should_save:
            self.save()
        return value

    def rename_task(self, old_title: Union['TitleList', str],
                    new_title: Union['TitleList', str], should_save=True) -> None:
        old_title, new_title = str(old_title), str(new_title)
        for value in self.player_work.values():
            if old_title in value:
                value.remove(old_title)
                value.add(new_title)
        if should_save:
            self.save()

    def remove_task(self, task_title: Union['TitleList', str], should_save=True) -> None:
        task_title = str(task_title)
        for value in self.player_work.values():
            if task_title in value:
                value.remove(task_title)
        if should_save:
            self.save()

    def add_work(self, player: str, task_title: Union['TitleList', str], should_save=True) -> None:
        task_title = str(task_title)
        if player not in self.player_work.keys():
            self.player_work[player] = set()
        if task_title not in self.player_work[player]:
            self.player_work[player].add(task_title)
        else:
            raise DuplicatedSameTask(task_title + " duplicated")
        if should_save:
            self.save()

    def rm_work(self, player: str, task_title: Union['TitleList', str], should_save=True) -> None:
        task_title = str(task_title)
        if player not in self.player_work.keys():
            self.player_work[player] = set()
        if task_title not in self.player_work[player]:
            raise TaskNotFoundError(TitleList(task_title))
        self.player_work[player].remove(task_title)
        if should_save:
            self.save()

    def save(self) -> None:
        with open(self.path, 'w', encoding='UTF-8') as f:
            json.dump(self.player_work, f, indent=4, ensure_ascii=False)

    def load(self) -> None:
        with open(self.path, 'r', encoding='UTF-8') as f:
            self.player_work = json.load(f)

    def get_responsibles(self, task_title: Union['TitleList', str]):
        task_title = str(task_title)
        ret = set()
        for key, value in self.player_work.items():
            if task_title in value:
                ret = ret.add(key)
        return list(ret)

    def __getitem__(self, player: str) -> Set[str]:
        return self.player_work.get(player, set())


class TitleList:
    def __init__(self, titles: Optional[Union[str, 'TitleList']] = None):
        self.titles = list(str(titles).split('.')) if titles is not None else []
        self.removed = TitleList()

    def pop_head(self) -> str:
        ret = self.titles.pop(0)
        self.removed.append(ret)
        return ret

    def pop_tail(self) -> str:
        ret = self.titles.pop()
        self.removed.lappend(ret)
        return ret

    @property
    def head(self) -> Optional[str]:
        ts = self.titles
        return self.titles[0] if len(ts) > 0 else None

    @property
    def tail(self) -> str:
        return self.titles[-1]

    def copy(self) -> 'TitleList':
        r = TitleList()
        r.titles = self.titles[:]
        return r

    def lappend(self, title: str) -> 'TitleList':
        titles = self.titles.copy()   # type: List[str]
        titles.reverse()
        titles.append(title)
        titles.reverse()
        self.titles = titles.copy()
        return self

    def append(self, title: str) -> 'TitleList':
        self.titles.append(title)
        return self

    @property
    def is_empty(self) -> bool:
        return len(self.titles) == 0

    # No longer support python 2.x and MCDeamon so no __unicode__ method
    def __str__(self) -> str:
        return '.'.join(self.titles)


class TaskBase:
    OPTIONAL_KEYS = [
        "deadline"
    ]

    def __init__(self):
        self.title = ""         # type: str
        self.done = False       # type: bool
        self.description = ""          # type: str
        self.sub_tasks = []      # type: List[Task]
        self.deadline = 0       # type: int
        self.__father = None      # type: Optional[Task]
        self.permission = 0

    def add_task(self, titles: 'TitleList', desc: str = '') -> None:
        """
        Add a sub-task
        :param titles: TitleList
        :param desc: str
        :return: Task
        """
        next_gen_title = titles.pop_head()
        next_gen_desc = desc if titles.is_empty else ''
        if next_gen_title not in self.child_titles:
            self.sub_tasks.append(Task(next_gen_title, self, next_gen_desc))
        if not titles.is_empty:
            self.child_map[next_gen_title].add_task(titles, desc)

    @property
    def child_map(self) -> Dict[str, 'Task']:
        ret = {}
        for item in self.sub_tasks:
            ret[item.title] = item
        return ret

    @property
    def child_titles(self) -> List[str]:
        return list(self.child_map.keys())

    def next_layer(self, titles: 'TitleList') -> Tuple[str, TitleList]:
        next_layer_title, titles = titles.pop_head()
        if next_layer_title not in next_layer_title:
            raise TaskNotFoundError(self.full_path().append(next_layer_title))
        return next_layer_title, titles

    def split_sub_tasks_by_done(self):
        undones, dones = [], []
        for t in self.sub_tasks:
            if t.done:
                dones.append(t)
            else:
                undones.append(t)
        return undones, dones

    @property
    def dict(self):
        ret = {}
        for key, value in self.__dict__.items():
            if not key.startswith('__'):
                if key == 'sub_tasks':
                    ret[key] = self.__get_sub_task_list()
                elif key not in self.OPTIONAL_KEYS or key:
                    ret[key] = value
        return ret

    def __get_sub_task_list(self) -> List[dict]:
        ret = []
        for item in self.sub_tasks:
            ret.append(item.dict)
        return ret

    def full_path(self, titles: 'TitleList' = TitleList()) -> 'TitleList':
        raise NotImplementedError('Not implemented method: Taskbase().full_path()')

    def create_sub_tasks_from_dict(self, list_dict: List[Dict[str, Any]]):
        self.sub_tasks = []
        for i in list_dict:
            task = Task(
                i["title"], self, i["description"]
            )
            task.done = i["done"]
            if i.get("deadline"):
                task.set_deadline(i["deadline"])
            task.create_sub_tasks_from_dict(i["sub_tasks"])
            self.sub_tasks.append(task)

    def __getitem__(self, titles: Union[TitleList, str]) -> 'Task':
        if isinstance(titles, str):
            titles = TitleList(titles)
        next_layer_title, titles = self.next_layer(titles)
        if next_layer_title not in self.child_titles:
            raise TaskNotFoundError(titles.lappend(next_layer_title))
        if titles.is_empty:
            return self.child_map[next_layer_title]
        return self.child_map[next_layer_title][titles]


class Task(TaskBase):
    def __init__(self, title: str, father: Union['Task', 'TaskBase'], desc: str):
        super().__init__()
        self.title = title
        self.father = father
        self.description = desc
        self.__manager = None   # type: Optional[TaskManager]

    def reinit(self) -> None:
        """
        Reinitialize this task, for debug only
        :return: None
        """
        if DEBUG_MODE:
            self.title = ''
            self.done = False
            self.description = ''
            self.sub_tasks = []     # type: List[Task]

    def full_path(self, titles: TitleList = TitleList()) -> TitleList:
        """
        Get full path titles of this task
        :param titles: TitleList
        :return: TitleList
        """
        return self.__father.full_path(titles.lappend(self.title))

    def set_deadline(self, deadline_timestamp: int):
        self.deadline = deadline_timestamp

    # Deprecated(?)
    def get_manager(self) -> 'TaskManager':
        if self.__manager is None:
            if isinstance(self.__father, TaskManager):
                self.__manager = self.__father
            else:
                self.__manager = self.__father.get_manager()
        return self.__manager


class TaskManager(TaskBase):
    def __init__(self) -> None:
        super().__init__()
        self.__path = TASK_PATH
        self.__responsible_manager = ResponsibleManager()

    def get_responsible_manager(self):
        return self.__responsible_manager

    def full_path(self, titles: 'TitleList' = TitleList()) -> 'TitleList':
        return titles

    def delete_task(self, titles: 'TitleList') -> None:
        title_to_del = titles.pop_tail()
        father_delete = self[titles]
        task = father_delete.child_map[title_to_del]
        father_delete.sub_tasks.remove(task)
        self.__responsible_manager.remove_task(titles)

    def rename_task(self, titles: 'TitleList', new_title: str) -> None:
        self[titles].title = new_title
        new_titles = titles.copy()
        new_titles.pop_tail()
        new_titles.append(new_title)
        self.__responsible_manager.rename_task(titles, new_title)

    def edit_desc(self, titles: 'TitleList', new_desc: str) -> None:
        self[titles].description = new_desc

    def done_task(self, titles: 'TitleList'):
        self[titles].done = True

    def undone_task(self, titles: 'TitleList'):
        self[titles].done = False

    def save(self):
        with open(self.__path, 'w', encoding='UTF-8') as f:
            json.dump(self.dict, f, indent=4, ensure_ascii=False)

    def load(self):
        if not os.path.isfile(self.__path):
            self.save()
        with open(self.__path, 'r', encoding='UTF-8') as f:
            js = json.load(f)
        self.create_sub_tasks_from_dict(js["sub_tasks"])

    def set_responsible(self, titles: TitleList, *res):
        num = 0
        for r in res:
            try:
                self.__responsible_manager.add_work(r, titles, should_save=False)
            except DuplicatedSameTask:
                pass
            else:
                num += 1
        self.__responsible_manager.save()

    def rm_responsible(self, titles: TitleList, *res):
        num = 0
        for r in res:
            try:
                self.__responsible_manager.rm_work(r, titles, should_save=False)
            except TaskNotFoundError:
                pass
            else:
                num += 1
        self.__responsible_manager.save()
        return num

    def set_perm(self, titles: TitleList, perm_level: int) -> None:
        if perm_level in [0, 1, 2, 3, 4]:
            self[titles].permission = perm_level


class TaskNotFoundError(Exception):
    def __init__(self, titles: TitleList) -> None:
        self.titles = titles


class DuplicatedSameTask(Exception):
    pass


class IllegalTaskName(Exception):
    def __init__(self, titles):
        self.titles = titles
