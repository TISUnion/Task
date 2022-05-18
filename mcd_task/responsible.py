import json
import os
from typing import Dict, Set, Union, TYPE_CHECKING, Iterator

from parse import parse

from mcd_task.constants import RESG_PATH
from mcd_task.utils import TitleList
from mcd_task.exceptions import DuplicatedTask, TaskNotFound


if TYPE_CHECKING:
    from mcd_task.task_manager import TaskManager, Task


class ResponsibleManager:
    def __init__(self, task_manager: "TaskManager"):
        self.path = RESG_PATH   # type: str
        self.player_work = {}   # type: Dict[str, Set[str]]
        self.task_manager = task_manager

    def rename_player(self, old_name: str, new_name: str, should_save=True):
        value = self.player_work.pop(old_name)
        self.player_work[new_name] = value
        if should_save:
            self.save()
        return value

    def rename_task(self, old_title: Union['TitleList', str],
                    new_title: Union['TitleList', str], should_save=True) -> None:
        old_title, new_titles = str(old_title), TitleList(old_title)
        new_titles.pop_tail()
        new_titles.append(new_title)
        new_title = str(new_titles)
        new_data = {}
        for key, value in self.player_work.items():
            for t in value:
                psd = parse(old_title + '{ext}', t)
                if psd is not None:
                    new_data[key] = value.copy()
                    new_data[key].remove(t)
                    new_data[key].add(new_title + psd['ext'])
        self.player_work.update(new_data)
        if should_save:
            self.save()

    def remove_task(self, task_title: Union['TitleList', str], should_save=True) -> None:
        task_title = str(task_title)
        removed = self.player_work.copy()
        for key, value in self.player_work.items():
            for t in value.copy():
                if t.startswith(task_title):
                    removed[key].remove(t)
        self.player_work = removed
        if should_save:
            self.save()

    def add_work(self, player: str, task_title: Union['TitleList', str], should_save=True) -> None:
        task_title = str(task_title)
        if player not in self.player_work.keys():
            self.player_work[player] = set()
        if task_title not in self.player_work[player]:
            self.player_work[player].add(task_title)
        else:
            raise DuplicatedTask(task_title + " duplicated")
        if should_save:
            self.save()

    def rm_work(self, player: str, task_title: Union['TitleList', str], should_save=True) -> None:
        task_title = str(task_title)
        if player not in self.player_work.keys():
            self.player_work[player] = set()
        if task_title not in self.player_work[player]:
            raise TaskNotFound(TitleList(task_title))
        self.player_work[player].remove(task_title)
        if should_save:
            self.save()

    def save(self) -> None:
        to_save = {}
        for p, t in self.player_work.items():
            to_save[p] = list(t)
        with open(self.path, 'w', encoding='UTF-8') as f:
            json.dump(to_save, f, indent=4, ensure_ascii=False)

    def load(self) -> None:
        if not os.path.isfile(self.path):
            self.save()
        with open(self.path, 'r', encoding='UTF-8') as f:
            to_load = json.load(f)
        for p, t in to_load.items():
            self.player_work[p] = set(t)

    def get_responsibles(self, task_title: Union['TitleList', str]):
        task_title = str(task_title)
        ret = set()
        for key, value in self.player_work.items():
            if task_title in value:
                ret.add(key)
        return list(ret)

    def __getitem__(self, player: str) -> Iterator["Task"]:
        task_titles = self.player_work.get(player, set())
        for titles in task_titles:
            yield self.task_manager[titles]
