__all__ = ['Plugin']

import mimetypes
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

        results = self.send_get_request('databases', "application/json", notion_token=notion_token,
                                        database_id=database_id)
        if not results.get('object') == 'database':
            print("Invalid Notion token or database id!")
            return 1

        create_datasource = input("Do you want to create a new Datasource? (y/N) (default: yes): ")
        if create_datasource == "N":

            items = results.get('data_sources', [])

            for item in items:
                print(u'{0} ({1})'.format(item['name'], item['id']))

            datasource_id = input("Please select a datasource id to use: ")

            if datasource_id not in [item['id'] for item in items]:
                print("Invalid dataource id! Please select a datasource if from the list.")
                return 1
        else:
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

            results = self.send_post_request('data_sources', new_datasource,
                                             notion_token=notion_token, datasource_id="")
            datasource_id = results.get('id')

        config = {"notion_token": notion_token, "database_id": database_id,
                  "datasource_id": datasource_id}

        self.save_plugin_config(config)

    def hook_file_download_successful(self, filename, course_save_as, full_filepath):

        file_extension = os.path.splitext(filename)[1][1:]

        if file_extension not in ["aac", "adts", "mid", "midi", "mp3", "mpga", "m4a", "m4b", "mp4",
                                  "oga", "ogg", "wav", "wma", "pdf", "txt", "json", "doc", "dot",
                                  "docx", "dotx", "xls", "xlt", "xla", "xlsx", "xltx", "ppt",
                                  "pot", "pps", "ppa", "pptx", "potx", "gif", "heic", "jpeg",
                                  "jpg", "png", "svg", "tif", "tiff", "webp", "ico", "amv", "asf",
                                  "wmv", "avi", "f4v", "flv", "gifv", "m4v", "mp4", "mkv", "webm",
                                  "mov", "qt", "mpeg"]:
            print("Invalid file extension.")
            return
        if self.config and self.config.datasource_id:
            parent_datasource_id = self.config.datasource_id
        else:
            return
        body = {
            "mode": "single_part",
            "filename": filename,
        }
        self.print("Uploading new File: " + filename)
        result = self.send_post_request("file_uploads", body)
        if result.get('object') == 'file_upload':
            upload_id = result.get('id')
        # Abbruch Bedingung
        else:
            return
        # Todo: Wie Datei als File übergeben
        result = self.send_post_request("file_uploads", querry=True, files=full_filepath,
                                        file_upload_id=upload_id, additional_path="send")
        # result = self.send_post_request("file_uploads", querry=True, file_upload_id=upload_id, additional_path="complete")
        if result.get('object') == 'file_upload' and result.get('status') == 'uploaded':
            file_id = result.get('id')
        # Abbruch Bedingung
        else:
            return

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
                    "select": {
                        "name": course_save_as
                    }
                },
                "File": {
                    "files": {
                        "id": file_id,
                        "filename": filename
                    }
                }
            }
        }
        result = self.send_post_request("pages", body)
        if result.get('object') == 'page':
            self.print("File successfully Uploaded: " + full_filepath)

    def send_get_request(self, endpoint, content_type, payload=None, **kwargs):
        """Send a GET request to the Notion API."""

        target_id = ''
        notion_token = kwargs.get("notion_token") or self.config.notion_token
        if endpoint == 'databases':
            target_id = kwargs.get("database_id") or self.config.database_id
        elif endpoint == 'data_sources':
            target_id = kwargs.get("datasource_id") or self.config.datasource_id
        headers = {
            "Authorization": "Bearer " + notion_token,
            "Content-Type": content_type,
            "Notion-Version": "2025-09-03",
        }
        url = f"{BASE_URL}/{endpoint}/{target_id}"

        response = requests.get(url, headers=headers, json=payload)
        return response.json()

    def send_post_request(self, endpoint, payload=None, querry=False, **kwargs):
        """Send a POST request to the Notion API."""

        target_id = None
        additional_path = None

        if kwargs.get("additional_path"):
            additional_path = kwargs.get("additional_path")
        notion_token = kwargs.get("notion_token") or self.config.notion_token
        if endpoint == 'databases' and querry == True:
            target_id = kwargs.get("database_id") or self.config.database_id
        elif endpoint == 'data_sources' and querry == True:
            target_id = kwargs.get("datasource_id") or self.config.datasource_id
        elif endpoint == 'file_uploads' and querry == True:
            target_id = kwargs.get("file_upload_id")

        url = f"{BASE_URL}/{endpoint}"
        if target_id:
            url = f"{url}/{target_id}"
        if additional_path:
            url = f"{url}/{additional_path}"

        if kwargs.get("files"):
            filepath = kwargs.get("files")
            filename = os.path.basename(filepath)
            mime_type, _ = mimetypes.guess_type(filepath)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            with open(filepath, 'rb') as f:
                files = {
                    'file': (filename, f, mime_type)
                }
                headers = {
                    "Authorization": "Bearer " + notion_token,
                    "Notion-Version": "2025-09-03",
                    "Content-Type": "singlepart/form-data"
                }
                # Todo: Warum unauthorized?
                response = requests.post(url, headers, files=files)
        else:
            headers = {
                "Authorization": "Bearer " + notion_token,
                "Content-Type": "application/json",
                "Notion-Version": "2025-09-03",
            }
            response = requests.post(url, headers=headers, json=payload)
        return response.json()
