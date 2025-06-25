# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""Tests for the frequenz.reporting package."""
from datetime import datetime
from typing import Any

import pytest
from frequenz.client.reporting._types import MetricSample

from frequenz.reporting import delete_me
from frequenz.reporting._reporting import extract_state_durations

test_cases_extract_state_durations = [
    {
        "description": "Empty samples",
        "samples": [],
        "alert_states": [1, 2],
        "include_warnings": True,
        "expected_all_states": [],
        "expected_alert_records": [],
    },
    {
        "description": "No matching metrics",
        "samples": [
            MetricSample(datetime(2023, 1, 1, 0, 0), 1, "101", "temperature", 25),
            MetricSample(datetime(2023, 1, 1, 1, 0), 1, "101", "humidity", 60),
        ],
        "alert_states": [1],
        "include_warnings": True,
        "expected_all_states": [],
        "expected_alert_records": [],
    },
    {
        "description": "Single state change",
        "samples": [
            MetricSample(datetime(2023, 1, 1, 0, 0), 1, "101", "state", 0),
            MetricSample(datetime(2023, 1, 1, 1, 0), 1, "101", "state", 1),
        ],
        "alert_states": [1],
        "include_warnings": True,
        "expected_all_states": [
            {
                "microgrid_id": 1,
                "component_id": "101",
                "state_type": "state",
                "state_value": 0,
                "start_time": datetime(2023, 1, 1, 0, 0),
                "end_time": datetime(2023, 1, 1, 1, 0),
            },
            {
                "microgrid_id": 1,
                "component_id": "101",
                "state_type": "state",
                "state_value": 1,
                "start_time": datetime(2023, 1, 1, 1, 0),
                "end_time": None,
            },
        ],
        "expected_alert_records": [
            {
                "microgrid_id": 1,
                "component_id": "101",
                "state_type": "state",
                "state_value": 1,
                "start_time": datetime(2023, 1, 1, 1, 0),
                "end_time": None,
            },
        ],
    },
    {
        "description": "Warnings and errors included",
        "samples": [
            MetricSample(datetime(2023, 1, 2, 0, 0), 3, "303", "state", 0),
            MetricSample(datetime(2023, 1, 2, 0, 30), 3, "303", "warning", 10),
            MetricSample(datetime(2023, 1, 2, 1, 0), 3, "303", "state", 1),
            MetricSample(datetime(2023, 1, 2, 1, 30), 3, "303", "error", 20),
        ],
        "alert_states": [1],
        "include_warnings": True,
        "expected_all_states": [
            # State transitions
            {
                "microgrid_id": 3,
                "component_id": "303",
                "state_type": "state",
                "state_value": 0,
                "start_time": datetime(2023, 1, 2, 0, 0),
                "end_time": datetime(2023, 1, 2, 1, 0),
            },
            {
                "microgrid_id": 3,
                "component_id": "303",
                "state_type": "state",
                "state_value": 1,
                "start_time": datetime(2023, 1, 2, 1, 0),
                "end_time": None,
            },
            # Warning transitions
            {
                "microgrid_id": 3,
                "component_id": "303",
                "state_type": "warning",
                "state_value": 10,
                "start_time": datetime(2023, 1, 2, 0, 30),
                "end_time": None,
            },
            # Error transitions
            {
                "microgrid_id": 3,
                "component_id": "303",
                "state_type": "error",
                "state_value": 20,
                "start_time": datetime(2023, 1, 2, 1, 30),
                "end_time": None,
            },
        ],
        "expected_alert_records": [
            {
                "microgrid_id": 3,
                "component_id": "303",
                "state_type": "warning",
                "state_value": 10,
                "start_time": datetime(2023, 1, 2, 0, 30),
                "end_time": None,
            },
            {
                "microgrid_id": 3,
                "component_id": "303",
                "state_type": "error",
                "state_value": 20,
                "start_time": datetime(2023, 1, 2, 1, 30),
                "end_time": None,
            },
            # State alert
            {
                "microgrid_id": 3,
                "component_id": "303",
                "state_type": "state",
                "state_value": 1,
                "start_time": datetime(2023, 1, 2, 1, 0),
                "end_time": None,
            },
        ],
    },
]


@pytest.mark.parametrize(
    "test_case", test_cases_extract_state_durations, ids=lambda tc: tc["description"]
)
def test_extract_state_durations(test_case: dict[str, Any]) -> None:
    """Test the extract_state_durations function."""
    all_states, alert_records = extract_state_durations(
        test_case["samples"], test_case["alert_states"], test_case["include_warnings"]
    )

    expected_all_states = test_case["expected_all_states"]
    expected_alert_records = test_case["expected_alert_records"]

    all_states_sorted = sorted(
        all_states,
        key=lambda x: (
            x["microgrid_id"],
            x["component_id"],
            x["state_type"],
            x["start_time"],
        ),
    )
    expected_all_states_sorted = sorted(
        expected_all_states,
        key=lambda x: (
            x["microgrid_id"],
            x["component_id"],
            x["state_type"],
            x["start_time"],
        ),
    )

    alert_records_sorted = sorted(
        alert_records,
        key=lambda x: (
            x["microgrid_id"],
            x["component_id"],
            x["state_type"],
            x["start_time"],
        ),
    )
    expected_alert_records_sorted = sorted(
        expected_alert_records,
        key=lambda x: (
            x["microgrid_id"],
            x["component_id"],
            x["state_type"],
            x["start_time"],
        ),
    )

    assert all_states_sorted == expected_all_states_sorted
    assert alert_records_sorted == expected_alert_records_sorted


def test_frequenz_reporting_succeeds() -> None:  # TODO(cookiecutter): Remove
    """Test that the delete_me function succeeds."""
    assert delete_me() is True


def test_frequenz_reporting_fails() -> None:  # TODO(cookiecutter): Remove
    """Test that the delete_me function fails."""
    with pytest.raises(RuntimeError, match="This function should be removed!"):
        delete_me(blow_up=True)
