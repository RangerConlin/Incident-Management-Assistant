import { useState } from "react";
import { SUBJECT_STATUSES, SUBJECT_TYPES } from "../../../api/endpoints";
import { SelectField, TextField } from "../IntelFormFields";

const PERSON_TYPES = new Set(["Missing Person", "Witness", "Reporting Party", "Contact", "Patient"]);

interface NewSubjectDialogProps {
  initialType: string;
  /** "Missing Person — Quick" opens the same dialog with the second half of
   * SAR Details hidden — matches desktop's `quick` flag on
   * _NewSubjectDialog, not a separate form. */
  initialQuick: boolean;
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
}

export default function NewSubjectDialog({ initialType, initialQuick, onCreate, onCancel, busy }: NewSubjectDialogProps) {
  const [type, setType] = useState(initialType);
  const [quick] = useState(initialQuick);
  const [name, setName] = useState("");
  const [status, setStatus] = useState("Active");
  const [f, setF] = useState<Record<string, string>>({});
  const set = (key: string) => (value: string) => setF((prev) => ({ ...prev, [key]: value }));

  const isMissing = type === "Missing Person";
  const isPatient = type === "Patient";
  const isPerson = PERSON_TYPES.has(type);
  const isVehicle = type === "Vehicle";
  const isAircraft = type === "Aircraft";
  const hasIdentity = isMissing || isPatient;

  const title = quick && isMissing ? "Quick Capture" : `New ${type} Profile`;

  const buildBody = (): Record<string, unknown> => ({
    subject_type: type,
    name: name.trim(),
    status,
    ...(hasIdentity && {
      age: f.age ? Number(f.age) : undefined,
      sex: f.sex,
      dob: f.dob,
      race: f.race,
      height: f.height,
      weight: f.weight,
      hair_color: f.hair_color,
      eye_color: f.eye_color,
      distinguishing_features: f.distinguishing_features,
    }),
    ...(isPerson && {
      phone: f.phone,
      email: f.email,
      address: f.address,
      organization: f.organization,
      relationship_to_incident: f.relationship_to_incident,
    }),
    ...(isMissing && {
      lkp_place: f.lkp_place,
      lkp_time: f.lkp_time,
      clothing_description: f.clothing_description,
      ...(!quick && {
        pls_place: f.pls_place,
        pls_time: f.pls_time,
        equipment_description: f.equipment_description,
        vehicle_description: f.vehicle_description,
        outdoor_experience: f.outdoor_experience,
        behavioral_notes: f.behavioral_notes,
        communication_needs: f.communication_needs,
        sensory_considerations: f.sensory_considerations,
        routine_habits: f.routine_habits,
        wandering_history: f.wandering_history,
        favorite_places: f.favorite_places,
        triggers_or_stressors: f.triggers_or_stressors,
        recent_changes: f.recent_changes,
        medical_conditions: f.medical_conditions,
        medications: f.medications,
        mobility_limitations: f.mobility_limitations,
      }),
    }),
    ...(isPatient && {
      medical_conditions: f.medical_conditions,
      medications: f.medications,
      treatment_given: f.treatment_given,
      transport_required: f.transport_required,
      transport_method: f.transport_method,
      transport_destination: f.transport_destination,
      disposition: f.disposition,
    }),
    ...(isVehicle && {
      make: f.make,
      model: f.model,
      year: f.year ? Number(f.year) : undefined,
      color: f.color,
      plate: f.plate,
      plate_state: f.plate_state,
      vin: f.vin,
      owner_or_operator: f.owner_or_operator,
      description: f.description,
    }),
    ...(isAircraft && {
      tail_number: f.tail_number,
      aircraft_type: f.aircraft_type,
      make_model: f.make_model,
      color_markings: f.color_markings,
      pilot_or_operator: f.pilot_or_operator,
      departure_point: f.departure_point,
      destination: f.destination,
      occupants: f.occupants,
      fuel_endurance: f.fuel_endurance,
      elt_survival_gear: f.elt_survival_gear,
      route_or_last_contact: f.route_or_last_contact,
      remarks: f.remarks,
    }),
    notes: f.notes,
  });

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" style={{ maxWidth: 640, maxHeight: "85vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>

        <TextField label="Name" value={name} onChange={setName} required placeholder="Name or temporary identifier" />
        <SelectField label="Type" value={type} onChange={setType} options={SUBJECT_TYPES} />
        <SelectField label="Status" value={status} onChange={setStatus} options={SUBJECT_STATUSES} />

        {hasIdentity && (
          <fieldset>
            <legend>Identity</legend>
            <TextField label="Age" value={f.age ?? ""} onChange={set("age")} type="number" />
            <TextField label="Sex" value={f.sex ?? ""} onChange={set("sex")} />
            <TextField label="DOB" value={f.dob ?? ""} onChange={set("dob")} placeholder="YYYY-MM-DD" />
            <TextField label="Race" value={f.race ?? ""} onChange={set("race")} />
            <TextField label="Height" value={f.height ?? ""} onChange={set("height")} />
            <TextField label="Weight" value={f.weight ?? ""} onChange={set("weight")} />
            <TextField label="Hair Color" value={f.hair_color ?? ""} onChange={set("hair_color")} />
            <TextField label="Eye Color" value={f.eye_color ?? ""} onChange={set("eye_color")} />
            <TextField label="Distinguishing Features" value={f.distinguishing_features ?? ""} onChange={set("distinguishing_features")} textarea />
          </fieldset>
        )}

        {isPerson && (
          <fieldset>
            <legend>Contact Information</legend>
            <TextField label="Phone" value={f.phone ?? ""} onChange={set("phone")} />
            <TextField label="Email" value={f.email ?? ""} onChange={set("email")} />
            <TextField label="Address" value={f.address ?? ""} onChange={set("address")} />
            <TextField label="Organization" value={f.organization ?? ""} onChange={set("organization")} />
            <TextField label="Relationship to Incident" value={f.relationship_to_incident ?? ""} onChange={set("relationship_to_incident")} />
          </fieldset>
        )}

        {isMissing && (
          <fieldset>
            <legend>SAR Details</legend>
            <TextField label="LKP Place" value={f.lkp_place ?? ""} onChange={set("lkp_place")} />
            <TextField label="LKP Time" value={f.lkp_time ?? ""} onChange={set("lkp_time")} placeholder="YYYY-MM-DD HH:MM" />
            <TextField label="Clothing" value={f.clothing_description ?? ""} onChange={set("clothing_description")} textarea />
            {!quick && (
              <>
                <TextField label="PLS Place" value={f.pls_place ?? ""} onChange={set("pls_place")} />
                <TextField label="PLS Time" value={f.pls_time ?? ""} onChange={set("pls_time")} placeholder="YYYY-MM-DD HH:MM" />
                <TextField label="Equipment" value={f.equipment_description ?? ""} onChange={set("equipment_description")} textarea />
                <TextField label="Vehicle Description" value={f.vehicle_description ?? ""} onChange={set("vehicle_description")} />
                <TextField label="Outdoor Experience" value={f.outdoor_experience ?? ""} onChange={set("outdoor_experience")} />
                <TextField label="Behavioral Notes" value={f.behavioral_notes ?? ""} onChange={set("behavioral_notes")} textarea />
                <TextField label="Communication Needs" value={f.communication_needs ?? ""} onChange={set("communication_needs")} />
                <TextField label="Sensory Considerations" value={f.sensory_considerations ?? ""} onChange={set("sensory_considerations")} />
                <TextField label="Routine Habits" value={f.routine_habits ?? ""} onChange={set("routine_habits")} textarea />
                <TextField label="Wandering History" value={f.wandering_history ?? ""} onChange={set("wandering_history")} />
                <TextField label="Favorite Places" value={f.favorite_places ?? ""} onChange={set("favorite_places")} />
                <TextField label="Triggers/Stressors" value={f.triggers_or_stressors ?? ""} onChange={set("triggers_or_stressors")} />
                <TextField label="Recent Changes" value={f.recent_changes ?? ""} onChange={set("recent_changes")} />
                <TextField label="Medical Conditions" value={f.medical_conditions ?? ""} onChange={set("medical_conditions")} textarea />
                <TextField label="Medications" value={f.medications ?? ""} onChange={set("medications")} />
                <TextField label="Mobility Limitations" value={f.mobility_limitations ?? ""} onChange={set("mobility_limitations")} />
              </>
            )}
          </fieldset>
        )}

        {isPatient && (
          <fieldset>
            <legend>Patient Care</legend>
            <TextField label="Medical Conditions" value={f.medical_conditions ?? ""} onChange={set("medical_conditions")} textarea />
            <TextField label="Medications" value={f.medications ?? ""} onChange={set("medications")} />
            <TextField label="Treatment Given" value={f.treatment_given ?? ""} onChange={set("treatment_given")} textarea />
            <TextField label="Transport Required" value={f.transport_required ?? ""} onChange={set("transport_required")} />
            <TextField label="Transport Method" value={f.transport_method ?? ""} onChange={set("transport_method")} />
            <TextField label="Transport Destination" value={f.transport_destination ?? ""} onChange={set("transport_destination")} />
            <TextField label="Disposition" value={f.disposition ?? ""} onChange={set("disposition")} />
          </fieldset>
        )}

        {isVehicle && (
          <fieldset>
            <legend>Vehicle Details</legend>
            <TextField label="Make" value={f.make ?? ""} onChange={set("make")} />
            <TextField label="Model" value={f.model ?? ""} onChange={set("model")} />
            <TextField label="Year" value={f.year ?? ""} onChange={set("year")} type="number" placeholder="e.g. 2019" />
            <TextField label="Color" value={f.color ?? ""} onChange={set("color")} />
            <TextField label="License Plate" value={f.plate ?? ""} onChange={set("plate")} />
            <TextField label="Plate State" value={f.plate_state ?? ""} onChange={set("plate_state")} />
            <TextField label="VIN" value={f.vin ?? ""} onChange={set("vin")} />
            <TextField label="Owner/Operator" value={f.owner_or_operator ?? ""} onChange={set("owner_or_operator")} />
            <TextField label="Description" value={f.description ?? ""} onChange={set("description")} textarea />
          </fieldset>
        )}

        {isAircraft && (
          <fieldset>
            <legend>Aircraft Details</legend>
            <TextField label="Tail Number" value={f.tail_number ?? ""} onChange={set("tail_number")} />
            <TextField label="Aircraft Type" value={f.aircraft_type ?? ""} onChange={set("aircraft_type")} />
            <TextField label="Make/Model" value={f.make_model ?? ""} onChange={set("make_model")} />
            <TextField label="Color/Markings" value={f.color_markings ?? ""} onChange={set("color_markings")} />
            <TextField label="Pilot/Operator" value={f.pilot_or_operator ?? ""} onChange={set("pilot_or_operator")} />
            <TextField label="Departure Point" value={f.departure_point ?? ""} onChange={set("departure_point")} />
            <TextField label="Destination" value={f.destination ?? ""} onChange={set("destination")} />
            <TextField label="Occupants" value={f.occupants ?? ""} onChange={set("occupants")} />
            <TextField label="Fuel Endurance" value={f.fuel_endurance ?? ""} onChange={set("fuel_endurance")} />
            <TextField label="ELT/Survival Gear" value={f.elt_survival_gear ?? ""} onChange={set("elt_survival_gear")} />
            <TextField label="Route/Last Contact" value={f.route_or_last_contact ?? ""} onChange={set("route_or_last_contact")} textarea />
            <TextField label="Remarks" value={f.remarks ?? ""} onChange={set("remarks")} textarea />
          </fieldset>
        )}

        <TextField label="Notes" value={f.notes ?? ""} onChange={set("notes")} textarea />

        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button disabled={!name.trim() || busy} onClick={() => onCreate(buildBody())}>
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
