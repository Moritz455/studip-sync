__all__ = ['Plugin']

import os.path
import subprocess
from datetime import timedelta

from studip_sync.helpers import JSONConfig, ConfigError
from studip_sync.plugins import PluginBase
import pickle

import requests

BASE_URL = 'https://api.notion.com/v1'


class CredentialsError(PermissionError):
    pass


def is_iterable(obj):
    try:
        iter(obj)
    except TypeError:
        return False
    else:
        return True


class PluginConfig(JSONConfig):

    @property
    def database_id(self):
        if not self.config:
            return
        return self.config.get("database_id")

    @property
    def datasource_id(self):
        if not self.config:
            return
        return self.config.get("datasource_id")

    @property
    def notion_token(self):
        if not self.config:
            return
        return self.config.get("notion_token")


class Plugin(PluginBase):

    def __init__(self, config_path):
        super(Plugin, self).__init__("notion", config_path, PluginConfig)
        self.service = None

    def hook_configure(self):
        super(Plugin, self).hook_configure()

        notion_token = input("Enter your Notion Secret: ")
        database_id = input("Enter the ID of your Notion Database: ")

        if not notion_token or not database_id:
            print("Please enter your Notion Secret and Database ID.")
            return 1

        results = self.send_get_request('databases', notion_token=notion_token,
                                        database_id=database_id)
        # items = results.get('data_sources',[])
        if not results.get('object') == 'database':
            print("Invalid Notion token or database id!")
            return 1
        # for item in items:
        #     print(u'{0} ({1})'.format(item['name'], item['id']))
        #
        # datasource_id = input("Please select a datasource id to use: ")
        #
        # if datasource_id not in [item['id'] for item in items]:
        #     print("Invalid dataource id! Please select a datasource if from the list.")
        #     return 1

        new_datasource = {
            "parent": {
                "type": "database_id",
                "database_id": database_id
            },
            "properties": {
                "Name": {
                    "name": "Name",
                    "type": "title",
                    "title": {}
                },
                "Course": {
                    "name": "Course",
                    "type": "select",
                    "select": {}
                },
                "Upload Date": {
                    "name": "Upload Date",
                    "type": "created_time",
                    "created_time": {}
                },
                "File": {
                    "name": "File",
                    "type": "files",
                    "files": {}
                }
            },
            "title": [
                {
                    "type": "text",
                    "text": {"content": "StudIP Sync"}
                }
            ]
        }

        results = self.send_post_request('data_sources', new_datasource, notion_token=notion_token, datasource_id="")
        datasource_id = results.get('id')

        config = {"notion_token": notion_token, "database_id": database_id,
                  "datasource_id": datasource_id}

        self.save_plugin_config(config)

    def hook_file_download_successful(self, filename, course_save_as, full_filepath):
        if self.config and self.config.datasource_id:
            parent_datasource_id = self.config.datasource_id

        body = {
            "parent": {
                "data_source_id": parent_datasource_id
            },
            "properties": {
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": filename
                            }
                        }
                    ]
                },
                "Course": {
                    "select": {}
                },
                "File": {
                    "files": {}
                }
            }
        }


    def send_get_request(self, endpoint, payload=None, **kwargs):
        """Send a GET request to the Notion API."""

        target_id = ''
        notion_token = kwargs.get("notion_token") or self.config.notion_token
        if endpoint == 'databases':
            target_id = kwargs.get("database_id") or self.config.database_id
        elif endpoint == 'data_sources':
            target_id = kwargs.get("datasource_id") or self.config.datasource_id
        headers = {
            "Authorization": "Bearer " + notion_token,
            "Content-Type": "application/json",
            "Notion-Version": "2025-09-03",
        }
        url = f"{BASE_URL}/{endpoint}/{target_id}"

        response = requests.get(url, headers=headers, json=payload)
        return response.json()

    def send_post_request(self, endpoint, payload=None, **kwargs):
        """Send a POST request to the Notion API."""

        target_id = ''
        notion_token = kwargs.get("notion_token") or self.config.notion_token
        if endpoint == 'databases':
            target_id = kwargs.get("database_id") or self.config.database_id
        elif endpoint == 'data_sources' and kwargs.get("querry")==True:
            target_id = kwargs.get("datasource_id") or self.config.datasource_id
        headers = {
            "Authorization": "Bearer " + notion_token,
            "Content-Type": "application/json",
            "Notion-Version": "2025-09-03",
        }
        url = f"{BASE_URL}/{endpoint}/{target_id}"

        response = requests.post(url, headers=headers, json=payload)
        return response.json()
