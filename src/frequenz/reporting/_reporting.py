# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""A highlevel interface for the reporting API."""
import enum
import logging
from collections import namedtuple
from datetime import datetime, timedelta
from itertools import groupby
from typing import NamedTuple

from frequenz.client.common.enum_proto import enum_from_proto
from frequenz.client.common.metric import Metric
from frequenz.client.common.microgrid.components import (
    ComponentErrorCode,
    ComponentStateCode,
)
from frequenz.client.reporting import ReportingApiClient
from frequenz.client.reporting._types import MetricSample

_logger = logging.getLogger(__name__)

CumulativeEnergy = namedtuple(
    "CumulativeEnergy", ["start_time", "end_time", "consumption", "production"]
)


class StateRecord(NamedTuple):
    """A record of a component state change.

    A named tuple was chosen to allow safe access to the fields while keeping
    the simplicity of a tuple. This data type can be easily used to create a
    numpy array or a pandas DataFrame.
    """

    microgrid_id: int
    """The ID of the microgrid."""

    component_id: str
    """The ID of the component within the microgrid."""

    state_type: str
    """The type of the state (e.g., "state", "warning", "error")."""

    state_value: str
    """The value of the state (e.g., "ON", "OFF", "ERROR" etc.)."""

    start_time: datetime | None
    """The start time of the state change."""

    end_time: datetime | None
    """The end time of the state change."""


# pylint: disable-next=too-many-arguments
async def cumulative_energy(
    *,
    client: ReportingApiClient,
    microgrid_id: int,
    component_id: int,
    start_time: datetime,
    end_time: datetime,
    use_active_power: bool,
    resampling_period: timedelta | None,
) -> CumulativeEnergy:
    """
    Calculate the cumulative energy consumption and production over a specified time range.

    Args:
        client: The client used to fetch the metric samples from the Reporting API.
        microgrid_id: The ID of the microgrid.
        component_id: The ID of the component within the microgrid.
        start_time: The start date and time for the period.
        end_time: The end date and time for the period.
        use_active_power: If True, use the 'AC_ACTIVE_POWER' metric.
                          If False, use the 'AC_ACTIVE_ENERGY' metric.
        resampling_period: The period for resampling the data.If None, no resampling is applied.
    Returns:
        EnergyMetric: A named tuple with start_time, end_time, consumption, and production
        in Wh. Consumption has a positive sign, production has a negative sign.
    """
    metric = Metric.AC_ACTIVE_POWER if use_active_power else Metric.AC_ACTIVE_ENERGY

    metric_samples = [
        sample
        async for sample in client.receive_microgrid_components_data(
            microgrid_components=[(microgrid_id, [component_id])],
            metrics=metric,
            start_time=start_time,
            end_time=end_time,
            resampling_period=resampling_period,
        )
    ]

    if metric_samples:
        if use_active_power:
            # Convert power to energy if using AC_ACTIVE_POWER
            consumption = (
                sum(
                    m1.value * (m2.timestamp - m1.timestamp).total_seconds()
                    for m1, m2 in zip(metric_samples, metric_samples[1:])
                    if m1.value > 0
                )
                / 3600.0
            )  # Convert seconds to hours

            last_value_consumption = (
                metric_samples[-1].value
                * (end_time - metric_samples[-1].timestamp).total_seconds()
                if metric_samples[-1].value > 0
                else 0
            ) / 3600.0

            consumption += last_value_consumption

            production = (
                sum(
                    m1.value * (m2.timestamp - m1.timestamp).total_seconds()
                    for m1, m2 in zip(metric_samples, metric_samples[1:])
                    if m1.value < 0
                )
                / 3600.0
            )

            last_value_production = (
                metric_samples[-1].value
                * (end_time - metric_samples[-1].timestamp).total_seconds()
                if metric_samples[-1].value < 0
                else 0
            ) / 3600.0

            production += last_value_production

        else:
            # Fetch energy consumption and production metrics separately
            consumption_samples = [
                sample
                async for sample in client.receive_microgrid_components_data(
                    microgrid_components=[(microgrid_id, [component_id])],
                    metrics=Metric.AC_ACTIVE_ENERGY_CONSUMED,
                    start_time=start_time,
                    end_time=end_time,
                    resampling_period=resampling_period,
                )
            ]

            production_samples = [
                sample
                async for sample in client.receive_microgrid_components_data(
                    microgrid_components=[(microgrid_id, [component_id])],
                    metrics=Metric.AC_ACTIVE_ENERGY_DELIVERED,
                    start_time=start_time,
                    end_time=end_time,
                    resampling_period=resampling_period,
                )
            ]

            consumption = (
                sum(
                    max(0, m2.value - m1.value)
                    for m1, m2 in zip(consumption_samples, consumption_samples[1:])
                )
                if len(consumption_samples) > 1
                else float("nan")
            )

            production = (
                sum(
                    max(0, m2.value - m1.value)
                    for m1, m2 in zip(production_samples, production_samples[1:])
                )
                if len(production_samples) > 1
                else float("nan")
            )

    return CumulativeEnergy(
        start_time=start_time,
        end_time=end_time,
        consumption=consumption,
        production=production,
    )


# pylint: disable-next=too-many-arguments
async def fetch_and_extract_state_durations(
    *,
    client: ReportingApiClient,
    microgrid_components: list[tuple[int, list[int]]],
    metrics: list[Metric],
    start_time: datetime,
    end_time: datetime,
    resampling_period: timedelta | None,
    alert_states: list[ComponentStateCode],
    include_warnings: bool = True,
) -> tuple[list[StateRecord], list[StateRecord]]:
    """Fetch data using the Reporting API and extract state durations and alert records.

    Args:
        client: The client used to fetch the metric samples from the Reporting API.
        microgrid_components: List of tuples where each tuple contains microgrid
            ID and corresponding component IDs.
        metrics: List of metric names.
            NOTE: The service will support requesting states without metrics in
            the future and this argument will be removed.
        start_time: The start date and time for the period.
        end_time: The end date and time for the period.
        resampling_period: The period for resampling the data. If None, data
            will be returned in its original resolution
        alert_states: List of ComponentStateCode names that should trigger an alert.
        include_warnings: Whether to include warning states in the alert records.

    Returns:
        A tuple containing:
            - A list of StateRecord instances representing the state changes.
            - A list of StateRecord instances that match the alert criteria.
    """
    samples = await _fetch_component_data(
        client=client,
        microgrid_components=microgrid_components,
        metrics=metrics,
        start_time=start_time,
        end_time=end_time,
        resampling_period=resampling_period,
        include_states=True,
        include_bounds=False,
    )

    all_states = _extract_state_records(samples, include_warnings)
    alert_records = _filter_alerts(all_states, alert_states, include_warnings)
    return all_states, alert_records


def _extract_state_records(
    samples: list[MetricSample],
    include_warnings: bool,
) -> list[StateRecord]:
    """Extract state records from the provided samples.

    Args:
        samples: List of MetricSample instances containing the reporting data.
        include_warnings: Whether to include warning states in the alert records.

    Returns:
        A list of StateRecord instances representing the state changes.
    """
    alert_metrics = ["warning", "error"] if include_warnings else ["error"]
    state_metrics = ["state"] + alert_metrics
    filtered_samples = sorted(
        (s for s in samples if s.metric in state_metrics),
        key=lambda s: (s.microgrid_id, s.component_id, s.metric, s.timestamp),
    )

    if not filtered_samples:
        return []

    # Group samples by (microgrid_id, component_id, metric)
    all_states = []
    for key, group in groupby(
        filtered_samples, key=lambda s: (s.microgrid_id, s.component_id, s.metric)
    ):
        all_states.extend(_process_sample_group(key, list(group)))

    all_states.sort(key=lambda x: (x.microgrid_id, x.component_id, x.start_time))
    return all_states


def _process_sample_group(
    key: tuple[int, str, str],
    group_samples: list[MetricSample],
) -> list[StateRecord]:
    """Process samples for a single group to extract state durations.

    Args:
        key: Tuple containing microgrid ID, component ID, and metric.
        group_samples: List of samples for the group.

    Returns:
        A list of StateRecord instances representing the state changes.
    """
    mid, cid, metric = key
    if not group_samples:
        return []

    state_records = []
    current_state_value: float | None = None
    start_time: datetime | None = None
    enum_class = ComponentStateCode if metric == "state" else ComponentErrorCode

    for sample in group_samples:
        if current_state_value != sample.value:
            # Close previous state run
            if current_state_value is not None:
                state_records.append(
                    StateRecord(
                        microgrid_id=mid,
                        component_id=cid,
                        state_type=metric,
                        state_value=_resolve_enum_name(current_state_value, enum_class),
                        start_time=start_time,
                        end_time=sample.timestamp,
                    )
                )
            # Start new state run
            current_state_value = sample.value
            start_time = sample.timestamp

    # Close the last state run
    state_records.append(
        StateRecord(
            microgrid_id=mid,
            component_id=cid,
            state_type=metric,
            state_value=(
                _resolve_enum_name(current_state_value, enum_class)
                if current_state_value is not None
                else ""
            ),
            start_time=start_time,
            end_time=None,
        )
    )

    return state_records


def _resolve_enum_name(value: float, enum_class: type[enum.Enum]) -> str:
    """Resolve the name of an enum member from its integer value.

    Args:
        value: The integer value of the enum.
        enum_class: The enum class to convert the value to.

    Returns:
        The name of the enum member if it exists, otherwise the value as a string.
    """
    result = enum_from_proto(int(value), enum_class)
    if isinstance(result, int):
        _logger.warning(
            "Unknown enum value %s for %s, returning the integer value as a string.",
            value,
            enum_class.__name__,
        )
        return str(result)
    return result.name


def _filter_alerts(
    all_states: list[StateRecord],
    alert_states: list[ComponentStateCode],
    include_warnings: bool,
) -> list[StateRecord]:
    """Identify alert records from all states.

    Args:
        all_states: List of all state records.
        alert_states: List of ComponentStateCode names that should trigger an alert.
        include_warnings: Whether to include warning states in the alert records.

    Returns:
        A list of StateRecord instances that match the alert criteria.
    """
    alert_metrics = ["warning", "error"] if include_warnings else ["error"]
    _alert_state_names = {state.name for state in alert_states}
    return [
        state
        for state in all_states
        if (
            (state.state_type == "state" and state.state_value in _alert_state_names)
            or (state.state_type in alert_metrics)
        )
    ]


# pylint: disable-next=too-many-arguments
async def _fetch_component_data(
    *,
    client: ReportingApiClient,
    microgrid_components: list[tuple[int, list[int]]],
    metrics: list[Metric],
    start_time: datetime,
    end_time: datetime,
    resampling_period: timedelta | None,
    include_states: bool = False,
    include_bounds: bool = False,
) -> list[MetricSample]:
    """Fetch component data from the Reporting API.

    Args:
        client: The client used to fetch the metric samples from the Reporting API.
        microgrid_components: List of tuples where each tuple contains
            microgrid ID and corresponding component IDs.
        metrics: List of metric names.
        start_time: The start date and time for the period.
        end_time: The end date and time for the period.
        resampling_period: The period for resampling the data. If None, data
            will be returned in its original resolution
        include_states: Whether to include the state data.
        include_bounds: Whether to include the bound data.

    Returns:
        List of MetricSample instances containing the reporting data.
    """
    return [
        sample
        async for sample in client.receive_microgrid_components_data(
            microgrid_components=microgrid_components,
            metrics=metrics,
            start_time=start_time,
            end_time=end_time,
            resampling_period=resampling_period,
            include_states=include_states,
            include_bounds=include_bounds,
        )
    ]
