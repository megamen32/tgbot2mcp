"""Telethon session management — login, connect, disconnect."""

from __future__ import annotations

import logging
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import User

from tgbot2mcp.config import AppConfig

logger = logging.getLogger("tgbot2mcp.telegram.client")


class TelegramSessionManager:
    """Manages a Telethon user session for interacting with Telegram bots."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._client: TelegramClient | None = None
        self._me: User | None = None

    @property
    def client(self) -> TelegramClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Call login() or connect() first.")
        return self._client

    def _session_path(self) -> str:
        """Return the session file path (without .session extension)."""
        return str(self.config.session_dir / "tgbot2mcp")

    def _create_client(self) -> TelegramClient:
        """Create a new TelegramClient instance."""
        if not self.config.api_id or not self.config.api_hash:
            raise ValueError(
                "api_id and api_hash are required. "
                "Set them via config.yaml or TG_API_ID/TG_API_HASH env vars."
            )
        return TelegramClient(
            session=self._session_path(),
            api_id=self.config.api_id,
            api_hash=self.config.api_hash,
        )

    async def login(self) -> User:
        """
        Interactive login — prompts for phone number / code / 2FA password.

        Persists the session file for future reuse.
        """
        self._client = self._create_client()
        await self._client.connect()

        if await self._client.is_user_authorized():
            self._me = await self._client.get_me()
            logger.info(f"Already authorized as {self._me.first_name} (@{self._me.username})")
            return self._me

        # Interactive authentication
        phone = input("Enter your phone number (with country code, e.g. +1234567890): ")
        await self._client.send_code_request(phone)

        code = input("Enter the verification code sent to your Telegram app: ")
        try:
            await self._client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            password = input("Enter your 2FA password: ")
            await self._client.sign_in(password=password)

        self._me = await self._client.get_me()
        logger.info(f"Logged in as {self._me.first_name} (@{self._me.username})")

        # Secure session file permissions
        session_file = Path(f"{self._session_path()}.session")
        if session_file.exists():
            session_file.chmod(0o600)

        return self._me

    async def connect(self) -> User:
        """Connect using an existing session (no interactive prompts)."""
        self._client = self._create_client()
        await self._client.connect()

        if not await self._client.is_user_authorized():
            raise RuntimeError(
                "No valid session found. Run 'tgbot2mcp login' first."
            )

        self._me = await self._client.get_me()
        logger.info(f"Connected as {self._me.first_name} (@{self._me.username})")
        return self._me

    async def disconnect(self) -> None:
        """Disconnect the client."""
        if self._client and self._client.is_connected():
            await self._client.disconnect()
            logger.info("Disconnected.")
        self._client = None
        self._me = None

    @property
    def me(self) -> User | None:
        return self._me
