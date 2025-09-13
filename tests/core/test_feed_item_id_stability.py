import tempfile
import os
import pytest
from app.models import init_db, get_db, FeedModel, FeedItemModel

@pytest.fixture
def temp_db():
    import app.models as models
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_db = tmp.name
    original_db = models.DB_PATH
    models.DB_PATH = tmp_db
    init_db()
    yield tmp_db
    models.DB_PATH = original_db
    if os.path.exists(tmp_db):
        os.unlink(tmp_db)


def test_item_id_stable_on_update(temp_db):
    feed_id = FeedModel.create_feed("https://example.com", "Example")
    first_id = FeedItemModel.create_item(feed_id, "guid", "Title", "https://example.com/1")
    second_id = FeedItemModel.create_item(feed_id, "guid", "Updated Title", "https://example.com/1")
    assert first_id == second_id
    with get_db() as conn:
        row = conn.execute("SELECT title FROM feed_items WHERE id=?", (first_id,)).fetchone()
        assert row[0] == "Updated Title"
