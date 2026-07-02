"""Subject dataclass for the Intel module."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


class SubjectType:
    MISSING_PERSON = "Missing Person"
    WITNESS = "Witness"
    REPORTING_PARTY = "Reporting Party"
    PATIENT = "Patient"
    CONTACT = "Contact"
    VEHICLE = "Vehicle"
    AIRCRAFT = "Aircraft"


SUBJECT_TYPES = [
    SubjectType.MISSING_PERSON,
    SubjectType.WITNESS,
    SubjectType.REPORTING_PARTY,
    SubjectType.PATIENT,
    SubjectType.CONTACT,
    SubjectType.VEHICLE,
    SubjectType.AIRCRAFT,
]


@dataclass
class Subject:
    id: str
    incident_id: str
    subject_type: str
    name: str
    status: str = "Active"

    # Identity (person-specific)
    sex: Optional[str] = None
    dob: Optional[str] = None
    age: Optional[int] = None
    race: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    distinguishing_features: Optional[str] = None

    # SAR-specific (Missing Person)
    lkp_time: Optional[str] = None
    lkp_place: Optional[str] = None
    pls_time: Optional[str] = None
    pls_place: Optional[str] = None
    clothing_description: Optional[str] = None
    equipment_description: Optional[str] = None
    vehicle_description: Optional[str] = None
    outdoor_experience: Optional[str] = None
    behavioral_notes: Optional[str] = None
    communication_needs: Optional[str] = None
    sensory_considerations: Optional[str] = None
    routine_habits: Optional[str] = None
    wandering_history: Optional[str] = None
    favorite_places: Optional[str] = None
    triggers_or_stressors: Optional[str] = None
    recent_changes: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    mobility_limitations: Optional[str] = None

    # Contact
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    organization: Optional[str] = None
    relationship_to_incident: Optional[str] = None

    # Patient / care
    treatment_given: Optional[str] = None
    transport_required: Optional[str] = None
    transport_method: Optional[str] = None
    transport_destination: Optional[str] = None
    disposition: Optional[str] = None

    # Vehicle-specific fields
    plate: Optional[str] = None
    plate_state: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    color: Optional[str] = None
    vin: Optional[str] = None
    owner_or_operator: Optional[str] = None

    # Aircraft-specific fields
    tail_number: Optional[str] = None
    aircraft_type: Optional[str] = None
    make_model: Optional[str] = None
    color_markings: Optional[str] = None
    pilot_or_operator: Optional[str] = None
    route_or_last_contact: Optional[str] = None
    departure_point: Optional[str] = None
    destination: Optional[str] = None
    occupants: Optional[str] = None
    fuel_endurance: Optional[str] = None
    elt_survival_gear: Optional[str] = None
    remarks: Optional[str] = None

    # General description (vehicle, aircraft, or other non-person subjects)
    description: Optional[str] = None

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
            communication_needs=data.get("communication_needs"),
            sensory_considerations=data.get("sensory_considerations"),
            routine_habits=data.get("routine_habits"),
            wandering_history=data.get("wandering_history"),
            favorite_places=data.get("favorite_places"),
            triggers_or_stressors=data.get("triggers_or_stressors"),
            recent_changes=data.get("recent_changes"),
            medical_conditions=data.get("medical_conditions"),
            medications=data.get("medications"),
            mobility_limitations=data.get("mobility_limitations"),
            phone=data.get("phone"),
            email=data.get("email"),
            address=data.get("address"),
            organization=data.get("organization"),
            relationship_to_incident=data.get("relationship_to_incident"),
            treatment_given=data.get("treatment_given"),
            transport_required=data.get("transport_required"),
            transport_method=data.get("transport_method"),
            transport_destination=data.get("transport_destination"),
            disposition=data.get("disposition"),
            plate=data.get("plate"),
            plate_state=data.get("plate_state"),
            make=data.get("make"),
            model=data.get("model"),
            year=data.get("year"),
            color=data.get("color"),
            vin=data.get("vin"),
            owner_or_operator=data.get("owner_or_operator"),
            tail_number=data.get("tail_number"),
            aircraft_type=data.get("aircraft_type"),
            make_model=data.get("make_model"),
            color_markings=data.get("color_markings"),
            pilot_or_operator=data.get("pilot_or_operator"),
            route_or_last_contact=data.get("route_or_last_contact"),
            departure_point=data.get("departure_point"),
            destination=data.get("destination"),
            occupants=data.get("occupants"),
            fuel_endurance=data.get("fuel_endurance"),
            elt_survival_gear=data.get("elt_survival_gear"),
            remarks=data.get("remarks"),
            description=data.get("description"),
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
            "communication_needs": self.communication_needs,
            "sensory_considerations": self.sensory_considerations,
            "routine_habits": self.routine_habits,
            "wandering_history": self.wandering_history,
            "favorite_places": self.favorite_places,
            "triggers_or_stressors": self.triggers_or_stressors,
            "recent_changes": self.recent_changes,
            "medical_conditions": self.medical_conditions,
            "medications": self.medications,
            "mobility_limitations": self.mobility_limitations,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "organization": self.organization,
            "relationship_to_incident": self.relationship_to_incident,
            "treatment_given": self.treatment_given,
            "transport_required": self.transport_required,
            "transport_method": self.transport_method,
            "transport_destination": self.transport_destination,
            "disposition": self.disposition,
            "plate": self.plate,
            "plate_state": self.plate_state,
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "color": self.color,
            "vin": self.vin,
            "owner_or_operator": self.owner_or_operator,
            "tail_number": self.tail_number,
            "aircraft_type": self.aircraft_type,
            "make_model": self.make_model,
            "color_markings": self.color_markings,
            "pilot_or_operator": self.pilot_or_operator,
            "route_or_last_contact": self.route_or_last_contact,
            "departure_point": self.departure_point,
            "destination": self.destination,
            "occupants": self.occupants,
            "fuel_endurance": self.fuel_endurance,
            "elt_survival_gear": self.elt_survival_gear,
            "remarks": self.remarks,
            "description": self.description,
            "notes": self.notes,
            "linked_item_ids": self.linked_item_ids,
            "linked_task_ids": self.linked_task_ids,
        }
