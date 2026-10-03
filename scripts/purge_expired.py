"""Delete expired conversations. Run from cron or a scheduler, for example hourly.

    cd backend && python ../scripts/purge_expired.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.database.repository import ConversationRepository  # noqa: E402
from app.database.session import make_session_factory  # noqa: E402

if __name__ == "__main__":
    session = make_session_factory(get_settings())()
    try:
        removed = ConversationRepository(session).purge_expired()
        session.commit()
        print(f"purged {removed} expired conversation(s)")
    finally:
        session.close()
