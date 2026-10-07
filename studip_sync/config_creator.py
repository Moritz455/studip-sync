import getpass
import json
import os

from studip_sync import get_config_file
from studip_sync.constants import (
    LOGIN_PRESETS,
    LOGIN_PRESET_KEYS,
    AUTHENTICATION_TYPES,
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


CUSTOM_PROVIDER_KEY = "custom"


class EnvConfigError(ValueError):
    pass


def _env(*names):
    """Returns the first non-empty environment variable of the given names"""
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def get_login_from_env():
    """Returns (base_url, auth_key, auth_data) based on STUDIP_PROVIDER"""
    valid = ", ".join(list(LOGIN_PRESET_KEYS) + [CUSTOM_PROVIDER_KEY])
    provider = (_env("STUDIP_PROVIDER") or "").lower()

    if not provider:
        raise EnvConfigError(f"STUDIP_PROVIDER is not set. Valid values: {valid}")

    if provider != CUSTOM_PROVIDER_KEY:
        preset = LOGIN_PRESET_KEYS.get(provider)
        if preset is None:
            raise EnvConfigError(f"Unknown STUDIP_PROVIDER '{provider}'. Valid values: {valid}")
        return preset.base_url, preset.auth_type, dict(preset.auth_data)

    # Custom server: everything comes from environment variables
    base_url = _env("STUDIP_BASE_URL", "BASE_URL")
    auth_key = _env("STUDIP_AUTH_TYPE")

    missing = [name for name, value in (("STUDIP_BASE_URL", base_url),
                                        ("STUDIP_AUTH_TYPE", auth_key)) if not value]
    if missing:
        raise EnvConfigError("STUDIP_PROVIDER=custom requires: " + ", ".join(missing))

    if auth_key not in AUTHENTICATION_TYPES:
        raise EnvConfigError(f"Unknown STUDIP_AUTH_TYPE '{auth_key}'. "
                             f"Valid values: {', '.join(AUTHENTICATION_TYPES)}")

    # STUDIP_AUTH_TYPE_DATA is optional and must be a JSON object
    raw_data = _env("STUDIP_AUTH_TYPE_DATA")
    try:
        auth_data = json.loads(raw_data) if raw_data else {}
    except json.JSONDecodeError as e:
        raise EnvConfigError(f"STUDIP_AUTH_TYPE_DATA is not valid JSON: {e}")
    if not isinstance(auth_data, dict):
        raise EnvConfigError("STUDIP_AUTH_TYPE_DATA must be a JSON object")

    # Dedicated variables take precedence over STUDIP_AUTH_TYPE_DATA
    login_url = _env("STUDIP_LOGIN_URL", "STUDIP_AUTH_LOGIN_URL")
    sso_post_url = _env("STUDIP_SSO_POST_URL", "STUDIP_AUTH_SSO_POST_URL")
    if login_url:
        auth_data["login_url"] = login_url
    if sso_post_url:
        auth_data["sso_post_url"] = sso_post_url

    if auth_key == "shibboleth":
        missing = [k for k in ("login_url", "sso_post_url") if not auth_data.get(k)]
        if missing:
            raise EnvConfigError("auth type 'shibboleth' requires: " + ", ".join(missing))

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

        try:
            base_url, auth_key, auth_data = get_login_from_env()
        except EnvConfigError as e:
            print(f"ERROR: {e}")
            return False

        files_destination = (
            os.environ.get("STUDIP_FILES_DESTINATION")
            or os.environ.get("STUDIP_FILES_DEST")
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
