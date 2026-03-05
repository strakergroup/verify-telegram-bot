"""Download handler for WhatsApp: poll project status and send translated files."""

import asyncio
import logging
import tempfile
from pathlib import Path

from ...verify.client import VerifyAPIError, VerifyClient
from ...verify.models import STATUS_EMOJI, Project, ProjectStatus
from ...whatsapp.client import WhatsAppClient
from ..session_store import WhatsAppSessionStore

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
MAX_POLL_ATTEMPTS = 60


class DownloadHandler:
    """Handles downloading translated files from completed projects."""

    def __init__(
        self,
        wa_client: WhatsAppClient,
        session_store: WhatsAppSessionStore,
        verify_client: VerifyClient,
    ) -> None:
        self._wa = wa_client
        self._session = session_store
        self._verify = verify_client

    async def handle_download(self, phone: str, project_id: str) -> None:
        """Download translated files for a project, polling if still processing."""
        if not project_id:
            await self._wa.send_text(phone, "Usage: *download <project_id>*")
            return

        api_key = self._session.get_api_key(phone)
        if not api_key:
            await self._wa.send_text(phone, "You need to login first. Send *login*.")
            return

        try:
            project = await self._verify.get_project(api_key, project_id)
        except VerifyAPIError as e:
            logger.error("Failed to fetch project %s: %s", project_id, e.detail)
            await self._wa.send_text(phone, f"Could not find project {project_id}.")
            return

        if project.status == ProjectStatus.COMPLETED:
            await self._download_and_send(phone, api_key, project)
            return

        if project.status in (ProjectStatus.UNSUCCESSFUL, ProjectStatus.ARCHIVED):
            emoji = STATUS_EMOJI.get(project.status, "")
            await self._wa.send_text(
                phone, f"{emoji} Project is *{project.status.value}* and cannot be downloaded.",
            )
            return

        await self._wa.send_text(
            phone,
            f"Project is *{project.status.value}*. Waiting for completion...\n"
            f"(checking every {POLL_INTERVAL_SECONDS}s, up to 5 minutes)",
        )

        for attempt in range(MAX_POLL_ATTEMPTS):
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

            try:
                project = await self._verify.get_project(api_key, project_id)
            except VerifyAPIError:
                logger.warning("Poll attempt %d failed for project %s", attempt, project_id)
                continue

            if project.status == ProjectStatus.COMPLETED:
                await self._wa.send_text(phone, "Project is *COMPLETED*! Downloading files...")
                await self._download_and_send(phone, api_key, project)
                return

            if project.status == ProjectStatus.UNSUCCESSFUL:
                await self._wa.send_text(phone, "Project has *FAILED*. No files to download.")
                return

            if attempt % 6 == 5:
                await self._wa.send_text(
                    phone,
                    f"Still waiting... Status: *{project.status.value}* "
                    f"(attempt {attempt + 1}/{MAX_POLL_ATTEMPTS})",
                )

        await self._wa.send_text(
            phone,
            "Timed out waiting for project to complete.\n"
            "The project is still processing. Try *download* again later.",
        )

    async def _download_and_send(self, phone: str, api_key: str, project: Project) -> None:
        """Download all translated files and send them via WhatsApp."""
        target_files: list[tuple[str, str, str]] = []
        for source_file in project.source_files:
            if not source_file.target_files:
                continue
            for target_file in source_file.target_files:
                target_files.append((
                    target_file.target_file_uuid,
                    source_file.filename,
                    target_file.language_uuid,
                ))

        if not target_files:
            await self._wa.send_text(phone, "No translated files found in this project.")
            return

        sent_count = 0
        with tempfile.TemporaryDirectory(prefix="verify_wa_dl_") as temp_dir:
            for file_uuid, original_name, lang_uuid in target_files:
                try:
                    file_bytes = await self._verify.download_file(api_key, file_uuid)

                    stem = Path(original_name).stem
                    suffix = Path(original_name).suffix
                    download_name = f"{stem}_{lang_uuid[:8]}{suffix}"
                    local_path = Path(temp_dir) / download_name
                    local_path.write_bytes(file_bytes)

                    mime_type = self._guess_mime(suffix)
                    media_id = await self._wa.upload_media(local_path, mime_type)
                    await self._wa.send_document(
                        to=phone,
                        media_id=media_id,
                        filename=download_name,
                        caption=f"Translated: {download_name}",
                    )
                    sent_count += 1
                except VerifyAPIError as e:
                    logger.error("Failed to download file %s: %s", file_uuid, e.detail)
                    await self._wa.send_text(phone, f"Failed to download file {file_uuid}: {e.detail}")
                except Exception:
                    logger.exception("Unexpected error downloading file %s", file_uuid)
                    await self._wa.send_text(phone, f"Error downloading file {file_uuid}.")

        await self._wa.send_text(phone, f"Download complete. Sent *{sent_count}* translated file(s).")

    @staticmethod
    def _guess_mime(suffix: str) -> str:
        """Guess MIME type from file extension."""
        mime_map = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".txt": "text/plain",
            ".xliff": "application/xliff+xml",
            ".xlf": "application/xliff+xml",
            ".json": "application/json",
            ".xml": "application/xml",
            ".csv": "text/csv",
        }
        return mime_map.get(suffix.lower(), "application/octet-stream")
