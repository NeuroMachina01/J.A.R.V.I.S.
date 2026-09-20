# agents/agent_registry.py
# Auto-discovers every agent in /agents/ at startup.
# Adding a new agent = drop the file. Nothing else.

import importlib
import inspect
import pkgutil
from pathlib import Path
from agents._base import BaseAgent
import logging

logger = logging.getLogger(__name__)


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def discover(self, package_path: str = "agents") -> None:
        """
        Scans the agents/ directory, imports every module,
        finds classes that inherit BaseAgent, instantiates them.
        """
        agents_dir = Path(package_path)

        for _, module_name, _ in pkgutil.iter_modules([str(agents_dir)]):
            if module_name.startswith("_"):
                continue  # skip _base.py, __init__.py

            try:
                module = importlib.import_module(f"{package_path}.{module_name}")

                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BaseAgent)
                        and obj is not BaseAgent
                        and hasattr(obj, "name")
                    ):
                        instance = obj()

                        if not instance.health_check():
                            logger.warning(f"Agent {obj.name} failed health check — skipping.")
                            continue

                        self._agents[instance.name] = instance
                        logger.info(f"Registered agent: {instance.name}")

            except Exception as e:
                logger.error(f"Failed to load agent from {module_name}: {e}")

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def all(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def routing_manifest(self) -> str:
        """
        Builds the routing prompt the LLM receives.
        Each agent's description is included — this IS the routing table.
        """
        lines = ["Available agents (name → when to use):"]
        for agent in self._agents.values():
            lines.append(f'- {agent.name}: {agent.description}')
        lines.append('- general: simple conversation, greetings, nothing else fits')
        return "\n".join(lines)

    def all_triggers(self) -> dict[str, list[str]]:
        """Returns {agent_name: [trigger_keywords]} for fast pre-routing."""
        return {
            agent.name: agent.triggers
            for agent in self._agents.values()
        }

    def __repr__(self):
        return f"<AgentRegistry agents={list(self._agents.keys())}>"
