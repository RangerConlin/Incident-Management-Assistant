"""Subject dataclass for the Intel module."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


class SubjectType:
    MISSING_PERSON = "Missing Person"
    WITNESS = "Witness"
    REPORTING_PARTY = "Reporting Party"
    PATIENT = "Patient"
    PERSON_OF_INTEREST = "Person of Interest"
    CONTACT = "Contact"


SUBJECT_TYPES = [
    SubjectType.MISSING_PERSON,
    SubjectType.WITNESS,
    SubjectType.REPORTING_PARTY,
    SubjectType.PATIENT,
    SubjectType.PERSON_OF_INTEREST,
    SubjectType.CONTACT,
]


@dataclass
class Subject:
    id: str
    incident_id: str
    subject_type: str
    name: str
    status: str = "Active"

    # Identity
    sex: Optional[str] = None
    dob: Optional[str] = None
    age: Optional[int] = None
    race: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    distinguishing_features: Optional[str] = None

    # SAR-specific
    lkp_time: Optional[str] = None
    lkp_place: Optional[str] = None
    pls_time: Optional[str] = None
    pls_place: Optional[str] = None
    clothing_description: Optional[str] = None
    equipment_description: Optional[str] = None
    vehicle_description: Optional[str] = None
    outdoor_experience: Optional[str] = None
    behavioral_notes: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    mobility_limitations: Optional[str] = None

    # Contact
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    organization: Optional[str] = None

    # Witness / reporting party
    reliability: Optional[str] = None
    initial_report: Optional[str] = None

    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    deleted: bool = False

    linked_item_ids: list[str] = field(default_factory=list)
    linked_task_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> "Subject":
        return cls(
            id=data.get("_id") or data.get("id", ""),
            incident_id=data.get("incident_id", ""),
            subject_type=data.get("subject_type", SubjectType.MISSING_PERSON),
            name=data.get("name", "Unknown"),
            status=data.get("status", "Active"),
            sex=data.get("sex"),
            dob=data.get("dob"),
            age=data.get("age"),
            race=data.get("race"),
            height=data.get("height"),
            weight=data.get("weight"),
            hair_color=data.get("hair_color"),
            eye_color=data.get("eye_color"),
            distinguishing_features=data.get("distinguishing_features"),
            lkp_time=data.get("lkp_time"),
            lkp_place=data.get("lkp_place"),
            pls_time=data.get("pls_time"),
            pls_place=data.get("pls_place"),
            clothing_description=data.get("clothing_description"),
            equipment_description=data.get("equipment_description"),
            vehicle_description=data.get("vehicle_description"),
            outdoor_experience=data.get("outdoor_experience"),
            behavioral_notes=data.get("behavioral_notes"),
            medical_conditions=data.get("medical_conditions"),
            medications=data.get("medications"),
            mobility_limitations=data.get("mobility_limitations"),
            phone=data.get("phone"),
            email=data.get("email"),
            address=data.get("address"),
            organization=data.get("organization"),
            reliability=data.get("reliability"),
            initial_report=data.get("initial_report"),
            notes=data.get("notes"),
            created_by=data.get("created_by"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            deleted=data.get("deleted", False),
            linked_item_ids=data.get("linked_item_ids", []),
            linked_task_ids=data.get("linked_task_ids", []),
        )

    def to_api_dict(self) -> dict:
        return {
            "subject_type": self.subject_type,
            "name": self.name,
            "status": self.status,
            "sex": self.sex,
            "dob": self.dob,
            "age": self.age,
            "race": self.race,
            "height": self.height,
            "weight": self.weight,
            "hair_color": self.hair_color,
            "eye_color": self.eye_color,
            "distinguishing_features": self.distinguishing_features,
            "lkp_time": self.lkp_time,
            "lkp_place": self.lkp_place,
            "pls_time": self.pls_time,
            "pls_place": self.pls_place,
            "clothing_description": self.clothing_description,
            "equipment_description": self.equipment_description,
            "vehicle_description": self.vehicle_description,
            "outdoor_experience": self.outdoor_experience,
            "behavioral_notes": self.behavioral_notes,
            "medical_conditions": self.medical_conditions,
            "medications": self.medications,
            "mobility_limitations": self.mobility_limitations,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "organization": self.organization,
            "reliability": self.reliability,
            "initial_report": self.initial_report,
            "notes": self.notes,
        }
