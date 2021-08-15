import os
import json

from typing import List, Dict, Optional, Any, Union
from parse import parse

from mcd_task.task_manager import TitleList, TaskNotFoundError
from mcd_task.globals import RESG_PATH


class ResponsibleGroup:
    def __init__(self, title: str, *args: str) -> None:
        self.title = title
        self.players = list(args)     # type: List[str]
        self.tasks = []               # type: List[str]

    def append(self, *args) -> List[str]:
        ret = []
        for p in args:
            if p not in self.players:
                self.players.append(p)
                ret.append(p)
        return ret

    def remove(self, *args) -> List[str]:
        ret = []
        for p in args:
            if p in self.players:
                ret.append(p)
                self.players.remove(p)
        return ret

    @property
    def dict(self) -> Dict[str, Any]:
        return self.__dict__

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResponsibleGroup':
        instance = cls('', *[])
        instance.__dict__.update(data)
        return instance

    @property
    def can_be_removed(self) -> bool:
        return bool(self.tasks)

    def add_work(self, title: Union[TitleList, str]) -> None:
        if str(title) not in self.tasks:
            self.tasks.append(str(title))

    def rm_work(self, title: Union[TitleList, str]) -> None:
        text = str(title)
        if text not in self.tasks:
            raise TaskNotFoundError(TitleList(text))
        self.tasks.append(text)

    def has_task(self, titles: Union[TitleList, str]) -> bool:
        return str(titles) in self.tasks


class ResponsibleManager:
    def __init__(self):
        self.path = RESG_PATH   # type: str
        self.groups = []        # type: List[ResponsibleGroup]
        self.player_work = {}   # type: Dict[str, List[str]]

    def rename(self, title: str, new_title: str) -> None:
        target = self[title]
        target.title = new_title
        self.save()

    def new(self, *args) -> str:
        title = self.__get_default_title()
        self.groups.append(ResponsibleGroup(
           title, *args
        ))
        self.save()
        return title

    def add_work(self, name: str, task_title: Union[TitleList, str]) -> None:
        res = self.get_actual_title(name)
        if isinstance(res, ResponsibleGroup):
            res.add_work(str(task_title))
        else:
            if res in self.player_work.keys():
                self.player_work[res].append(task_title)
            else:
                self.player_work[res] = [task_title]

    def rm_work(self, name: str, task_title: Union[TitleList, str]) -> None:
        res = self.get_actual_title(name)
        if isinstance(res, ResponsibleGroup):
            res.rm_work(str(task_title))
        else:
            if res in self.player_work.keys():
                self.player_work[res].remove(task_title)
            else:
                if isinstance(task_title, str):
                    task_title = TitleList(task_title)
                raise TaskNotFoundError(task_title)

    def exist(self, title) -> bool:
        return self[title] is not None

    def __get_default_title(self) -> str:
        ret = None
        num = 0
        while not ret:
            num += 1
            title = 'group_{}'.format(str(num))
            if not self.exist(title):
                ret = title
        return ret

    def save(self) -> None:
        gr = []
        for item in self.groups:
            gr.append(item.dict)
        js = {
            "players": self.player_work,
            "groups": gr
        }
        with open(self.path, 'w', encoding='UTF-8') as f:
            json.dump(js, f, indent=4, ensure_ascii=False)

    def load(self) -> None:
        if not os.path.isfile(self.path):
            with open(self.path, 'w', encoding='UTF-8') as f:
                json.dump({"players": {}, "groups": []}, f)
        with open(self.path, 'w', encoding='UTF-8') as f:
            js = json.load(f)
        self.groups = []
        self.player_work = js["players"]
        for item in js["groups"]:
            group = ResponsibleGroup.from_dict(item)
            if not self.exist(group.title):
                self.groups.append(group)

    def get_player_group_titles(self, player: str) -> List[str]:
        ret = []
        for g in self.groups:
            if player in g.players:
                ret.append(g.title)
        return ret

    def get_player_tasks(self, player: str) -> Optional[List[str]]:
        return self.player_work.get(player)

    def get_actual_title(self, formatted_title: Union[ResponsibleGroup, str]) -> Union[ResponsibleGroup, str]:
        # ResponsibleGroup
        if isinstance(formatted_title, ResponsibleGroup):
            if formatted_title not in self.groups:
                return formatted_title.title
            else:
                return formatted_title
        # str
        psd = parse(RESG_FORMAT, formatted_title)
        if psd:
            return self[psd["title"]]
        return formatted_title

    def get_responsibles(self, titles: Union[TitleList, str]):
        resp, resg = [], []
        for player, task in self.player_work.items():
            if str(task) == str(titles):
                resp.append(player)
        for gr in self.groups:
            if gr.has_task(titles):
                resg.append(gr)
        return resp, resg

    def __getitem__(self, title: str) -> Optional[ResponsibleGroup]:
        for g in self.groups:
            if g.title == title:
                return g
        return None
