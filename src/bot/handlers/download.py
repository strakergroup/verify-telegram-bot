import asyncio
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from ...session.store import SessionStore
from ...verify.client import VerifyAPIError, VerifyClient
from ...verify.models import Project, ProjectStatus, STATUS_EMOJI

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
MAX_POLL_ATTEMPTS = 60  # 5 minutes max wait


def create_download_handler(
    session_store: SessionStore,
    verify_client: VerifyClient,
) -> dict:
    """Create the download handler function with injected dependencies."""

    async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /download <project_id> -- poll project and send translated files."""
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id
        api_key = session_store.get_api_key(user_id)
        if not api_key:
            await update.effective_message.reply_text(
                "You need to be logged in. Use /login first."
            )
            return

        args = context.args or []
        if not args:
            await update.effective_message.reply_text(
                "Usage: /download &lt;project_id&gt;",
                parse_mode="HTML",
            )
            return

        project_id = args[0].strip()

        # Fetch initial project status
        try:
            project = await verify_client.get_project(api_key, project_id)
        except VerifyAPIError as e:
            logger.error("Failed to fetch project %s: %s", project_id, e.detail)
            await update.effective_message.reply_text(
                f"Could not find project <code>{project_id}</code>.",
                parse_mode="HTML",
            )
            return

        # If already completed, download immediately
        if project.status == ProjectStatus.COMPLETED:
            await _download_and_send_files(
                update, api_key, project, verify_client
            )
            return

        # If failed or archived, inform the user
        if project.status in (ProjectStatus.UNSUCCESSFUL, ProjectStatus.ARCHIVED):
            emoji = STATUS_EMOJI.get(project.status, "")
            await update.effective_message.reply_text(
                f"{emoji} Project is <b>{project.status.value}</b> "
                "and cannot be downloaded.",
                parse_mode="HTML",
            )
            return

        # Project is still processing -- poll until completed
        status_msg = await update.effective_message.reply_text(
            f"Project is <b>{project.status.value}</b>. "
            "Waiting for completion...\n"
            f"(will check every {POLL_INTERVAL_SECONDS}s, up to 5 minutes)",
            parse_mode="HTML",
        )

        for attempt in range(MAX_POLL_ATTEMPTS):
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

            try:
                project = await verify_client.get_project(api_key, project_id)
            except VerifyAPIError:
                logger.warning("Poll attempt %d failed for project %s", attempt, project_id)
                continue

            if project.status == ProjectStatus.COMPLETED:
                await status_msg.edit_text(
                    "Project is <b>COMPLETED</b>! Downloading files...",
                    parse_mode="HTML",
                )
                await _download_and_send_files(
                    update, api_key, project, verify_client
                )
                return

            if project.status == ProjectStatus.UNSUCCESSFUL:
                await status_msg.edit_text(
                    "Project has <b>FAILED</b>. No files to download.",
                    parse_mode="HTML",
                )
                return

            # Update the status message periodically (every 6th poll ~ 30s)
            if attempt % 6 == 5:
                try:
                    await status_msg.edit_text(
                        f"Still waiting... Status: <b>{project.status.value}</b> "
                        f"(attempt {attempt + 1}/{MAX_POLL_ATTEMPTS})",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

        # Timed out
        await status_msg.edit_text(
            "Timed out waiting for project to complete.\n"
            "The project is still processing. Try /download again later.",
        )

    return {
        "download_command": download_command,
    }


async def _download_and_send_files(
    update: Update,
    api_key: str,
    project: Project,
    verify_client: VerifyClient,
) -> None:
    """Download all translated files from a completed project and send them to the user."""
    if not update.effective_message:
        return

    target_files_to_download: list[tuple[str, str, str]] = []

    for source_file in project.source_files:  # type: ignore[attr-defined]
        if not source_file.target_files:
            continue
        for target_file in source_file.target_files:
            target_files_to_download.append((
                target_file.target_file_uuid,
                source_file.filename,
                target_file.language_uuid,
            ))

    if not target_files_to_download:
        await update.effective_message.reply_text(
            "No translated files found in this project."
        )
        return

    sent_count = 0
    with tempfile.TemporaryDirectory(prefix="verify_dl_") as temp_dir:
        for file_uuid, original_name, lang_uuid in target_files_to_download:
            try:
                file_bytes = await verify_client.download_file(api_key, file_uuid)

                stem = Path(original_name).stem
                suffix = Path(original_name).suffix
                download_name = f"{stem}_{lang_uuid[:8]}{suffix}"
                local_path = Path(temp_dir) / download_name

                local_path.write_bytes(file_bytes)

                await update.effective_message.reply_document(
                    document=local_path,
                    filename=download_name,
                    caption=f"Translated file: {download_name}",
                )
                sent_count += 1
            except VerifyAPIError as e:
                logger.error("Failed to download file %s: %s", file_uuid, e.detail)
                await update.effective_message.reply_text(
                    f"Failed to download file (UUID: <code>{file_uuid}</code>):\n"
                    f"{e.detail}",
                    parse_mode="HTML",
                )
            except Exception:
                logger.exception("Unexpected error downloading file %s", file_uuid)
                await update.effective_message.reply_text(
                    f"Error downloading file <code>{file_uuid}</code>.",
                    parse_mode="HTML",
                )

    await update.effective_message.reply_text(
        f"Download complete. Sent <b>{sent_count}</b> translated file(s).",
        parse_mode="HTML",
    )
