import getpass
import os

from studip_sync import get_config_file
from studip_sync.constants import (
    LOGIN_PRESETS,
    AUTHENTICATION_TYPES,
    AUTHENTICATION_TYPE_DEFAULT,
    URL_BASEURL_DEFAULT,
)
from studip_sync.helpers import JSONConfig
from studip_sync.session import Session


def choose_authentication_type():
    print("Supported authentication methods:")
    i = 1
    auth_list = list(AUTHENTICATION_TYPES.items())
    for auth_key, auth_value in auth_list:
        print("{}) {}".format(i, auth_value.name()))
        i += 1

    print()

    try:
        auth_id = int(input("Choose an authentication method: "))
    except ValueError:
        raise ValueError("Please enter a valid number!")

    if auth_id <= 0 or auth_id > len(auth_list):
        raise ValueError("Please enter a valid number!")

    return auth_list[auth_id - 1]


def choose_preset():
    print("Supported universities:")
    i = 1
    for preset in LOGIN_PRESETS:
        print("{}) {}".format(i, preset.name, preset.base_url))
        i += 1

    print("{}) Custom server".format(i))
    print()

    try:
        preset_id = int(input("Choose a server: "))
    except ValueError:
        print("Invalid input! Defaulting to custom server...")
        return None

    if preset_id == i:
        return None

    if preset_id <= 0 or preset_id > len(LOGIN_PRESETS):
        print("Invalid input! Defaulting to custom server...")
        return None

    return LOGIN_PRESETS[preset_id - 1]


def get_url_and_auth_type():
    selected_preset = choose_preset()

    if selected_preset is not None:
        return selected_preset.base_url, selected_preset.auth_type, selected_preset.auth_data

    # Otherwise ask for them interactively
    base_url = input("URL of StudIP: ")
    auth_key, auth_type = choose_authentication_type()
    auth_data = auth_type.config_creator_get_auth_data()

    return base_url, auth_key, auth_data


class ConfigCreator(object):
    """Create a new config file interactively"""

    def __init__(self):
        super(ConfigCreator, self).__init__()
        self._session = Session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._session.__exit__(exc_type, exc_value, traceback)

    def new_config(self):
        base_url, auth_key, auth_data = get_url_and_auth_type()
        username = input("Username: ")
        password = getpass.getpass()

        if base_url:
            self._session.set_base_url(base_url)

        print("Logging in...")
        self._session.login(auth_key, auth_data, username, password)

        save_password = input("Save password (in clear text)? [y/N]: ").lower() in ("y", "yes")
        files_destination = input("Sync files to directory (leave empty to disable): ")
        media_destination = input("Sync media to directory (leave empty to disable): ")

        config = {
            "user": {
                "login": username
            }
        }

        if base_url:
            config["base_url"] = base_url

        if auth_key:
            config["auth_type"] = auth_key

        if auth_data:
            config["auth_type_data"] = auth_data

        if save_password:
            config["user"]["password"] = password

        if files_destination:
            config["files_destination"] = files_destination

        if media_destination:
            config["media_destination"] = media_destination

        path = get_config_file()

        JSONConfig.save_config(path, config)

    def init_from_env(self, config_path=None):
        """Create a new config file non-interactively using environment variables"""
        username = (
            os.environ.get("STUDIP_USERNAME")
            or os.environ.get("STUDIP_USER")
            or os.environ.get("STUDIP_LOGIN")
        )
        if not username:
            user_env = os.environ.get("USERNAME")
            if user_env and (os.environ.get("STUDIP_PASSWORD") or os.environ.get("STUDIP_PASS")):
                username = user_env

        if not username:
            print("No username provided in environment (set STUDIP_USERNAME or STUDIP_LOGIN).")
            return False

        password = (
            os.environ.get("STUDIP_PASSWORD")
            or os.environ.get("STUDIP_PASS")
            or os.environ.get("PASSWORD")
        )
        password_cmd = os.environ.get("STUDIP_PASSWORD_COMMAND")

        base_url = (
            os.environ.get("STUDIP_BASE_URL")
            or os.environ.get("BASE_URL")
            or URL_BASEURL_DEFAULT
        )

        preset_choice = os.environ.get("STUDIP_PRESET", "").lower().strip()
        selected_preset = None
        if preset_choice:
            try:
                preset_idx = int(preset_choice) - 1
                if 0 <= preset_idx < len(LOGIN_PRESETS):
                    selected_preset = LOGIN_PRESETS[preset_idx]
            except ValueError:
                for p in LOGIN_PRESETS:
                    if preset_choice in p.name.lower() or preset_choice in p.base_url.lower():
                        selected_preset = p
                        break

        if not selected_preset:
            for p in LOGIN_PRESETS:
                if p.base_url.rstrip("/") == base_url.rstrip("/"):
                    selected_preset = p
                    break

        if selected_preset:
            base_url = selected_preset.base_url
            auth_key = selected_preset.auth_type
            auth_data = dict(selected_preset.auth_data)
        else:
            auth_key = os.environ.get("STUDIP_AUTH_TYPE", AUTHENTICATION_TYPE_DEFAULT)
            auth_data = {}
            if auth_key == "shibboleth":
                login_url = os.environ.get("STUDIP_LOGIN_URL") or os.environ.get(
                    "STUDIP_AUTH_LOGIN_URL")
                sso_post_url = os.environ.get("STUDIP_SSO_POST_URL") or os.environ.get(
                    "STUDIP_AUTH_SSO_POST_URL")
                if login_url:
                    auth_data["login_url"] = login_url
                if sso_post_url:
                    auth_data["sso_post_url"] = sso_post_url

        files_destination = (
            os.environ.get("STUDIP_FILES_DESTINATION")
            or os.environ.get("STUDIP_FILES_DEST")
            or os.environ.get("FILES_DESTINATION")
            or "./studip_files"
        )
        media_destination = (
            os.environ.get("STUDIP_MEDIA_DESTINATION")
            or os.environ.get("STUDIP_MEDIA_DEST")
            or os.environ.get("MEDIA_DESTINATION")
        )
        plugins_env = os.environ.get("STUDIP_PLUGINS") or os.environ.get("PLUGINS") or ""
        plugins = [p.strip() for p in plugins_env.split(",") if p.strip()]

        config = {
            "user": {
                "login": username
            },
            "base_url": base_url,
            "auth_type": auth_key,
            "auth_type_data": auth_data,
            "plugins": plugins
        }

        if password:
            config["user"]["password"] = password
        elif password_cmd:
            config["user"]["password_command"] = password_cmd

        if files_destination:
            config["files_destination"] = files_destination
        if media_destination:
            config["media_destination"] = media_destination

        use_new_struct = os.environ.get("STUDIP_USE_NEW_FILE_STRUCTURE", "").lower()
        if use_new_struct in ("true", "1", "yes"):
            config["use_new_file_structure"] = True

        path = config_path or get_config_file()
        JSONConfig.save_config(path, config)
        print(f"Configuration initialized from environment and saved to '{path}'")
        return True

    @staticmethod
    def replace_config(config):
        path = get_config_file()

        JSONConfig.save_config(path, config)
