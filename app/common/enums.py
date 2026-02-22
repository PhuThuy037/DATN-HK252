from enum import Enum

class UserStatus(str, Enum):
    active = "active"
    blocked = "blocked"


class CompanyStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class MemberRole(str, Enum):
    member = "member"
    company_admin = "company_admin"


class MemberStatus(str, Enum):
    active = "active"
    removed = "removed"


class RuleScope(str, Enum):
    prompt = "prompt"
    chat = "chat"
    file = "file"
    api = "api"


class RuleAction(str, Enum):
    allow = "allow"
    mask = "mask"
    block = "block"
    warn = "warn"


class RuleSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RagMode(str, Enum):
    off = "off"
    explain = "explain"
    verify = "verify"


class ConversationStatus(str, Enum):
    active = "active"
    archived = "archived"


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class MessageInputType(str, Enum):
    user_input = "user_input"
    system_prompt = "system_prompt"
    tool_result = "tool_result"


class ScanStatus(str, Enum):
    pending = "pending"
    done = "done"
    failed = "failed"


class EntitySource(str, Enum):
    regex = "regex"
    presidio = "presidio"
    llm = "llm"
