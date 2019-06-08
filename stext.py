# -*- coding: utf-8 -*-
from __future__ import unicode_literals


import json


class SColor(object):
    black = "black"
    darkBlue = "dark_blue"
    darkGreen = "dark_green"
    darkAqua = "dark_aqua"
    darkRed = "dark_red"
    darkPurple = "dark_purple"
    gold = "gold"
    gray = "gray"
    darkGray = "dark_gray"
    blue = "blue"
    green = "green"
    aqua = "aqua"
    red = "red"
    lightPurple = "light_purple"
    yellow = "yellow"
    white = "white"


class SStyle(object):
    bold = "bold"
    italic = "italic"
    underlined = "underlined"
    strikethrough = "strikethrough"
    obfuscated = "obfuscated"


class SAction(object):
    none = ""
    suggest = "suggest_command"
    run = "run_command"


class SText(object):
    def __init__(self, text='', color=SColor.white, styles=None, click_action=SAction.none, click_value='', hover_text=None):
        self.text = text
        self.color = color
        self.styles = styles
        self.click_action = click_action
        self.click_value = click_value
        self.hover_text = hover_text  # type: SText

    def to_json_object(self):
        d = {
            "text": self.text,
            "color": self.color,
        }

        # 沙雕 MC 虽然用了 json 格式，但解析还是按照原来的字符形式来解析的，必须全部置 False 才能修改过来
        all_styles = [SStyle.bold, SStyle.italic, SStyle.underlined, SStyle.strikethrough, SStyle.obfuscated]
        for s in all_styles:
            d[s] = False

        if self.styles is not None:
            for s in self.styles:
                d[s] = True

        if self.click_action != SAction.none:
            d["clickEvent"] = {
                "action": self.click_action,
                "value": self.click_value,
            }

        if self.hover_text is not None:
            d["hoverEvent"] = {
                "action": "show_text",
                "value": {
                    "text": "",
                    "extra": [self.hover_text.to_json_object()],
                }
            }

        return d

    def set_click_suggest(self, text):
        self.click_action = SAction.suggest
        self.click_value = text

    def set_click_command(self, text):
        self.click_action = SAction.run
        self.click_value = text

    @staticmethod
    def newline():
        return SText('\n')

    @staticmethod
    def indent(indent=0):
        space = ' '
        return SText(indent * space)

    @staticmethod
    def space():
        return SText(' ')


class STextList(object):
    def __init__(self, *texts):
        self.texts = []
        self.append(*texts)

    def append(self, *texts):
        for t in texts:
            if t is not None:
                self.texts.append(t)

    def extend(self, other):
        # type: (STextList) -> None
        self.texts.extend(other.texts)

    def to_json_object(self):
        r = [t.to_json_object() for t in self.texts]
        return r


def show_to_player(server, player, stext):
    o = stext.to_json_object()
    message = json.dumps(o)
    cmd = "/tellraw {} {}".format(player, message)
    server.execute(cmd)
