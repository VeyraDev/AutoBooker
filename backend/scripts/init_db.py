"""创建/更新数据库表（开发环境）。"""

from app.database import Base, engine
import app.models  # noqa: F401


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Database tables ensured.")


if __name__ == "__main__":
    main()
