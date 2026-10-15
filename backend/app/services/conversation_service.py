"""Conversation service — persistent chat history with Task Passport scoping."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.conversation import AttachmentRow, ConversationRow, MessageRow
from app.schemas.conversation import (
    AttachmentRead,
    ConversationRead,
    MessageRead,
)
from app.services.audit_service import audit_service

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


def _ensure_upload_dir() -> None:
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def _conversation_to_read(row: ConversationRow) -> ConversationRead:
    return ConversationRead(
        id=row.id,
        task_id=row.task_id,
        user_id=row.user_id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _message_to_read(row: MessageRow) -> MessageRead:
    return MessageRead(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
        model=row.model,
        created_at=row.created_at,
    )


def _attachment_to_read(row: AttachmentRow) -> AttachmentRead:
    return AttachmentRead(
        id=row.id,
        message_id=row.message_id,
        conversation_id=row.conversation_id,
        task_id=row.task_id,
        filename=row.filename,
        content_type=row.content_type,
        file_size=row.file_size,
        created_at=row.created_at,
    )


class ConversationService:
    """Manages conversations and messages scoped to tasks and users."""

    def create_conversation(
        self,
        db: Session,
        *,
        task_id: str,
        user_id: str,
        title: str = "New Conversation",
    ) -> ConversationRead:
        now = datetime.now(timezone.utc)
        row = ConversationRow(
            id=str(uuid4()),
            task_id=task_id,
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        audit_service.record(
            event_type="chat_conversation_created",
            task_id=task_id,
            user_id=user_id,
            identity=user_id,
            role="",
            detail=f"Conversation created: {title}",
        )

        return _conversation_to_read(row)

    def get_conversation(self, db: Session, conversation_id: str, user_id: str) -> ConversationRead | None:
        row = db.get(ConversationRow, conversation_id)
        if row is None or row.user_id != user_id:
            return None
        return _conversation_to_read(row)

    def delete_conversation(self, db: Session, conversation_id: str, user_id: str) -> None:
        """Delete a conversation and all its messages. Only the owner can delete."""
        from app.models.conversation import MessageRow

        row = db.get(ConversationRow, conversation_id)
        if row is None or row.user_id != user_id:
            return

        db.query(MessageRow).filter(MessageRow.conversation_id == conversation_id).delete()
        db.delete(row)
        db.commit()

    def list_conversations_for_task(
        self, db: Session, task_id: str, user_id: str
    ) -> list[ConversationRead]:
        rows = (
            db.query(ConversationRow)
            .filter(
                ConversationRow.task_id == task_id,
                ConversationRow.user_id == user_id,
            )
            .order_by(ConversationRow.updated_at.desc())
            .all()
        )
        return [_conversation_to_read(r) for r in rows]

    def list_general_conversations(
        self, db: Session, user_id: str
    ) -> list[ConversationRead]:
        """List General Chat conversations (task_id empty) for a user."""
        rows = (
            db.query(ConversationRow)
            .filter(
                ConversationRow.task_id == "",
                ConversationRow.user_id == user_id,
            )
            .order_by(ConversationRow.updated_at.desc())
            .all()
        )
        return [_conversation_to_read(r) for r in rows]

    def add_message(
        self,
        db: Session,
        *,
        conversation_id: str,
        role: str,
        content: str,
        model: str | None = None,
    ) -> MessageRead:
        now = datetime.now(timezone.utc)
        row = MessageRow(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
            created_at=now,
        )
        db.add(row)

        conv = db.get(ConversationRow, conversation_id)
        if conv:
            conv.updated_at = now

        db.commit()
        db.refresh(row)

        return _message_to_read(row)

    def get_messages(
        self, db: Session, conversation_id: str
    ) -> list[MessageRead]:
        rows = (
            db.query(MessageRow)
            .filter(MessageRow.conversation_id == conversation_id)
            .order_by(MessageRow.created_at)
            .all()
        )
        return [_message_to_read(r) for r in rows]

    def add_attachment(
        self,
        db: Session,
        *,
        message_id: str,
        conversation_id: str,
        task_id: str,
        filename: str,
        content_type: str,
        file_size: int,
        storage_path: str,
    ) -> AttachmentRead:
        row = AttachmentRow(
            id=str(uuid4()),
            message_id=message_id,
            conversation_id=conversation_id,
            task_id=task_id,
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            storage_path=storage_path,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _attachment_to_read(row)

    def get_attachments_for_message(
        self, db: Session, message_id: str
    ) -> list[AttachmentRead]:
        rows = (
            db.query(AttachmentRow)
            .filter(AttachmentRow.message_id == message_id)
            .all()
        )
        return [_attachment_to_read(r) for r in rows]

    def get_attachments_for_conversation(
        self, db: Session, conversation_id: str
    ) -> list[AttachmentRead]:
        rows = (
            db.query(AttachmentRow)
            .filter(AttachmentRow.conversation_id == conversation_id)
            .order_by(AttachmentRow.created_at)
            .all()
        )
        return [_attachment_to_read(r) for r in rows]

    def record_chat_audit(
        self,
        *,
        event_type: str,
        task_id: str,
        user_id: str,
        role: str = "",
        detail: str = "",
    ) -> None:
        audit_service.record(
            event_type=event_type,
            task_id=task_id,
            user_id=user_id,
            identity=user_id,
            role=role,
            detail=detail,
        )


conversation_service = ConversationService()
