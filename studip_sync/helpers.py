import json
import os


class ConfigError(Exception):
    pass


class JSONConfig(object):
    def __init__(self, config_path=None):
        super(JSONConfig, self).__init__()

        if not config_path:
            raise ConfigError("Config file missing! Run 'studip-sync --init' to create a new "
                              "config file")

        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                self.config = json.load(config_file)
        except (FileNotFoundError, TypeError):
            raise ConfigError("Config file missing! Run 'studip-sync --init' to create a new "
                              "config file")
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file '{config_path}': {e}")

        self._check()

    def _check(self):
        pass

    @staticmethod
    def save_config(path, config):
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(path, "w", encoding="utf-8") as config_file:
            print("Writing new config to '{}'".format(path))
            json.dump(config, config_file, ensure_ascii=False, indent=4)
