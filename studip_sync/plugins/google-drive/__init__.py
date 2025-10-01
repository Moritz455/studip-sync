__all__ = ['Plugin']

import os.path
import subprocess
from datetime import timedelta

from googleapiclient.http import MediaFileUpload

from studip_sync.helpers import JSONConfig, ConfigError
from studip_sync.plugins import PluginBase
import pickle

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/drive"]


class CredentialsError(PermissionError):
    pass


class Plugin(PluginBase):

    def __init__(self, config_path):
        super(Plugin, self).__init__("google-drive", config_path, PluginConfig)
        self.token_pickle_path = os.path.join(self.config_dir, "token.pickle")
        self.credentials_path = os.path.join(self.config_dir, "credentials.json")
        self.service = None

    def hook_configure(self):
        super(Plugin, self).hook_configure()

        credentials = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.

        if os.path.exists(self.token_pickle_path):
            with open(self.token_pickle_path, 'rb') as token:
                credentials = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise CredentialsError("Missing credentials.json at " + self.credentials_path)

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                credentials = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.token_pickle_path, 'wb') as token:
                pickle.dump(credentials, token)

        service = build('drive', 'v3', credentials=credentials)
        page_token = None

        results = service.files().list(
            q="mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            spaces="drive",
            fields="nextPageToken, files(id, name, parents)",
            pageToken=page_token).execute()
        items = results.get('files', [])

        upload_folder_id = input("Please input a Folder id to use: ")

        if upload_folder_id not in [item['id'] for item in items]:
            print("Invalid folder id!")
            return 1

        config = {"upload_folder_id": upload_folder_id}

        self.save_plugin_config(config)

    def hook_start(self):
        super(Plugin, self).hook_start()

        credentials = None

        if os.path.exists(self.token_pickle_path):
            with open(self.token_pickle_path, 'rb') as token:
                credentials = pickle.load(token)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                raise CredentialsError("drive: couldn't log in")

        self.service = build('drive', 'v3', credentials=credentials)

    def hook_file_download_successful(self, filename, course_save_as, full_filepath):
        # Todo: Verarbeitung und Upload von Videos hinzufügen
        # file_extension = os.path.splitext(filename)[1][1:]

        #        if self.config and self.config.video_filetype and file_extension not in self.config.video_filetype:
        #            self.print("Skipping file: " + filename)
        #            return

        description = course_save_as

        #        if self.config and self.config.display_video_length and file_extension in DISPLAY_VIDEO_LENGTH_ALLOWED_FILETYPES:
        #            video_length = get_video_length_of_file(full_filepath)
        #            video_length_seconds = int(video_length)
        #            video_length_str = str(timedelta(seconds=video_length_seconds))
        #
        #            description = "{}: {}".format(video_length_str, description)

        return self.upload_new_file(filename, description, full_filepath)

    def upload_new_file(self, filename, course, filepath):

        if course and self.config and self.config.upload_folder_id:
            parent_folder_id = self._get_or_create_folder(course, self.config.upload_folder_id)
        elif self.config and self.config.upload_folder_id:
            parent_folder_id = self.config.upload_folder_id
        else:
            parent_folder_id = None

        body = {"name": filename}
        media = MediaFileUpload(filepath)

        if parent_folder_id:
            body["parents"] = [parent_folder_id]

        self.print("Uploading new File: " + filename)
        return self.service.files().create(body=body, media_body=media).execute()

    def _get_or_create_folder(self, folder_name, parent_folder_id):

        # Suche nach existierendem Ordner
        query = f"mimeType = 'application/vnd.google-apps.folder' and name = '{folder_name}' and '{parent_folder_id}' in parents and trashed = false"

        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=1
        ).execute()

        items = results.get('files', [])

        if items:
            # Ordner existiert bereits
            return items[0]['id']
        else:
            # Erstelle neuen Ordner
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id]
            }

            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()

            self.print(f"Ordner erstellt: {folder_name}")
            return folder.get('id')


class PluginConfig(JSONConfig):

    @property
    def upload_folder_id(self):
        if not self.config:
            return
        return self.config.get("upload_folder_id")
