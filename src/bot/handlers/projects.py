import logging

from telegram import Update
from telegram.ext import ContextTypes

from ...session.store import SessionStore
from ...verify.client import VerifyAPIError, VerifyClient
from ...verify.models import STATUS_EMOJI

logger = logging.getLogger(__name__)

MAX_DISPLAY_PROJECTS = 10


def create_project_handlers(
    session_store: SessionStore,
    verify_client: VerifyClient,
) -> dict:
    """Create project listing handler functions with injected dependencies."""

    async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /projects -- list recent projects."""
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id
        api_key = session_store.get_api_key(user_id)
        if not api_key:
            await update.effective_message.reply_text(
                "You need to be logged in. Use /login first."
            )
            return

        try:
            projects = await verify_client.get_projects(api_key, page=1, page_size=MAX_DISPLAY_PROJECTS)
        except VerifyAPIError as e:
            logger.error("Failed to fetch projects for user %d: %s", user_id, e.detail)
            await update.effective_message.reply_text(
                "Failed to fetch projects. Please try again later."
            )
            return

        if not projects:
            await update.effective_message.reply_text("You have no projects yet.")
            return

        lines = ["<b>Your Recent Projects:</b>\n"]
        for project in projects:
            emoji = STATUS_EMOJI.get(project.status, "")
            title = project.title or "Untitled"
            date_str = project.created_at.strftime("%Y-%m-%d")
            file_count = len(project.source_files)
            lang_count = len(project.target_languages)
            lines.append(
                f"{emoji} <b>{title}</b>\n"
                f"   ID: <code>{project.uuid}</code>\n"
                f"   Status: {project.status.value} | {file_count} file(s) | {lang_count} lang(s)\n"
                f"   Created: {date_str}"
            )

        await update.effective_message.reply_text(
            "\n\n".join(lines),
            parse_mode="HTML",
        )

    async def project_detail_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /project <id> -- show project details."""
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
                "Usage: /project &lt;project_id&gt;",
                parse_mode="HTML",
            )
            return

        project_id = args[0].strip()

        try:
            project = await verify_client.get_project(api_key, project_id)
        except VerifyAPIError as e:
            logger.error("Failed to fetch project %s: %s", project_id, e.detail)
            await update.effective_message.reply_text(
                f"Could not find project <code>{project_id}</code>.",
                parse_mode="HTML",
            )
            return

        emoji = STATUS_EMOJI.get(project.status, "")
        lang_names = [lang.name for lang in project.target_languages]
        file_info_lines = []
        for sf in project.source_files:
            target_status = ""
            if sf.target_files:
                statuses = [tf.status for tf in sf.target_files]
                target_status = f" ({', '.join(set(statuses))})"
            file_info_lines.append(f"  - {sf.filename}{target_status}")

        detail = (
            f"{emoji} <b>{project.title or 'Untitled'}</b>\n\n"
            f"<b>ID:</b> <code>{project.uuid}</code>\n"
            f"<b>Status:</b> {project.status.value}\n"
            f"<b>Languages:</b> {', '.join(lang_names)}\n"
            f"<b>Created:</b> {project.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"<b>Modified:</b> {project.modified_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"<b>Files:</b>\n" + "\n".join(file_info_lines)
        )

        await update.effective_message.reply_text(detail, parse_mode="HTML")

    return {
        "projects_command": projects_command,
        "project_detail_command": project_detail_command,
    }
