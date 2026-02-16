from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class DriveService:
    def __init__(self, creds: Credentials):
        self.service = build("drive", "v3", credentials=creds)
        self._folder_id: str | None = None

    def _get_or_create_folder(self, folder_name: str) -> str:
        """Find or create the target folder in Google Drive."""
        query = (
            f"name='{folder_name}' and "
            f"mimeType='application/vnd.google-apps.folder' and "
            f"trashed=false"
        )
        results = self.service.files().list(q=query, spaces="drive").execute()
        items = results.get("files", [])

        if items:
            return items[0]["id"]

        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = self.service.files().create(body=file_metadata, fields="id").execute()
        return folder["id"]

    def upload_notes_as_doc(
        self,
        notes_filepath: str,
        doc_title: str,
        folder_name: str = "notes",
    ) -> str:
        """Upload a markdown file as a Google Doc. Returns the Google Doc URL."""
        if not self._folder_id:
            self._folder_id = self._get_or_create_folder(folder_name)

        file_metadata = {
            "name": doc_title,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [self._folder_id],
        }

        media = MediaFileUpload(
            notes_filepath,
            mimetype="text/markdown",
            resumable=True,
        )

        file = (
            self.service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id, webViewLink",
            )
            .execute()
        )

        return file.get("webViewLink", "")
