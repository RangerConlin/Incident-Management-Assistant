from modules.public_information.services import PublicInformationRepository, build_release_html


class FakePublicInformationApiClient:
    def __init__(self):
        self.messages = []
        self.revisions = []
        self.approvals = []
        self.templates = []
        self.records = {
            "pio_media_log": [],
            "pio_misinformation_items": [],
            "pio_misinformation_timeline": [],
            "pio_talking_points": [],
            "pio_distribution_log": [],
            "pio_generated_documents": [],
        }

    def get(self, path, *, params=None):
        if path.endswith("/messages"):
            return sorted(self.messages, key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
        if "/messages/" in path and path.endswith("/approvals"):
            message_id = int(path.split("/messages/")[1].split("/")[0])
            return [row for row in self.approvals if row["message_id"] == message_id]
        if "/messages/" in path:
            message_id = int(path.rsplit("/", 1)[1])
            return self._find(self.messages, message_id)
        if path.endswith("/templates"):
            rows = list(self.templates)
            if (params or {}).get("active_only") == "true":
                rows = [row for row in rows if row.get("is_active") == 1]
            return sorted(rows, key=lambda row: row.get("template_name", ""))
        if "/templates/" in path:
            return self._find(self.templates, int(path.rsplit("/", 1)[1]))
        if "/records/" in path:
            table = path.rsplit("/", 1)[1]
            return list(self.records[table])
        if "/misinformation/" in path and path.endswith("/timeline"):
            item_id = int(path.split("/misinformation/")[1].split("/")[0])
            return [row for row in self.records["pio_misinformation_timeline"] if row["item_id"] == item_id]
        if path.endswith("/summary"):
            return {
                "Pending Approvals": sum(1 for row in self.messages if row.get("status") == "Submitted for Review"),
                "Draft Messages": sum(1 for row in self.messages if row.get("status") == "Draft"),
                "Published / Released Messages": sum(1 for row in self.messages if row.get("status") == "Published"),
                "Media Follow-Ups": sum(
                    1
                    for row in self.records["pio_media_log"]
                    if row.get("follow_up_needed") in {1, True} or row.get("status") == "Follow-Up Needed"
                ),
                "Active Misinformation Items": sum(
                    1
                    for row in self.records["pio_misinformation_items"]
                    if row.get("status") not in {"Corrected", "Closed"}
                ),
                "Next Briefing / Next Update": "Not scheduled",
            }
        raise AssertionError(f"Unhandled GET {path}")

    def post(self, path, *, json=None):
        payload = dict(json or {})
        if path.endswith("/messages"):
            return self._save_message(payload)
        if "/messages/" in path and path.endswith("/status"):
            message_id = int(path.split("/messages/")[1].split("/")[0])
            message = self._find(self.messages, message_id)
            message["status"] = payload["status"]
            message["updated_at"] = "now"
            if payload["status"] == "Approved":
                message["approved_by"] = payload.get("user", "")
            if payload["status"] == "Published":
                message["published_at"] = "now"
            self.approvals.append(
                {
                    "id": len(self.approvals) + 1,
                    "message_id": message_id,
                    "reviewer_id": payload.get("user", ""),
                    "reviewer_name": payload.get("user", ""),
                    "action": payload["status"],
                    "comment": payload.get("comment", ""),
                    "timestamp": "now",
                }
            )
            return message
        if path.endswith("/templates"):
            return self._save(self.templates, payload)
        if "/records/" in path:
            table = path.rsplit("/", 1)[1]
            return self._save(self.records[table], payload)
        if "/media/" in path and path.endswith("/response-draft"):
            media_id = int(path.split("/media/")[1].split("/")[0])
            media = self._find(self.records["pio_media_log"], media_id)
            message = self._save_message(
                {
                    "title": media.get("topic", ""),
                    "type": "Holding Statement",
                    "audience": "Media",
                    "priority": "Normal",
                    "status": "Draft",
                    "created_by": payload.get("user", ""),
                    "source_media_log_id": media_id,
                }
            )
            media["related_message_id"] = message["id"]
            return message
        if "/misinformation/" in path and path.endswith("/timeline"):
            item_id = int(path.split("/misinformation/")[1].split("/")[0])
            return self._save(
                self.records["pio_misinformation_timeline"],
                {"item_id": item_id, "event_time": "now", "event_text": payload.get("event_text", "")},
            )
        raise AssertionError(f"Unhandled POST {path}")

    def _save_message(self, payload):
        payload.pop("_revision_user", None)
        message = self._save(self.messages, payload)
        self.revisions.append(
            {
                "id": len(self.revisions) + 1,
                "message_id": message["id"],
                "title": message.get("title", ""),
                "body": message.get("body", ""),
                "revision_number": sum(1 for row in self.revisions if row["message_id"] == message["id"]) + 1,
            }
        )
        return message

    def _save(self, rows, payload):
        if payload.get("id"):
            row = self._find(rows, int(payload["id"]))
            row.update(payload)
            return row
        row = dict(payload)
        row["id"] = len(rows) + 1
        rows.append(row)
        return row

    @staticmethod
    def _find(rows, row_id):
        for row in rows:
            if row.get("id") == row_id:
                return row
        raise AssertionError(f"Row {row_id} not found")


def repo():
    return PublicInformationRepository("PIO-TEST", api_client=FakePublicInformationApiClient())


def test_message_workflow_and_preview():
    repository = repo()
    template = repository.save_template(
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
    message = repository.save_message(
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
    assert repository.summary_counts()["Draft Messages"] == 1
    submitted = repository.set_message_status(message["id"], "Submitted for Review", "user-1", "ready")
    assert submitted["status"] == "Submitted for Review"
    approved = repository.set_message_status(message["id"], "Approved", "lead", "approved")
    assert approved["approved_by"] == "lead"
    published = repository.set_message_status(message["id"], "Published", "lead", "released")
    assert published["published_at"]
    approvals = repository.list_approvals(message["id"])
    assert [item["action"] for item in approvals] == ["Submitted for Review", "Approved", "Published"]
    html = build_release_html(published, template)
    assert "FOR RELEASE" in html
    assert "Incident update body" in html


def test_tracker_media_talking_points_and_distribution():
    repository = repo()
    rumor = repository.save_record(
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
    repository.add_misinformation_timeline(rumor["id"], "Verified source context")
    assert len(repository.list_misinformation_timeline(rumor["id"])) == 1
    media = repository.save_record(
        "pio_media_log",
        {"topic": "Media question", "status": "New", "follow_up_needed": 1},
    )
    draft = repository.create_response_draft_from_media(media["id"], "pio")
    assert draft["audience"] == "Media"
    assert draft["source_media_log_id"] == media["id"]
    point = repository.save_record(
        "pio_talking_points",
        {"title": "Approved point", "category": "Approved to Say", "status": "Draft"},
        "updated_at",
    )
    assert point["category"] == "Approved to Say"
    dist = repository.save_record(
        "pio_distribution_log",
        {"message_id": draft["id"], "channel": "Website", "audience": "Public"},
    )
    assert dist["channel"] == "Website"
