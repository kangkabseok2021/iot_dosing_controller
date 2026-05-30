import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import RouteCache, get_cache
from app.auth.jwt import create_access_token
from app.db.base import Base, get_db
from app.db.models import Vehicle
from app.main import create_app

SQLITE_URL = "sqlite:///./test_fleet.db"


@pytest.fixture(autouse=True)
def db_tables():
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_tables):
    engine = db_tables
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _override_get_cache():
        return RouteCache(client=None)

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_cache] = _override_get_cache
    with TestClient(app) as c:
        yield c


@pytest.fixture
def vehicle(db_tables):
    engine = db_tables
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    v = Vehicle(plate="TEST-001", capacity_kg=1000.0)
    db.add(v)
    db.commit()
    db.refresh(v)
    vid = v.id
    db.close()
    return vid


@pytest.fixture
def dispatcher_token():
    return create_access_token(sub="dispatcher1", role="dispatcher")


@pytest.fixture
def viewer_token():
    return create_access_token(sub="viewer1", role="viewer")
