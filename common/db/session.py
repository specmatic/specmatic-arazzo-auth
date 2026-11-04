from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from common.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def create_schema() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session]:
    with Session(engine) as session:
        yield session
