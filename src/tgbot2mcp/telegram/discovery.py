"""
DFS-based bot discovery — explore a Telegram bot's state space.

Adapted from BotFuzzer's approach (seniorsolt/BotFuzzer), but using
Telethon via our TelegramAdapter instead of Pyrogram.

Performs a depth-first traversal of the bot's interaction graph:
1. Send /start, collect response + buttons
2. Send /help, collect response + buttons
3. For each discovered button/command, perform the action and recurse
4. Build a state graph of all discovered states and transitions
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

from tgbot2mcp.config import AppConfig
from tgbot2mcp.models import (
    BotInteractionResult,
    ButtonKind,
    DiscoveredBot,
    DiscoveredButton,
    DiscoveredCommand,
    DiscoveredState,
)
from tgbot2mcp.telegram.adapter import TelegramAdapter
from tgbot2mcp.utils import extract_commands_from_text, extract_text_from_message

logger = logging.getLogger("tgbot2mcp.telegram.discovery")


class BotDiscovery:
    """
    Explore a Telegram bot's capabilities using DFS traversal.

    Builds a state/action graph similar to BotFuzzer, but using
    Telethon through our adapter layer.
    """

    def __init__(
        self,
        adapter: TelegramAdapter,
        config: AppConfig,
        bot_username: str,
        max_depth: int | None = None,
        max_repeats: int | None = None,
    ) -> None:
        self.adapter = adapter
        self.config = config
        self.bot_username = bot_username
        self.max_depth = max_depth or config.discovery_max_depth
        self.max_repeats = max_repeats or config.discovery_max_repeats

        self._states: dict[int, DiscoveredState] = {}
        self._transitions: list[tuple[int, str, int]] = []
        self._all_commands: dict[str, DiscoveredCommand] = {}
        self._all_buttons: list[DiscoveredButton] = []
        self._state_counter = 0
        self._visited_signatures: set[str] = set()

    def _next_state_id(self) -> int:
        self._state_counter += 1
        return self._state_counter

    def _state_signature(self, result: BotInteractionResult) -> str:
        """
        Create a hashable signature for a state to detect duplicates.

        Based on the text content and available buttons, similar to
        BotFuzzer's StateNode.__eq__ approach.
        """
        texts = sorted(m.get("text", "") for m in result.messages)
        button_texts = sorted(b.text for b in result.buttons)
        return f"texts={texts}|buttons={button_texts}"

    def _result_to_state(
        self,
        result: BotInteractionResult,
        depth: int,
    ) -> DiscoveredState:
        """Convert an interaction result to a DiscoveredState."""
        text_parts = [m.get("text", "") for m in result.messages]
        full_text = "\n".join(text_parts)

        state_id = self._next_state_id()
        state = DiscoveredState(
            state_id=state_id,
            text=full_text[:2000],  # Truncate very long responses
            buttons=result.buttons,
            status="timeout" if result.timed_out else ("error" if result.error else "ok"),
            outgoing_actions=[],
        )

        # Build outgoing actions list
        for btn in result.buttons:
            if btn.kind == ButtonKind.INLINE:
                state.outgoing_actions.append(f"click_button('{btn.text}')")
            else:
                state.outgoing_actions.append(f"send('{btn.text}')")

        # Extract commands from response text
        for cmd in extract_commands_from_text(full_text):
            if cmd not in self._all_commands:
                self._all_commands[cmd] = DiscoveredCommand(
                    command=cmd, source="start_text"
                )

        return state

    async def _perform_action(
        self,
        action_desc: str,
        timeout: float | None = None,
    ) -> BotInteractionResult:
        """
        Perform a single action (send text or click button).

        action_desc format:
          - "send('/start')" or "send('Some button text')"
          - "click_button('Button Text', msg_id=42)"
        """
        if action_desc.startswith("send("):
            text = action_desc[5:-2]  # Extract text from send('...')
            text = text.strip("'\"")
            return await self.adapter.send_message(
                self.bot_username, text, timeout=timeout
            )
        elif action_desc.startswith("click_button("):
            # Parse button click
            # Format: click_button('text', msg_id=N)
            import re

            match = re.match(
                r"click_button\('(.+?)'(?:,\s*msg_id=(\d+))?\)", action_desc
            )
            if match:
                btn_text = match.group(1)
                msg_id = int(match.group(2)) if match.group(2) else None
                return await self.adapter.click_button(
                    self.bot_username,
                    message_id=msg_id or 0,
                    button_text=btn_text,
                    timeout=timeout,
                )
        return BotInteractionResult(error=f"Unknown action: {action_desc}")

    async def discover(self) -> DiscoveredBot:
        """
        Run the full DFS discovery process.

        Returns a DiscoveredBot with all states, commands, buttons, and transitions.
        """
        logger.info(f"Starting discovery of {self.bot_username} (max_depth={self.max_depth})")

        # Step 1: Get registered commands from bot profile
        await self._discover_commands_from_profile()

        # Step 2: Send /start and explore
        start_result = await self.adapter.send_command(
            self.bot_username, "start", timeout=self.config.default_timeout
        )
        start_state = self._result_to_state(start_result, depth=0)
        start_text = start_state.text
        self._states[start_state.state_id] = start_state

        # Step 3: Send /help and explore
        help_result = await self.adapter.send_command(
            self.bot_username, "help", timeout=self.config.default_timeout
        )
        help_state = self._result_to_state(help_result, depth=0)
        help_text = help_state.text
        if help_state.state_id != start_state.state_id:
            self._states[help_state.state_id] = help_state

        # Extract commands from /help text
        for cmd in extract_commands_from_text(help_text):
            if cmd not in self._all_commands:
                self._all_commands[cmd] = DiscoveredCommand(
                    command=cmd, source="help_text"
                )

        # Step 4: DFS from /start state
        await self._dfs_explore(start_state, depth=0, path=[])

        # Collect all unique buttons
        seen_buttons: set[str] = set()
        for state in self._states.values():
            for btn in state.buttons:
                btn_key = f"{btn.kind}:{btn.text}"
                if btn_key not in seen_buttons:
                    seen_buttons.add(btn_key)
                    self._all_buttons.append(btn)

        # Build final result
        bot = DiscoveredBot(
            username=self.bot_username,
            commands=list(self._all_commands.values()),
            buttons=self._all_buttons,
            states=list(self._states.values()),
            start_text=start_text,
            help_text=help_text,
            transitions=self._transitions,
        )

        logger.info(
            f"Discovery complete: {len(bot.commands)} commands, "
            f"{len(bot.buttons)} buttons, {len(bot.states)} states"
        )
        return bot

    async def _discover_commands_from_profile(self) -> None:
        """Fetch bot commands from the Telegram API (BotFather-registered commands)."""
        try:
            commands = await self.adapter.get_bot_commands(self.bot_username)
            for cmd in commands:
                self._all_commands[cmd.command] = DiscoveredCommand(
                    command=cmd.command,
                    description=cmd.description,
                    source="profile",
                )
            logger.info(f"Found {len(commands)} registered commands from profile")
        except Exception as e:
            logger.warning(f"Could not fetch profile commands: {e}")

    async def _dfs_explore(
        self,
        state: DiscoveredState,
        depth: int,
        path: list[int],
    ) -> None:
        """
        DFS exploration of the bot's state space.

        Similar to BotFuzzer's Tester.test() method but adapted for our adapter.
        """
        if depth >= self.max_depth:
            logger.debug(f"Max depth {self.max_depth} reached at state {state.state_id}")
            return

        # Check for loops
        repeat_count = path.count(state.state_id)
        if repeat_count >= self.max_repeats:
            logger.debug(f"State {state.state_id} repeated {repeat_count} times, skipping")
            return

        new_path = path + [state.state_id]

        for action in state.outgoing_actions:
            logger.debug(
                f"[depth={depth}] State {state.state_id}: trying action '{action}'"
            )

            try:
                result = await self._perform_action(
                    action, timeout=self.config.default_timeout
                )

                if result.timed_out or result.error:
                    logger.debug(f"Action '{action}' resulted in timeout/error")
                    continue

                new_state = self._result_to_state(result, depth + 1)

                # Check for duplicate states (same signature = same state)
                sig = self._state_signature(result)
                if sig in self._visited_signatures:
                    logger.debug(f"Duplicate state detected, skipping")
                    continue
                self._visited_signatures.add(sig)

                self._states[new_state.state_id] = new_state
                self._transitions.append((state.state_id, action, new_state.state_id))

                # Recurse
                await self._dfs_explore(new_state, depth + 1, new_path)

            except Exception as e:
                logger.warning(f"Error during DFS action '{action}': {e}")
                continue
