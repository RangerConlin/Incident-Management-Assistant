from modules.intel.weather.models.location import RunwayEnd
from modules.intel.weather.services import crosswind


def test_compute_crosswind_direct_headwind_is_zero_crosswind():
    # Wind directly down the runway: crosswind ~0, headwind ~= wind speed
    xwind, headwind = crosswind.compute_crosswind(wind_dir_deg=90, wind_speed_kt=20, runway_heading_deg=90)
    assert abs(xwind) < 0.01
    assert abs(headwind - 20) < 0.01


def test_compute_crosswind_direct_crosswind_is_zero_headwind():
    # Wind 90 degrees off runway heading: full crosswind, ~0 headwind
    xwind, headwind = crosswind.compute_crosswind(wind_dir_deg=180, wind_speed_kt=20, runway_heading_deg=90)
    assert abs(xwind - 20) < 0.01
    assert abs(headwind) < 0.01


def test_best_runway_crosswind_picks_lowest():
    runway_ends = [
        RunwayEnd(designator="09", heading_true_deg=90, length_ft=3000),
        RunwayEnd(designator="18", heading_true_deg=180, length_ft=3000),
    ]
    result = crosswind.best_runway_crosswind(runway_ends, wind_dir_deg=95, wind_speed_kt=20)
    assert result is not None
    assert result.runway.designator == "09"
    assert result.crosswind_kt < 5


def test_missing_runway_data_returns_none_not_a_guess():
    assert crosswind.best_runway_crosswind([], wind_dir_deg=90, wind_speed_kt=10) is None
    assert crosswind.all_runway_crosswinds([], wind_dir_deg=90, wind_speed_kt=10) == []


def test_missing_wind_data_returns_none():
    runway_ends = [RunwayEnd(designator="09", heading_true_deg=90, length_ft=3000)]
    assert crosswind.best_runway_crosswind(runway_ends, wind_dir_deg=None, wind_speed_kt=None) is None


def test_all_runway_crosswinds_sorted_best_first():
    runway_ends = [
        RunwayEnd(designator="18", heading_true_deg=180, length_ft=3000),
        RunwayEnd(designator="09", heading_true_deg=90, length_ft=3000),
    ]
    results = crosswind.all_runway_crosswinds(runway_ends, wind_dir_deg=95, wind_speed_kt=20)
    assert len(results) == 2
    assert results[0].runway.designator == "09"
    assert results[0].crosswind_kt <= results[1].crosswind_kt
