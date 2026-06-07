from pathlib import Path

from modules.public_information.services import PublicInformationRepository, build_release_html


def test_message_workflow_and_preview(tmp_path: Path):
    repo = PublicInformationRepository("PIO-TEST", tmp_path / "incident.db")
    template = repo.save_template(
        {
            "template_name": "Standard",
            "template_type": "Press Release",
            "agency_name": "Agency",
            "header_text": "{agency_name} {release_title}",
            "footer_text": "Footer",
            "contact_block": "PIO Contact",
            "release_label": "FOR RELEASE",
            "is_active": 1,
            "version": 1,
        }
    )
    message = repo.save_message(
        {
            "title": "Update",
            "type": "Press Release",
            "audience": "Public",
            "priority": "Normal",
            "status": "Draft",
            "body": "Incident update body",
            "template_id": template["id"],
        },
        "user-1",
    )
    assert message["status"] == "Draft"
    assert repo.summary_counts()["Draft Messages"] == 1
    submitted = repo.set_message_status(message["id"], "Submitted for Review", "user-1", "ready")
    assert submitted["status"] == "Submitted for Review"
    approved = repo.set_message_status(message["id"], "Approved", "lead", "approved")
    assert approved["approved_by"] == "lead"
    published = repo.set_message_status(message["id"], "Published", "lead", "released")
    assert published["published_at"]
    approvals = repo.list_approvals(message["id"])
    assert [item["action"] for item in approvals] == ["Submitted for Review", "Approved", "Published"]
    html = build_release_html(published, template)
    assert "FOR RELEASE" in html
    assert "Incident update body" in html


def test_tracker_media_talking_points_and_distribution(tmp_path: Path):
    repo = PublicInformationRepository("PIO-TEST", tmp_path / "incident.db")
    rumor = repo.save_record(
        "pio_misinformation_items",
        {
            "severity": "Moderate",
            "claim_rumor": "Claim text",
            "operational_impact": "Public Confusion",
            "status": "Monitoring",
            "response_decision": "Monitor Only",
        },
        "last_update",
    )
    assert rumor["response_decision"] == "Monitor Only"
    repo.add_misinformation_timeline(rumor["id"], "Verified source context")
    assert len(repo.list_misinformation_timeline(rumor["id"])) == 1
    media = repo.save_record(
        "pio_media_log",
        {"topic": "Media question", "status": "New", "follow_up_needed": 1},
    )
    draft = repo.create_response_draft_from_media(media["id"], "pio")
    assert draft["audience"] == "Media"
    assert draft["source_media_log_id"] == media["id"]
    point = repo.save_record(
        "pio_talking_points",
        {"title": "Approved point", "category": "Approved to Say", "status": "Draft"},
        "updated_at",
    )
    assert point["category"] == "Approved to Say"
    dist = repo.save_record(
        "pio_distribution_log",
        {"message_id": draft["id"], "channel": "Website", "audience": "Public"},
    )
    assert dist["channel"] == "Website"
