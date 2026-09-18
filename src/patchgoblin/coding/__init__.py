"""PatchGoblin coding package — repository-aware code modification."""

from patchgoblin.coding.agent import MAX_EDIT_ITERATIONS, CodingAgent, CodingAgentError
from patchgoblin.coding.editor import EditError, FileEditor
from patchgoblin.coding.models import ChangeResult, CodeChangePlan, EditOperation, FileEdit

__all__ = [
    "CodingAgent",
    "CodingAgentError",
    "MAX_EDIT_ITERATIONS",
    "EditError",
    "FileEditor",
    "ChangeResult",
    "CodeChangePlan",
    "EditOperation",
    "FileEdit",
]
