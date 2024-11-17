import caddy_chatbot.src.boot  # noqa: F401

from caddy_core.services.router import load_semantic_router

if __name__ == "__main__":
    load_semantic_router()
