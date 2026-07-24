from modules.intel.weather.services import thresholds


def test_evaluate_ground_go_marginal_nogo_boundaries():
    t = thresholds.DEFAULT_GROUND_THRESHOLDS
    assert thresholds.evaluate_ground({"wind_gust_mph": 5}, t) == "go"
    assert thresholds.evaluate_ground({"wind_gust_mph": t["wind_gust_marginal_mph"]}, t) == "marginal"
    assert thresholds.evaluate_ground({"wind_gust_mph": t["wind_gust_nogo_mph"]}, t) == "no_go"


def test_evaluate_ground_lower_is_worse_for_visibility_and_ceiling():
    t = thresholds.DEFAULT_GROUND_THRESHOLDS
    assert thresholds.evaluate_ground({"visibility_mi": 10}, t) == "go"
    assert thresholds.evaluate_ground({"visibility_mi": t["visibility_marginal_mi"]}, t) == "marginal"
    assert thresholds.evaluate_ground({"visibility_mi": t["visibility_nogo_mi"] - 0.1}, t) == "no_go"


def test_evaluate_ground_missing_values_are_go():
    assert thresholds.evaluate_ground({}, thresholds.DEFAULT_GROUND_THRESHOLDS) == "go"


def test_single_nogo_metric_overrides_otherwise_marginal_reading():
    t = thresholds.DEFAULT_GROUND_THRESHOLDS
    reading = {
        "wind_gust_mph": t["wind_gust_marginal_mph"],  # marginal
        "visibility_mi": t["visibility_nogo_mi"] - 0.1,  # no-go
    }
    assert thresholds.evaluate_ground(reading, t) == "no_go"


def test_evaluate_aviation_includes_crosswind_metric():
    t = thresholds.DEFAULT_AVIATION_THRESHOLDS
    verdict_go = thresholds.evaluate_aviation({}, t, crosswind_kt=5)
    assert verdict_go == "go"
    verdict_nogo = thresholds.evaluate_aviation({}, t, crosswind_kt=t["crosswind_nogo_kt"])
    assert verdict_nogo == "no_go"


def test_evaluate_aviation_without_crosswind_data_ignores_that_metric():
    t = thresholds.DEFAULT_AVIATION_THRESHOLDS
    assert thresholds.evaluate_aviation({}, t, crosswind_kt=None) == "go"
