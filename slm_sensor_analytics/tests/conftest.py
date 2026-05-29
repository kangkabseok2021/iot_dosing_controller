import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.session import get_db
from app.main import app
from app.services.anomaly import ModelStore

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_TestSessionLocal = async_sessionmaker(
    bind=_test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(autouse=True)
async def setup_db():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def override_dependencies(tmp_path):
    async def _get_test_db():
        async with _TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    app.state.model_store = ModelStore(str(tmp_path / "models"))
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client(override_dependencies):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
async def db_session():
    async with _TestSessionLocal() as session:
        yield session
