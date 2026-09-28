"""
memory.py
---------
LangChain-backed conversation memory.

This file preserves your older function names:
- save_message()
- get_history()
- clear_history()

Internally it uses LangChain's InMemoryChatMessageHistory.
"""

from langchain_core.chat_history import InMemoryChatMessageHistory


_session_history = InMemoryChatMessageHistory()


def save_message(message: str):
    """
    Saves user message in LangChain memory.
    """
    if message:
        _session_history.add_user_message(str(message))


def save_ai_message(message: str):
    """
    Saves AI/system response in LangChain memory.
    """
    if message:
        _session_history.add_ai_message(str(message))


def get_history():
    """
    Returns conversation history as a list of dictionaries.
    This keeps it easy for Streamlit/FastAPI to display.
    """
    history = []

    for item in _session_history.messages:
        history.append(
            {
                "type": item.type,
                "content": item.content
            }
        )

    return history


def get_history_text():
    """
    Returns conversation history as plain text.
    This can be sent to the SQL prompt for contextual follow-up questions.
    """
    lines = []

    for item in _session_history.messages:
        role = "User" if item.type == "human" else "Assistant"
        lines.append(f"{role}: {item.content}")

    return "\n".join(lines)


def clear_history():
    """
    Clears in-memory conversation history.
    """
    _session_history.clear()
