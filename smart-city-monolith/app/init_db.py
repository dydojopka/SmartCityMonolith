from app import database
from app.modules.notification import models as notification_models
from app.modules.notification.seed import seed_database as seed_notifications
from app.modules.utility import models as utility_models
from app.modules.utility.seed import seed_database as seed_issues


def init_database() -> None:
    database.Base.metadata.create_all(bind=database.engine)
    for seed in (seed_issues, seed_notifications):
        with database.SessionLocal() as session:
            seed(session)


if __name__ == "__main__":
    init_database()
