import json

from typing import Any, Dict, Optional

from mcd_task.globals import *
from mcd_task.task_manager import TitleList


class Config:
    def __init__(self) -> None:
        self.file = CONFIG_PATH
        self.default_config_path = DEFAULT_CONFIG_PATH
        self.data = {}

    @property
    def default_config(self) -> Dict[str, Any]:
        with root.server.open_bundled_file(self.default_config_path) as f:
            return json.load(f)

    def __write_config(self, new_data: Optional[Dict[str, Any]] = None):
        if isinstance(new_data, dict):
            self.data.update(new_data)
        with open(self.file, 'w', encoding='UTF-8') as f:
            json.dump(self.data, f, indent=4)

    def __get_config(self):
        with open(self.file, 'r', encoding='UTF-8') as f:
            self.data.update(json.load(f))

    def load(self, server: PluginServerInterface):
        if not os.path.isdir(os.path.dirname(self.file)):
            os.makedirs(os.path.dirname(self.file))
            server.logger.info('Config directory not found, created')
        if not os.path.isfile(self.file):
            self.__write_config(self.default_config)
            server.logger.info('Config file not found, using default')
        else:
            try:
                self.__get_config()
            except json.JSONDecodeError:
                self.__write_config(self.default_config)
                server.logger.info('Invalid config file, using default')

    @staticmethod
    def __getkeyfromdict(target_dict: Dict[str, Any], key: str = None) -> Any:
        key_list = TitleList(key)
        ret = target_dict
        while True:
            k = key_list.pop_head()
            ret = ret.get(k)
            if key_list.is_empty or not isinstance(ret, dict):
                break
        if not key_list.is_empty:
            ret = None
        return ret

    def __getitem__(self, key: str) -> Any:
        ret = self.__getkeyfromdict(self.data, key)
        if ret is None:
            root.debug("An empty value is returned from config, is it a invalid key?\n",
                       "Requested key: {}".format(key))
            defv = self.__getkeyfromdict(self.default_config, key)
            if defv:
                self.__write_config({key: defv})
                root.logger.info("Restored default value for {}".format(key))
        return ret
