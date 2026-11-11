import pytest

from backend.db import connect, init_db


@pytest.fixture
def conn():
    conn = connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()
