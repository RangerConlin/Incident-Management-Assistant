"""Seed script for Public Information module."""

from .models.repository import PublicInfoRepository


def seed(mission_id: int) -> None:
    repo = PublicInfoRepository(mission_id)
    admin = {"id": 1, "roles": ["PIO", "LeadPIO", "IC"]}

    # Draft message
    repo.create_message(
        {
            "title": "Draft Message",
            "body": "This is a draft message.",
            "type": "PressRelease",
            "audience": "Public",
            "tags": "draft",
            "created_by": 1,
        }
    )

    # InReview message
    msg = repo.create_message(
        {
            "title": "Review Message",
            "body": "Pending review.",
            "type": "Advisory",
            "audience": "Agency",
            "created_by": 1,
        }
    )
    repo.submit_for_review(msg["id"], 1)

    # Published message
    msg = repo.create_message(
        {
            "title": "Published Message",
            "body": "This has been published.",
            "type": "SituationUpdate",
            "audience": "Public",
            "created_by": 1,
        }
    )
    repo.submit_for_review(msg["id"], 1)
    repo.approve_message(msg["id"], admin)
    repo.publish_message(msg["id"], admin)


if __name__ == "__main__":
    seed(1)
