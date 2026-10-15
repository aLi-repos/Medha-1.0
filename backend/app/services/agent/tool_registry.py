"""Tool Registry — all tools registered with capability metadata and risk levels."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ToolRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolDefinition:
    name: str
    description: str
    capabilities: list[str]
    risk: ToolRisk
    requires_approval: bool = False
    allowed_sensitivity_max: str = "restricted"


TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="document_reader",
        description="Read and extract text from ingested documents",
        capabilities=["read", "search", "extract"],
        risk=ToolRisk.LOW,
        requires_approval=False,
        allowed_sensitivity_max="restricted",
    ),
    ToolDefinition(
        name="docx_generator",
        description="Generate DOCX reports from analysis results",
        capabilities=["generate", "write", "export"],
        risk=ToolRisk.MEDIUM,
        requires_approval=False,
        allowed_sensitivity_max="restricted",
    ),
    ToolDefinition(
        name="data_analyzer",
        description="Perform statistical analysis on numerical data",
        capabilities=["analyze", "compute", "summarize"],
        risk=ToolRisk.LOW,
        requires_approval=False,
        allowed_sensitivity_max="restricted",
    ),
    ToolDefinition(
        name="email_sender",
        description="Send email notifications to stakeholders",
        capabilities=["send", "notify", "communicate"],
        risk=ToolRisk.HIGH,
        requires_approval=True,
        allowed_sensitivity_max="internal",
    ),
    ToolDefinition(
        name="api_caller",
        description="Make external API calls to third-party services",
        capabilities=["fetch", "post", "integrate"],
        risk=ToolRisk.HIGH,
        requires_approval=True,
        allowed_sensitivity_max="internal",
    ),
    ToolDefinition(
        name="code_executor",
        description="Execute Python code in a sandboxed environment",
        capabilities=["execute", "compute", "transform"],
        risk=ToolRisk.HIGH,
        requires_approval=True,
        allowed_sensitivity_max="internal",
    ),
    ToolDefinition(
        name="graph_generator",
        description="Generate charts and graphs from analysis data",
        capabilities=["visualize", "chart", "graph", "generate"],
        risk=ToolRisk.LOW,
        requires_approval=False,
        allowed_sensitivity_max="restricted",
    ),
    ToolDefinition(
        name="excel_generator",
        description="Generate Excel workbooks with multiple data sheets",
        capabilities=["generate", "write", "export", "spreadsheet"],
        risk=ToolRisk.MEDIUM,
        requires_approval=False,
        allowed_sensitivity_max="restricted",
    ),
    ToolDefinition(
        name="report_generator",
        description="Compile structured analysis reports from multiple data sources",
        capabilities=["generate", "compile", "format", "export"],
        risk=ToolRisk.MEDIUM,
        requires_approval=False,
        allowed_sensitivity_max="restricted",
    ),
]


class ToolRegistry:
    """Manages registered tools and their permission constraints."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        for t in TOOL_DEFINITIONS:
            self._tools[t.name] = t

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_all(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def is_tool_allowed(self, tool_name: str, allowed_tools: list[str]) -> bool:
        if not allowed_tools:
            return True
        return tool_name in allowed_tools

    def get_allowed_tools(self, allowed_tools: list[str]) -> list[ToolDefinition]:
        if not allowed_tools:
            return list(self._tools.values())
        return [t for t in self._tools.values() if t.name in allowed_tools]


tool_registry = ToolRegistry()
