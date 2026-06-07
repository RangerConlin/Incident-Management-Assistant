"""Shared values for the Public Information module."""

MESSAGE_TYPES = [
    "Press Release",
    "Public Advisory",
    "Situation Update",
    "Missing Person Bulletin",
    "Road / Access Notice",
    "Safety Notice",
    "Internal Bulletin",
    "Agency Update",
    "Misinformation Correction",
    "Holding Statement",
    "Social Media Post",
]
AUDIENCES = ["Public", "Media", "Agency", "Internal"]
PRIORITIES = ["Low", "Normal", "High", "Critical"]
MESSAGE_STATUSES = [
    "Draft",
    "Submitted for Review",
    "Returned for Revision",
    "Approved",
    "Published",
    "Retracted",
    "Archived",
]
APPROVAL_ACTIONS = [
    "Submit",
    "Approve",
    "Return for Revision",
    "Reject",
    "Publish",
    "Retract",
    "Archive",
]
APPROVAL_STEPS = [
    "Created",
    "Submitted for Review",
    "Under Review",
    "Command Review",
    "Approved",
    "Published",
]
MISINFORMATION_SEVERITIES = ["Low", "Moderate", "High", "Critical"]
MISINFORMATION_STATUSES = [
    "New",
    "Verifying",
    "Monitoring",
    "Response Needed",
    "Drafting Correction",
    "Pending Approval",
    "Corrected",
    "Escalated",
    "Closed",
]
OPERATIONAL_IMPACTS = [
    "None",
    "Public Confusion",
    "Media Escalation",
    "Family Impact",
    "Volunteer Convergence",
    "Responder Safety Issue",
    "Access / Traffic Issue",
    "Investigation Sensitive",
    "Command-Level Concern",
]
VERIFICATION_STATUSES = ["Unknown", "False", "Partially True", "True", "Unable to Verify"]
RESPONSE_DECISIONS = [
    "Monitor Only",
    "Internal Advisory",
    "Public Correction",
    "Media Talking Point",
    "Partner Agency Coordination",
    "Escalate to Command",
    "Escalate to Law Enforcement",
]
MEDIA_STATUSES = [
    "New",
    "Assigned",
    "Drafting Response",
    "Waiting Approval",
    "Responded",
    "Follow-Up Needed",
    "Closed",
]
TALKING_POINT_CATEGORIES = [
    "Approved to Say",
    "Do Not Release",
    "Holding Statement",
    "Safety Instructions",
    "Media Q&A",
    "Next Update",
]
TALKING_POINT_STATUSES = ["Draft", "Approved", "Retired"]
TEMPLATE_TYPES = [
    "Press Release",
    "Public Advisory",
    "Missing Person Bulletin",
    "Media Statement",
    "Joint Agency Release",
    "Internal Bulletin",
    "Situation Update",
    "Misinformation Correction",
    "Holding Statement",
]
MERGE_FIELDS = [
    "{incident_name}",
    "{incident_number}",
    "{operational_period}",
    "{release_datetime}",
    "{prepared_by}",
    "{approved_by}",
    "{pio_contact_name}",
    "{pio_contact_phone}",
    "{agency_name}",
    "{release_title}",
    "{release_subtitle}",
    "{release_body}",
    "{next_update_time}",
    "{public_summary}",
]
DISTRIBUTION_CHANNELS = [
    "Press Release Email",
    "Website",
    "Social Media",
    "Partner Agency",
    "Printed Handout",
    "Public Briefing",
    "Radio Announcement",
    "Internal Bulletin",
    "EOC Update",
]
