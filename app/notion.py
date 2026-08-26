"""Notion REST API bilan ishlash (async, httpx)."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app import config

logger = logging.getLogger("notion")

API = "https://api.notion.com/v1"


@dataclass
class Task:
    """Notion'dagi bitta zadacha (kerakli maydonlari ajratib olingan)."""

    page_id: str
    url: str
    title: str
    status: str
    start: dt.date | None
    deadline: dt.date | None
    assignees: list[str]
    owners: list[str]
    note: str
    created: dt.datetime
    edited: dt.datetime
    has_subtasks: bool
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def short(self) -> str:
        return self.title or "(nomsiz zadacha)"

    @property
    def effective_deadline(self) -> dt.date | None:
        """Deadline bo'lmasa, boshlanish sanasi deadline o'rnida ishlatiladi."""
        return self.deadline or self.start


def _plain(rich: list[dict] | None) -> str:
    if not rich:
        return ""
    return "".join(part.get("plain_text", "") for part in rich).strip()


def _date(prop: dict | None) -> dt.date | None:
    if not prop:
        return None
    value = prop.get("date")
    if not value or not value.get("start"):
        return None
    return dt.date.fromisoformat(value["start"][:10])


def _people(prop: dict | None, names: dict[str, str]) -> list[str]:
    if not prop:
        return []
    out = []
    for person in prop.get("people", []):
        pid = person.get("id", "")
        out.append(person.get("name") or names.get(pid) or pid[:8])
    return out


class NotionClient:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=API,
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {config.NOTION_TOKEN}",
                "Notion-Version": config.NOTION_VERSION,
                "Content-Type": "application/json",
            },
        )
        self._user_names: dict[str, str] = {}

    async def close(self) -> None:
        await self._http.aclose()

    # --- foydalanuvchilar ---------------------------------------------------
    async def load_users(self) -> dict[str, str]:
        """Notion workspace foydalanuvchilari: id -> ism."""
        if self._user_names:
            return self._user_names
        cursor = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            resp = await self._http.get("/users", params=params)
            resp.raise_for_status()
            data = resp.json()
            for user in data.get("results", []):
                if user.get("type") == "person":
                    self._user_names[user["id"]] = user.get("name") or "?"
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        logger.info("Notion foydalanuvchilari yuklandi: %d ta", len(self._user_names))
        return self._user_names

    # --- zadachalarni o'qish ------------------------------------------------
    async def fetch_active_tasks(self) -> list[Task]:
        """Statusi План / Стрт / Аудт bo'lgan barcha zadachalar."""
        names = await self.load_users()
        payload: dict[str, Any] = {
            "filter": {
                "or": [
                    {"property": config.P_STATUS, "status": {"equals": s}}
                    for s in config.ACTIVE_STATUSES
                ]
            },
            "page_size": 100,
        }
        tasks: list[Task] = []
        cursor = None
        while True:
            body = dict(payload)
            if cursor:
                body["start_cursor"] = cursor
            resp = await self._http.post(
                f"/databases/{config.NOTION_DATABASE_ID}/query", json=body
            )
            if resp.status_code >= 400:
                logger.error("Notion query xato %s: %s", resp.status_code, resp.text)
                resp.raise_for_status()
            data = resp.json()
            for page in data.get("results", []):
                tasks.append(self._parse(page, names))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        logger.info("Notion'dan %d ta aktiv zadacha olindi", len(tasks))
        return tasks

    async def fetch_task(self, page_id: str) -> Task:
        names = await self.load_users()
        resp = await self._http.get(f"/pages/{page_id}")
        resp.raise_for_status()
        return self._parse(resp.json(), names)

    def _parse(self, page: dict, names: dict[str, str]) -> Task:
        props = page.get("properties", {})
        status_prop = props.get(config.P_STATUS) or {}
        status = (status_prop.get("status") or {}).get("name") or ""
        subtask = props.get(config.P_SUBTASK) or {}
        return Task(
            page_id=page["id"],
            url=page.get("url", ""),
            title=_plain((props.get(config.P_TITLE) or {}).get("title")),
            status=status,
            start=_date(props.get(config.P_DATE)),
            deadline=_date(props.get(config.P_DEADLINE)),
            assignees=_people(props.get(config.P_ASSIGNEE), names),
            owners=_people(props.get(config.P_OWNER), names),
            note=_plain((props.get(config.P_NOTE) or {}).get("rich_text")),
            created=dt.datetime.fromisoformat(
                page["created_time"].replace("Z", "+00:00")
            ),
            edited=dt.datetime.fromisoformat(
                page["last_edited_time"].replace("Z", "+00:00")
            ),
            has_subtasks=bool(subtask.get("relation")),
            raw=page,
        )

    # --- yozish -------------------------------------------------------------
    async def add_comment(self, page_id: str, text: str) -> bool:
        """Zadacha sahifasiga komentariya qo'shadi."""
        if not config.WRITE_TO_NOTION:
            logger.info("WRITE_TO_NOTION=false, komentariya yozilmadi")
            return False
        resp = await self._http.post(
            "/comments",
            json={
                "parent": {"page_id": page_id},
                "rich_text": [{"text": {"content": text[:1900]}}],
            },
        )
        if resp.status_code >= 400:
            logger.error("Komentariya yozilmadi %s: %s", resp.status_code, resp.text)
            return False
        return True

    async def update_title(self, page_id: str, title: str) -> bool:
        resp = await self._http.patch(
            f"/pages/{page_id}",
            json={
                "properties": {
                    config.P_TITLE: {"title": [{"text": {"content": title[:1900]}}]}
                }
            },
        )
        if resp.status_code >= 400:
            logger.error("Nom yangilanmadi %s: %s", resp.status_code, resp.text)
            return False
        return True

    async def update_props(self, page_id: str, props: dict) -> bool:
        resp = await self._http.patch(f"/pages/{page_id}", json={"properties": props})
        if resp.status_code >= 400:
            logger.error("Yangilash xato %s: %s", resp.status_code, resp.text)
            return False
        return True

    async def create_task(
        self,
        title: str,
        start: dt.date | None = None,
        deadline: dt.date | None = None,
        note: str = "",
    ) -> str | None:
        """Yangi zadacha yaratadi, sahifa URL'ini qaytaradi."""
        props: dict[str, Any] = {
            config.P_TITLE: {"title": [{"text": {"content": title[:1900]}}]},
            config.P_STATUS: {"status": {"name": config.STATUS_TODO}},
        }
        if start:
            props[config.P_DATE] = {"date": {"start": start.isoformat()}}
        if deadline:
            props[config.P_DEADLINE] = {"date": {"start": deadline.isoformat()}}
        if note:
            props[config.P_NOTE] = {"rich_text": [{"text": {"content": note[:1900]}}]}
        resp = await self._http.post(
            "/pages",
            json={
                "parent": {"database_id": config.NOTION_DATABASE_ID},
                "properties": props,
            },
        )
        if resp.status_code >= 400:
            logger.error("Zadacha yaratilmadi %s: %s", resp.status_code, resp.text)
            return None
        return resp.json().get("url")
