from mcd_task.utils import TitleList


class TaskNotFound(Exception):
    def __init__(self, titles: TitleList, father: TitleList = None) -> None:
        self.titles = str(titles)
        self.father = str(father) if father is not None else None

    def __str__(self):
        if self.father is not None:
            return f"{self.father} has no sub-task named {self.titles}"
        else:
            return f"{self.titles} not found"


class DuplicatedTask(Exception):
    pass


class IllegalTaskName(Exception):
    def __init__(self, titles):
        self.titles = str(titles)
