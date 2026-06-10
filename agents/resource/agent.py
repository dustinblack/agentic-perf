from __future__ import annotations

import logging
from typing import Any

from agents.base import AgentBase
from agents.benchmark.mcp_server import cleanup_controller_ssh_keys
from agents.provisioning.mcp_server import cleanup_harness
from providers.events import EventBus
from providers.llm.base import LLMProvider, LLMResponse
from providers.secrets.base import SecretsProvider
from providers.ssh import SSHExecutor

from .mcp_server import create_resource_tool_handlers, get_resource_tools
from .prompts import RESOURCE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ResourceAgent(AgentBase):
    def __init__(
        self,
        llm_provider: LLMProvider,
        state_store_url: str,
        mode: str = "create",
        secrets_provider: SecretsProvider | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._mode = mode
        self._hitl_triggered = False
        self._hitl_ticket_id: str | None = None
        self._secrets = secrets_provider

        tools = get_resource_tools() if mode == "create" else []
        tool_handlers = (
            create_resource_tool_handlers(
                secrets_provider=secrets_provider,
            )
            if mode == "create"
            else {}
        )

        super().__init__(
            agent_name="resource-agent",
            llm_provider=llm_provider,
            state_store_url=state_store_url,
            tools=tools,
            tool_handlers=tool_handlers,
            event_bus=event_bus,
        )

    async def _do_request_clarification(self, question: str) -> None:
        if self._hitl_ticket_id:
            self._hitl_triggered = True
            await self._request_human_input(self._hitl_ticket_id, question)

    async def run(self, ticket_id: str) -> None:
        if self._mode == "teardown":
            await self._run_teardown(ticket_id)
            return
        self._hitl_ticket_id = ticket_id
        self._hitl_triggered = False
        await super().run(ticket_id)

    async def _run_teardown(self, ticket_id: str) -> None:
        logger.info(f"[resource-agent] Teardown for ticket {ticket_id}")
        ticket = await self._get_ticket(ticket_id)
        fields = ticket.get("custom_fields", {})
        assignment_id = fields.get("quads_assignment_id")
        host_cleanup = fields.get("host_cleanup", "required")

        if host_cleanup == "required":
            await self._run_host_cleanup(ticket_id, fields)

        if assignment_id and self._secrets:
            try:
                from providers.quads import QuadsClient
                client = await QuadsClient.from_secrets(self._secrets)
                result = await client.terminate_assignment(int(assignment_id))
                await client.close()
                await self._add_comment(
                    ticket_id,
                    f"QUADS assignment {assignment_id} terminated.",
                )
                logger.info(f"[resource-agent] QUADS assignment {assignment_id} terminated")
            except Exception as e:
                logger.exception(f"[resource-agent] Failed to terminate QUADS assignment {assignment_id}")
                await self._add_comment(
                    ticket_id,
                    f"Failed to terminate QUADS assignment {assignment_id}: {e}",
                )
        else:
            await self._add_comment(ticket_id, "Resources released (no QUADS assignment to terminate).")

        await self._transition_ticket(
            ticket_id, "closed", comment="Resource teardown complete"
        )
        logger.info(f"[resource-agent] Teardown complete for {ticket_id}")

    async def _run_host_cleanup(self, ticket_id: str, fields: dict) -> None:
        hw = fields.get("assigned_hardware_ips", {})
        controller = hw.get("controller")
        targets = hw.get("targets", [])
        ssh_key_path = fields.get("ssh_key_path")
        harness_name = fields.get("harness_name")
        all_hosts = ([controller] if controller else []) + targets

        if not all_hosts:
            logger.info("[resource-agent] No hosts to clean up")
            return

        ssh = SSHExecutor(user="root", key_path=ssh_key_path)
        cleanup_summary = []

        # Remove controller-to-endpoint SSH keys (benchmark agent's responsibility)
        if controller and targets:
            try:
                result = await cleanup_controller_ssh_keys(ssh, controller, targets)
                cleanup_summary.append(f"Controller SSH keys: {result['status']}")
                logger.info(f"[resource-agent] Controller key cleanup: {result}")
            except Exception as e:
                cleanup_summary.append(f"Controller SSH keys: failed ({e})")
                logger.exception("[resource-agent] Controller key cleanup failed")

        # Uninstall harness (provisioning agent's responsibility)
        if harness_name:
            for host in all_hosts:
                try:
                    result = await cleanup_harness(ssh, host, harness_name)
                    cleanup_summary.append(f"Harness on {host}: {result['status']}")
                    logger.info(f"[resource-agent] Harness cleanup on {host}: {result}")
                except Exception as e:
                    cleanup_summary.append(f"Harness on {host}: failed ({e})")
                    logger.exception(f"[resource-agent] Harness cleanup on {host} failed")

        # Remove QUADS provisioning SSH keys (resource agent's responsibility)
        if fields.get("quads_assignment_id") and self._secrets:
            try:
                from providers.quads import QuadsClient
                client = await QuadsClient.from_secrets(self._secrets)
                result = await client.cleanup_ssh_keys(all_hosts)
                await client.close()
                cleanup_summary.append(f"QUADS SSH keys: {result['status']}")
                logger.info(f"[resource-agent] QUADS key cleanup: {result}")
            except Exception as e:
                cleanup_summary.append(f"QUADS SSH keys: failed ({e})")
                logger.exception("[resource-agent] QUADS key cleanup failed")

        if cleanup_summary:
            await self._add_comment(
                ticket_id,
                "**Host Cleanup**\n\n" + "\n".join(f"- {s}" for s in cleanup_summary),
            )

    def _system_prompt(self) -> str:
        return RESOURCE_SYSTEM_PROMPT

    def _build_messages(self, ticket: dict[str, Any]) -> list[dict[str, Any]]:
        content = (
            f"## Performance Test Request\n\n"
            f"**Summary:** {ticket['summary']}\n\n"
            f"**Description:**\n{ticket['description']}\n"
        )

        specs = ticket.get("custom_fields", {}).get("parsed_specs")
        if specs:
            content += f"\n## Parsed Specifications\n```json\n{specs}\n```\n"

        if ticket.get("comments"):
            content += "\n## Previous Comments\n"
            for comment in ticket["comments"]:
                content += f"\n**{comment['author']}:** {comment['body']}\n"

        return [{"role": "user", "content": content}]

    async def _handle_completion(
        self, ticket_id: str, response: LLMResponse
    ) -> None:
        if self._hitl_triggered:
            logger.info(f"[resource-agent] HITL triggered for {ticket_id}")
            return

        result = self._get_submit_result(response)
        if not result:
            result = self._parse_json_response(response.text)
        if not result:
            result = {
                "assigned_hardware_ips": {},
                "ssh_user": "root",
                "ssh_key_path": "~/.ssh/id_rsa",
                "notes": "Could not produce structured output",
            }

        fields = {
            "assigned_hardware_ips": result.get("assigned_hardware_ips", {}),
            "ssh_user": result.get("ssh_user", "root"),
            "ssh_key_path": result.get("ssh_key_path", "~/.ssh/id_rsa"),
            "lease_expiration": result.get("lease_expiration"),
        }
        if result.get("quads_assignment_id"):
            fields["quads_assignment_id"] = result["quads_assignment_id"]
        if result.get("quads_cloud_name"):
            fields["quads_cloud_name"] = result["quads_cloud_name"]
        if result.get("fresh_host"):
            fields["fresh_host"] = True
        await self._update_fields(ticket_id, fields)

        hw = fields["assigned_hardware_ips"]
        summary = (
            f"**Resource Allocation Complete**\n\n"
            f"- **Controller:** {hw.get('controller', 'N/A')}\n"
            f"- **Targets:** {', '.join(hw.get('targets', []))}\n"
            f"- **SSH User:** {fields['ssh_user']}\n"
        )
        if result.get("notes"):
            summary += f"- **Notes:** {result['notes']}\n"

        await self._add_comment(ticket_id, summary)
        await self._transition_ticket(
            ticket_id,
            "awaiting_provision",
            comment="Hardware validated, ready for provisioning",
        )
