"""The one place that defines how a command is turned into model text (used by training AND serving)."""


def build_prompt(command: str) -> str:
    return f"Command: {command}\nJSON:"


def build_target(json_text: str) -> str:
    return " " + json_text
