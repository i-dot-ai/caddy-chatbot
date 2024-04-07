from typing import List


def format_chat_history(user_messages: List) -> List:
    """
    Formats chat messages for LangChain

    Args:
        user_messages (list): list of user messages

    Returns:
        history (list): langchain formatted
    """
    history_langchain_format = []
    for message in user_messages:
        human = message["llmPrompt"]
        ai = message["llmAnswer"]
        history_langchain_format.append((human, ai))
    return history_langchain_format
