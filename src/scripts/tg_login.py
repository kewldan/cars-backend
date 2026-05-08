import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from settings import settings
from tg import make_client


def main() -> None:
    if not settings.TG_API_ID or not settings.TG_API_HASH:
        raise SystemExit(
            "TG_API_ID and TG_API_HASH must be set in .env (get them at https://my.telegram.org)"
        )
    with make_client() as app:
        me = app.get_me()
        print(f"Signed in as {me.first_name} (@{me.username}) id={me.id}")
        print(
            f"Session saved to {settings.TG_SESSION_DIR}/{settings.TG_SESSION_NAME}.session"
        )


if __name__ == "__main__":
    main()
