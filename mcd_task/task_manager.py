import json
import os
import time

from copy import copy
from typing import List, Dict, Tuple, Any, Union, Optional, Iterable

from mcdreforged.api.utils import Serializable, deserialize

from mcd_task.exceptions import TaskNotFound, DuplicatedTask
from mcd_task.utils import TitleList, formatted_time
from mcd_task.constants import TASK_PATH, DEBUG_MODE
from mcd_task.responsible import ResponsibleManager
from mcd_task.global_variables import GlobalVariables


SUB_TASKS = 'rue'


class TaskBase(Serializable):
    title: str = ""
    done: bool = False
    description: str = ''
    sub_tasks: List["Task"] = []
    deadline: float = 0
    permission: int = 0
    priority: Optional[int] = None

    for key, value in locals().copy().items():
        if value is sub_tasks:
            globals()['SUB_TASKS'] = key

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._father: Optional["TaskBase"] = None

    @property
    def titles(self):
        return self.full_path()

    @property
    def child_map(self) -> Dict[str, 'Task']:
        ret = {}
        for item in self.sub_tasks:
            ret[item.title] = item
        return ret

    @property
    def child_titles(self) -> List[str]:
        return list(self.child_map.keys())

    @property
    def is_not_empty(self):
        if self.deadline != 0:
            return True
        if self.description != '':
            return True
        if self.priority is not None:
            return True
        if len(self.responsibles) > 0:
            return True
        return False

    @property
    def is_done(self):
        return self.done or self._father.is_done

    def full_path(self, titles: 'TitleList' = TitleList()) -> 'TitleList':
        raise NotImplementedError('Not implemented method: TaskBase.full_path()')

    def add_task(self, titles: 'TitleList', desc: str = '') -> None:
        next_gen_title = titles.pop_head()
        next_gen_desc = desc if titles.is_empty else ''
        if next_gen_title not in self.child_titles:
            self.__add_task(dict(title=next_gen_title, description=next_gen_desc))
        if not titles.is_empty:
            self.child_map[next_gen_title].add_task(titles, desc)

    def next_layer(self, titles: 'TitleList') -> Tuple[str, TitleList]:
        next_layer_title = titles.pop_head()
        if next_layer_title not in next_layer_title:
            raise TaskNotFound(self.titles.copy().append(next_layer_title))
        return next_layer_title, titles

    def __add_task(self, data: dict):
        self.sub_tasks.append(Task.deserialize(data).set_father(self))

    def seek_no_father_nodes(self):
        result = []
        for item in self.sub_tasks:
            if item._father is None:
                result.append(item)
            result += item.seek_no_father_nodes()
        return result

    def create_sub_tasks_from_serialized_data(self, serialized_task_list: List[Dict[str, Any]]):
        self.__setattr__(SUB_TASKS, [])
        for item in serialized_task_list:
            self.__add_task(item)

    def set_father(self, father_node: "TaskBase"):
        if not isinstance(father_node, TaskBase):
            raise TypeError(type(father_node).__name__)
        self._father = father_node
        return self

    @classmethod
    def deserialize(cls, data: dict, **kwargs):
        GlobalVariables.debug(data)
        sub_tasks = copy(data.get(SUB_TASKS, []))
        if not isinstance(sub_tasks, list):
            raise TypeError(
                'Unsupported input type: expected class "{}" but found data with class "{}"'.format(
                    list.__name__, type(data).__name__
                ))
        data[SUB_TASKS] = []
        this_task = deserialize(data=data, cls=cls, **kwargs)
        this_task.create_sub_tasks_from_serialized_data(sub_tasks)
        return this_task

    def split_sub_tasks_by_done(self):
        undones, dones = [], []
        for t in self.sub_tasks:
            if t.done:
                dones.append(t)
            else:
                undones.append(t)
        return undones, dones

    @property
    def sorted_sub_tasks(self):
        undones, dones = self.split_sub_tasks_by_done()
        return sort_by_title(undones) + sort_by_title(dones)

    def __getitem__(self, titles: Union[TitleList, str]) -> Union['Task', 'TaskBase']:
        if isinstance(titles, str):
            titles = TitleList(titles)
        if titles.is_empty:
            return self
        next_layer_title, titles = self.next_layer(titles)
        if next_layer_title not in self.child_titles:
            raise TaskNotFound(titles.lappend(next_layer_title))
        return self.child_map[next_layer_title][titles]

    def seek_for_item_with_priority(self, sort=True, with_done=False):
        result = []
        for item in self.sub_tasks:
            if isinstance(item.priority, int):
                if with_done or not item.is_done:
                    result.append(item)
                    GlobalVariables.debug(f'Priority task found: {item.full_path()}')
            result += item.seek_for_item_with_priority(sort=False)
        return sorted(result, key=lambda task: task.priority, reverse=True) if sort else result

    def seek_for_item_with_deadline_approaching(self, sort=True, with_done=False):
        result = []
        for item in self.sub_tasks:
            if item.deadline != 0 and item.deadline - \
                    time.time() < 3600 * 24 * GlobalVariables.config.overview_deadline_warning_threshold:
                if with_done or not item.is_done:
                    result.append(item)
                    GlobalVariables.debug(f'Deadline task found: {item.full_path()}')
            result += item.seek_for_item_with_deadline_approaching(sort=False)
        return sorted(result, key=lambda task: task.deadline, reverse=False) if sort else result

    @property
    def responsibles(self):
        return GlobalVariables.task_manager.responsible_manager.get_responsibles(self.titles)

    def __str__(self):
        return str(self.serialize())


class Task(TaskBase):
    def full_path(self, titles: TitleList = TitleList()) -> TitleList:
        return self._father.full_path(titles.copy().lappend(self.title))

    def reinit(self) -> None:
        if DEBUG_MODE:
            self.title = ''
            self.done = False
            self.description = ''
            self.sub_tasks = []  # type: List[Task]

    def get_elements(self, element_name: str):
        mappings = {
            'name': str(self.titles),
            'desc': self.description,
            'priority': '' if self.priority is None else self.priority,
            'deadline': '' if self.deadline == 0 else formatted_time(self.deadline)
        }
        return mappings.get(element_name)


class TaskManager(TaskBase):
    title: str = "TaskManager"
    __responsible_manager = None

    @property
    def responsible_manager(self):
        if self.__responsible_manager is None:
            self.__responsible_manager = ResponsibleManager(self)
        return self.__responsible_manager

    def save(self):
        data = json.dumps(self.serialize(), indent=4, ensure_ascii=False)
        GlobalVariables.debug(f'Saving data: {data}')
        with open(TASK_PATH, 'w', encoding='utf8') as fp:
            fp.write(data)

    @property
    def is_done(self):
        return False

    @classmethod
    def load(cls):
        if not os.path.isfile(TASK_PATH):
            cls.get_default().save()
        with open(TASK_PATH, 'r', encoding='utf8') as fp:
            js = json.load(fp)
        manager = cls.deserialize(js)
        GlobalVariables.debug(manager.serialize())
        manager.responsible_manager.load()
        return manager

    def exists(self, titles: TitleList) -> bool:
        titles = titles.copy()
        father_titles = titles.copy()
        title = father_titles.pop_tail()
        try:
            father = self[father_titles]
        except TaskNotFound:
            return False
        if title in father.child_titles:
            return True
        else:
            return False

    def full_path(self, titles: 'TitleList' = TitleList()) -> 'TitleList':
        return titles

    #   =========================

    def add_task(self, titles: 'TitleList', desc: str = '', should_save=True) -> None:
        super(TaskManager, self).add_task(titles, desc)
        if should_save:
            self.save()

    def delete_task(self, titles: 'TitleList', should_save=True) -> None:
        titles_father = titles.copy()
        title_to_del = titles_father.pop_tail()
        father_delete = self[titles_father]
        try:
            task = father_delete.child_map[title_to_del]
        except KeyError:
            raise TaskNotFound(titles.copy(), father_delete.full_path().copy())
        father_delete.sub_tasks.remove(task)
        self.responsible_manager.remove_task(titles)

        if should_save:
            self.save()

    def rename_task(self, titles: 'TitleList', new_title: str, should_save=True) -> None:
        self[titles.copy()].title = new_title
        new_titles = titles.copy()
        new_titles.pop_tail()
        new_titles.append(new_title)
        self.responsible_manager.rename_task(titles, new_title)
        if should_save:
            self.save()

    def set_deadline(self, titles: 'TitleList', deadline: float, should_save=True) -> None:
        self[titles].deadline = deadline
        if should_save:
            self.save()

    def edit_desc(self, titles: 'TitleList', new_desc: str, should_save=True) -> None:
        self[titles].description = new_desc
        if should_save:
            self.save()

    def done_task(self, titles: 'TitleList', should_save=True):
        self[titles].done = True
        if should_save:
            self.save()

    def undone_task(self, titles: 'TitleList', should_save=True):
        self[titles].done = False
        if should_save:
            self.save()

    def set_responsible(self, titles: TitleList, *res):
        num = 0
        for r in res:
            try:
                self.responsible_manager.add_work(r, titles, should_save=False)
            except DuplicatedTask:
                pass
            else:
                num += 1
        self.responsible_manager.save()
        return num

    def rm_responsible(self, titles: TitleList, *res):
        removed = set()
        for r in res:
            try:
                self.responsible_manager.rm_work(r, titles, should_save=False)
            except TaskNotFound:
                pass
            else:
                removed.add(r)
        self.responsible_manager.save()
        return removed

    def set_perm(self, titles: TitleList, perm_level: int, should_save=True) -> None:
        if perm_level in [0, 1, 2, 3, 4]:
            self[titles].permission = perm_level
            if should_save:
                self.save()

    def set_priority(self, titles: TitleList, priority: int, should_save=True) -> None:
        self[titles].priority = priority
        if should_save:
            self.save()


def sort_by_title(unsorted_task_list: Iterable[Task]):
    return sorted(unsorted_task_list, key=lambda task: task.title)


if __name__ == "__main__":
    print(SUB_TASKS)
