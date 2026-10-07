"""Stud.IP file synchronization tool.

A command line tool that keeps track of new files on Stud.IP and downloads them to your computer.
"""

__license__ = "Unlicense"
__version__ = "2.1.1"
__author__ = __maintainer__ = "lenke182"


def _get_config_path():
    import os
    prefix = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    path = os.path.join(prefix, "studip-sync/")
    return os.path.expanduser(path)


def get_config_file():
    import os
    from studip_sync.arg_parser import ARGS
    from studip_sync.constants import CONFIG_FILENAME

    config_target = None
    if ARGS and ARGS.config:
        config_target = ARGS.config
    elif os.environ.get("STUDIP_CONFIG_FILE"):
        config_target = os.environ.get("STUDIP_CONFIG_FILE")

    if config_target:
        if os.path.isdir(config_target) or config_target.endswith("/") or config_target.endswith(
            "\\") or not config_target.endswith(".json"):
            return os.path.join(config_target, CONFIG_FILENAME)
        return config_target
    else:
        return os.path.join(CONFIG_PATH, CONFIG_FILENAME)


CONFIG_PATH = _get_config_path()
