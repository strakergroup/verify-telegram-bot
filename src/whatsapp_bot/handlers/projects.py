"""Project listing and detail handler for WhatsApp."""

import logging

from ...verify.client import VerifyAPIError, VerifyClient
from ...verify.models import STATUS_EMOJI
from ...whatsapp.client import WhatsAppClient
from ..session_store import WhatsAppSessionStore

logger = logging.getLogger(__name__)

MAX_DISPLAY_PROJECTS = 10


class ProjectsHandler:
    """Handles project listing and detail commands."""

    def __init__(
        self,
        wa_client: WhatsAppClient,
        session_store: WhatsAppSessionStore,
        verify_client: VerifyClient,
    ) -> None:
        self._wa = wa_client
        self._session = session_store
        self._verify = verify_client

    async def handle_list(self, phone: str) -> None:
        """List recent projects."""
        api_key = self._session.get_api_key(phone)
        if not api_key:
            await self._wa.send_text(phone, "You need to login first. Send *login*.")
            return

        try:
            projects = await self._verify.get_projects(api_key, page=1, page_size=MAX_DISPLAY_PROJECTS)
        except VerifyAPIError as e:
            logger.error("Failed to fetch projects for %s: %s", phone, e.detail)
            await self._wa.send_text(phone, "Failed to fetch projects. Please try again.")
            return

        if not projects:
            await self._wa.send_text(phone, "You have no projects yet. Send *translate* to create one.")
            return

        lines = ["*Your Recent Projects:*\n"]
        for project in projects:
            emoji = STATUS_EMOJI.get(project.status, "")
            title = project.title or "Untitled"
            date_str = project.created_at.strftime("%Y-%m-%d")
            file_count = len(project.source_files)
            lang_count = len(project.target_languages)
            lines.append(
                f"{emoji} *{title}*\n"
                f"   ID: {project.uuid}\n"
                f"   Status: {project.status.value} | {file_count} file(s) | {lang_count} lang(s)\n"
                f"   Created: {date_str}"
            )

        await self._wa.send_text(phone, "\n\n".join(lines))

    async def handle_detail(self, phone: str, project_id: str) -> None:
        """Show details for a specific project."""
        if not project_id:
            await self._wa.send_text(phone, "Usage: *project <project_id>*")
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

        emoji = STATUS_EMOJI.get(project.status, "")
        lang_names = [lang.name for lang in project.target_languages]

        file_lines = []
        for sf in project.source_files:
            target_info = ""
            if sf.target_files:
                statuses = [tf.status for tf in sf.target_files]
                target_info = f" ({', '.join(set(statuses))})"
            file_lines.append(f"  - {sf.filename}{target_info}")

        detail = (
            f"{emoji} *{project.title or 'Untitled'}*\n\n"
            f"*ID:* {project.uuid}\n"
            f"*Status:* {project.status.value}\n"
            f"*Languages:* {', '.join(lang_names)}\n"
            f"*Created:* {project.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"*Modified:* {project.modified_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"*Files:*\n" + "\n".join(file_lines)
        )

        await self._wa.send_text(phone, detail)
