"""
Telegram bot interface for the agent system.

This is the human operator's command center. It provides:
1. Command interface (/status, /kill, /queue, /tweet, etc.)
2. Approval UI (inline keyboards for approve/reject/edit)
3. Alert delivery (high-severity events)
4. Daily reports

Requires: TELEGRAM_BOT_TOKEN and TELEGRAM_OPERATOR_CHAT_ID in env.
"""

import json
import logging
import os
from typing import Any

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

from core.approval_queue import ApprovalQueue
from core.kill_switch import KillSwitch
from core.token_budget import TokenBudgetManager
from core.audit_log import AuditLog

logger = logging.getLogger(__name__)


class TelegramBot:

    def __init__(self,
                 approval_queue: ApprovalQueue,
                 kill_switch: KillSwitch,
                 token_budget: TokenBudgetManager,
                 audit_log: AuditLog,
                 on_command: Any = None):
        """
        Args:
            on_command: Async callback(command: str, args: str) -> str
                        Called when operator sends a command the bot doesn't
                        handle directly (passed to agent engine).
        """
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.operator_id = int(os.environ.get("TELEGRAM_OPERATOR_CHAT_ID", "0"))
        self.queue = approval_queue
        self.kill = kill_switch
        self.budget = token_budget
        self.audit = audit_log
        self.on_command = on_command
        self.app: Application | None = None

    def _is_operator(self, update: Update) -> bool:
        """Only respond to the operator."""
        return update.effective_user and update.effective_user.id == self.operator_id

    async def start(self):
        """Start the Telegram bot."""
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN not set")
            return

        self.app = (
            Application.builder()
            .token(self.token)
            .build()
        )

        # Register commands
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("kill", self.cmd_kill))
        self.app.add_handler(CommandHandler("revive", self.cmd_revive))
        self.app.add_handler(CommandHandler("queue", self.cmd_queue))
        self.app.add_handler(CommandHandler("cost", self.cmd_cost))
        self.app.add_handler(CommandHandler("tweet", self.cmd_tweet))
        self.app.add_handler(CommandHandler("help", self.cmd_help))

        # Approval callbacks
        self.app.add_handler(CallbackQueryHandler(
            self.handle_approval_callback, pattern=r"^(approve|reject|edit)_"
        ))

        # Catch-all for agent commands
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.handle_message
        ))

        # Set bot commands menu
        await self.app.bot.set_my_commands([
            BotCommand("status", "System status"),
            BotCommand("kill", "Emergency shutdown"),
            BotCommand("revive", "Restart after kill"),
            BotCommand("queue", "Show pending approvals"),
            BotCommand("cost", "Today's token costs"),
            BotCommand("tweet", "Draft a tweet as David Flip"),
            BotCommand("help", "Show all commands"),
        ])

        logger.info("Telegram bot started")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

    async def stop(self):
        """Stop the Telegram bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    # --- Commands ---

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_operator(update):
            return
        await update.message.reply_text(
            "Clawdbot Agent System online.\n"
            f"Operator verified: {update.effective_user.id}\n\n"
            "Use /help for commands."
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_operator(update):
            return
        await update.message.reply_text(
            "**Clawdbot Commands**\n\n"
            "/status - System status\n"
            "/kill - EMERGENCY SHUTDOWN\n"
            "/revive - Restart after kill\n"
            "/queue - Show pending approvals\n"
            "/cost - Today's token costs\n"
            "/tweet <text> - Draft a tweet as David Flip\n"
            "/help - This message\n\n"
            "Or just type a message to talk to the agent.",
            parse_mode="Markdown"
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_operator(update):
            return

        kill_status = "KILLED" if self.kill.is_active else "RUNNING"
        pending = len(self.queue.get_pending())
        daily_spend = self.budget.get_daily_spend("david-flip")
        daily_limit = self.budget.get_daily_limit("david-flip")

        text = (
            f"**System Status**\n\n"
            f"State: {kill_status}\n"
            f"Pending approvals: {pending}\n"
            f"Today's cost: ${daily_spend:.4f} / ${daily_limit:.2f}\n"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def cmd_kill(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_operator(update):
            return
        reason = " ".join(context.args) if context.args else "Manual kill via Telegram"
        self.kill.activate(reason)
        self.audit.log("master", "critical", "kill_switch",
                       f"Kill switch activated: {reason}")
        await update.message.reply_text(
            "KILL SWITCH ACTIVATED.\nAll agent activity stopped.\n\n"
            f"Reason: {reason}\n"
            "Use /revive to restart."
        )

    async def cmd_revive(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_operator(update):
            return
        self.kill.deactivate()
        self.audit.log("master", "info", "kill_switch", "Kill switch deactivated")
        await update.message.reply_text("System revived. Agents can resume.")

    async def cmd_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_operator(update):
            return
        pending = self.queue.get_pending()
        if not pending:
            await update.message.reply_text("No pending approvals.")
            return

        for item in pending[:10]:
            await self._send_approval_card(update.effective_chat.id, item)

    async def cmd_cost(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_operator(update):
            return
        report = self.budget.get_daily_report("david-flip")
        text = (
            f"**Cost Report - {report['date']}**\n\n"
            f"Total: ${report['total_cost']:.4f}\n"
            f"Limit: ${report['daily_limit']:.2f}\n"
            f"Remaining: ${report['remaining']:.4f}\n"
        )
        if report["by_model"]:
            text += "\n**By Model:**\n"
            for m in report["by_model"]:
                text += f"  {m['model']}: ${m['total_cost']:.4f} ({m['call_count']} calls)\n"
        await update.message.reply_text(text, parse_mode="Markdown")

    async def cmd_tweet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_operator(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /tweet <text>")
            return

        tweet_text = " ".join(context.args)

        # Submit to approval queue
        approval_id = self.queue.submit(
            project_id="david-flip",
            agent_id="operator-direct",
            action_type="tweet",
            action_data={"text": tweet_text},
            context_summary="Direct tweet from operator",
        )

        approval = self.queue.get_by_id(approval_id)
        await self._send_approval_card(update.effective_chat.id, approval)

    async def handle_message(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        """Handle non-command messages (pass to agent engine)."""
        if not self._is_operator(update):
            return
        if self.on_command:
            response = await self.on_command("message", update.message.text)
            await update.message.reply_text(response)
        else:
            await update.message.reply_text(
                "Agent engine not connected. Use /help for commands."
            )

    # --- Approval UI ---

    async def _send_approval_card(self, chat_id: int, approval: dict):
        """Send an approval card with inline buttons."""
        preview = self.queue.format_preview(approval)

        text = (
            f"**Approval #{approval['id']}**\n\n"
            f"Agent: {approval['agent_id']}\n"
            f"Type: {approval['action_type']}\n"
            f"Cost: ${approval['cost_estimate']:.4f}\n\n"
            f"{preview}\n\n"
            f"Context: {approval['context_summary'][:200]}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "Approve", callback_data=f"approve_{approval['id']}"
                ),
                InlineKeyboardButton(
                    "Reject", callback_data=f"reject_{approval['id']}"
                ),
            ],
        ])

        await self.app.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    async def handle_approval_callback(self, update: Update,
                                       context: ContextTypes.DEFAULT_TYPE):
        """Handle approve/reject button clicks."""
        query = update.callback_query
        await query.answer()

        if not self._is_operator(update):
            return

        data = query.data
        action, approval_id_str = data.split("_", 1)
        approval_id = int(approval_id_str)

        if action == "approve":
            result = self.queue.approve(approval_id)
            self.audit.log(
                result.get("project_id", "unknown"), "info", "approval",
                f"Approved #{approval_id}"
            )
            await query.edit_message_text(
                f"APPROVED #{approval_id}\n\n"
                f"{query.message.text}\n\n"
                "Executing..."
            )
            # Trigger execution of approved action
            await self._execute_approved(approval_id)

        elif action == "reject":
            self.queue.reject(approval_id)
            self.audit.log(
                "david-flip", "info", "approval",
                f"Rejected #{approval_id}"
            )
            await query.edit_message_text(
                f"REJECTED #{approval_id}\n\n"
                f"{query.message.text}"
            )

    async def _execute_approved(self, approval_id: int):
        """Execute an approved action."""
        approval = self.queue.get_by_id(approval_id)
        if not approval:
            return

        action_type = approval["action_type"]
        action_data = json.loads(approval["action_data"])

        # Route to appropriate tool executor
        # (This will be connected to actual tool implementations)
        try:
            if self.on_command:
                result = await self.on_command(
                    f"execute_{action_type}", json.dumps(action_data)
                )
                self.queue.mark_executed(approval_id)
                await self.app.bot.send_message(
                    chat_id=self.operator_id,
                    text=f"Executed #{approval_id}: {result}",
                )
            else:
                await self.app.bot.send_message(
                    chat_id=self.operator_id,
                    text=f"#{approval_id} approved but no executor connected.",
                )
        except Exception as e:
            self.audit.log(
                approval.get("project_id", "unknown"), "reject",
                "execution", f"Failed to execute #{approval_id}: {e}",
                success=False
            )
            await self.app.bot.send_message(
                chat_id=self.operator_id,
                text=f"EXECUTION FAILED #{approval_id}: {e}",
            )

    # --- Alert delivery ---

    async def send_alert(self, text: str):
        """Send an alert to the operator."""
        if self.app and self.operator_id:
            await self.app.bot.send_message(
                chat_id=self.operator_id,
                text=f"ALERT\n\n{text}",
            )

    async def send_report(self, text: str):
        """Send a report to the operator."""
        if self.app and self.operator_id:
            await self.app.bot.send_message(
                chat_id=self.operator_id,
                text=text,
                parse_mode="Markdown",
            )
