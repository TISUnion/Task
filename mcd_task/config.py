import json
import os

from typing import Any, Dict, Optional

from mcd_task.constants import CONFIG_PATH, DEFAULT_CONFIG_PATH, DEBUG_MODE

from mcdreforged.api.all import PluginServerInterface


class Config:
    def __init__(self, server: PluginServerInterface) -> None:
        self.file = CONFIG_PATH
        self.default_config_path = DEFAULT_CONFIG_PATH
        self.data = {}
        self.server = server

    @property
    def default_config(self) -> Dict[str, Any]:
        with self.server.open_bundled_file(self.default_config_path) as f:
            return json.load(f)

    def __write_config(self, new_data: Optional[Dict[str, Any]] = None):
        if isinstance(new_data, dict):
            self.data.update(new_data)
        with open(self.file, 'w', encoding='UTF-8') as f:
            json.dump(self.data, f, indent=4)

    def __get_config(self):
        with open(self.file, 'r', encoding='UTF-8') as f:
            self.data.update(json.load(f))

    def load(self):
        if not os.path.isdir(os.path.dirname(self.file)):
            os.makedirs(os.path.dirname(self.file))
            self.server.logger.info('Config directory not found, created')
        if not os.path.isfile(self.file):
            self.__write_config(self.default_config)
            self.server.logger.info('Config file not found, using default')
        else:
            try:
                self.__get_config()
            except json.JSONDecodeError:
                self.__write_config(self.default_config)
                self.server.logger.info('Invalid config file, using default')
        self.server.logger.debug("Loaded config data: {}".format(str(self.data)), no_check=DEBUG_MODE)

    @staticmethod
    def __getkeyfromdict(target_dict: Dict[str, Any], key: str = None) -> Any:
        key_list = key.split('.')
        ret = target_dict.copy()
        while True:
            k = key_list.pop(0)
            ret = ret.get(k)
            if len(key_list) == 0 or not isinstance(ret, dict):
                break
        if not len(key_list) == 0:
            ret = None
        return ret

    @staticmethod
    def __setkeytodict(target_dict: Dict[str, Any], key: str, value: Any):
        key_list = key.split('.')
        dic = target_dict
        while True:
            k = key_list.pop(0)
            if not isinstance(dic.get(k), dict) and len(key_list) != 0:
                dic[k] = {}
            if len(key_list) == 0:
                dic[k] = value
                return
            dic = dic[k]

    def __getitem__(self, key: str) -> Any:
        ret = self.__getkeyfromdict(self.data, key)
        if ret is None:
            self.server.logger.debug("An empty value is returned from config, is it a invalid key?\n" +
                                     "Requested key: {}".format(key), no_check=DEBUG_MODE)
            defv = self.__getkeyfromdict(self.default_config, key)
            if defv:
                self.__setkeytodict(self.data, key, defv)
                self.__write_config()
                self.server.logger.info("Restored default value for {}".format(key))
        return ret
