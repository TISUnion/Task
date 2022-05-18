import time
from typing import Optional, Union, List

from mcdreforged.command.command_source import CommandSource, PlayerCommandSource

from mcd_task.global_variables import GlobalVariables


class TitleList:
    def __init__(self, titles: Optional[Union[str, 'TitleList']] = None):
        self.titles = list(str(titles).split('.')) if titles is not None else []
        self.__removed = []

    def pop_head(self) -> str:
        ret = self.titles.pop(0)
        self.__removed.append(ret)
        return ret

    def pop_tail(self) -> str:
        ret = self.titles.pop()
        self.__removed = self.removed.copy().lappend(ret).titles
        return ret

    @property
    def removed(self):
        return TitleList('.'.join(self.__removed).strip('.'))

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


def formatted_time(timestamp: float, locale: Optional[str] = None) -> str:
    """
    Format time text with specified locale
    :param timestamp:
    :param locale:
    :return:
    """
    return time.strftime(GlobalVariables.server.tr("mcd_task.time_format", lang=locale), time.localtime(timestamp))


def source_name(source: CommandSource):
    if isinstance(source, PlayerCommandSource):
        return source.player
    else:
        return source.__class__.__name__