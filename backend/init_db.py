import os

from sqlalchemy import create_engine, inspect

from models import Base


def get_sync_database_url() -> str:
    async_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://scraper:scraper@localhost:5432/ecom_scraper",
    )
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def main() -> None:
    engine = create_engine(get_sync_database_url())

    with engine.begin() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())

        if "jobs" not in tables:
            print("Bootstrapping schema with SQLAlchemy create_all()...")
            Base.metadata.create_all(bind=connection)
            print("DB_INIT_ACTION=bootstrap")
            return

        if "alembic_version" not in tables:
            print("Existing schema found without alembic_version.")
            print("DB_INIT_ACTION=stamp")
            return

        print("Alembic-managed schema detected.")
        print("DB_INIT_ACTION=upgrade")


if __name__ == "__main__":
    main()
