"""
Tool call models.

Represents the append-only trace of tool calls made by the
investigation agent, forming the audit trail.
"""

from pydantic import BaseModel, Field
from datetime import datetime


class ToolCall(BaseModel):
    """A record of a single tool invocation by the agent."""

    tool_name: str = Field(..., description="Name of the tool that was called")
    arguments: dict = Field(default_factory=dict, description="Arguments passed to the tool")
    rationale: str = Field(..., description="Agent's reasoning for choosing this tool")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO timestamp of when the call was made",
    )


class ToolResult(BaseModel):
    """Result returned by a tool execution."""

    tool_name: str
    success: bool = True
    result: dict = Field(default_factory=dict, description="Structured result from the tool")
    error: str | None = None


class ToolCallRecord(BaseModel):
    """Combined record of a tool call and its result — one entry in the trace."""

    call: ToolCall
    result: ToolResult
