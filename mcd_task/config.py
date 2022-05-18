from typing import Any, Dict, Optional

from mcdreforged.api.all import PluginServerInterface, Serializable

from mcd_task.constants import CONFIG_PATH, DEBUG_MODE


class Config(Serializable):
    permission: Dict[str, int] = {
        "help":  0,
        "list": 0,
        "detail": 0,
        "list-all": 0,
        "list-done": 0,
        "player": 2,
        "responsible": 2,
        "unresponsible": 2
    }
    detect_player_rename: bool = True
    default_overview_instead_of_list: bool = True
    overview_deadline_warning_threshold: int = 1  # days
    overview_maximum_task_amount: int = 10

    @classmethod
    def load(cls, server: PluginServerInterface):
        return server.load_config_simple(
            file_name=CONFIG_PATH, default_config=cls.get_default().serialize(), in_data_folder=False, target_class=cls
        ).set_server(server)

    def save(self):
        self.__server.save_config_simple(self, file_name=CONFIG_PATH, in_data_folder=False)

    def set_server(self, server: PluginServerInterface):
        self.__server = server
        return self

    def __init__(self, **kwargs) -> None:
        super(Config, self).__init__(**kwargs)
        self.__server: Optional[PluginServerInterface] = None

    @staticmethod
    def __get_key_from_dict(target_dict: Dict[str, Any], key: str = None) -> Any:
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

    def get_permission(self, cmd: str):
        return self.permission.get(cmd, 1)

    @staticmethod
    def __set_key_to_dict(target_dict: Dict[str, Any], key: str, value: Any):
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
        ret = self.__get_key_from_dict(self.serialize(), key)
        if ret is None:
            self.__server.logger.debug("An empty value is returned from config, is it a invalid key?\n" +
                                       "Requested key: {}".format(key), no_check=DEBUG_MODE)
            default_value = self.__get_key_from_dict(self.get_default(), key)
            if default_value:
                self.__set_key_to_dict(vars(self), key, default_value)
                self.save()
                self.__server.logger.info("Restored default value for {}".format(key))
        return ret
