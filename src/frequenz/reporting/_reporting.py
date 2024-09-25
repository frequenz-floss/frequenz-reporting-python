# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""A highlevel interface for the reporting API."""

from collections import namedtuple
from datetime import datetime

from frequenz.client.common.metric import Metric
from frequenz.client.reporting import ReportingApiClient

CumulativeEnergy = namedtuple(
    "CumulativeEnergy", ["start_time", "end_time", "consumption", "production"]
)
"""Type for cumulative energy consumption and production over a specified time."""


# pylint: disable-next=too-many-arguments
async def cumulative_energy(
    client: ReportingApiClient,
    microgrid_id: int,
    component_id: int,
    start_time: datetime,
    end_time: datetime,
    use_active_power: bool,
    resolution: int | None = None,
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
        resolution: The resampling resolution for the data, represented in seconds.
                    If None, no resampling is applied.
    Returns:
        EnergyMetric: A named tuple with start_time, end_time, consumption, and production
        in Wh. Consumption has a positive sign, production has a negative sign.
    """
    metric = Metric.AC_ACTIVE_POWER if use_active_power else Metric.AC_ACTIVE_ENERGY

    metric_samples = [
        sample
        async for sample in client.list_microgrid_components_data(
            microgrid_components=[(microgrid_id, [component_id])],
            metrics=metric,
            start_dt=start_time,
            end_dt=end_time,
            resolution=resolution,
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
            # Directly use energy values if using AC_ACTIVE_ENERGY
            consumption = sum(
                m2.value - m1.value
                for m1, m2 in zip(metric_samples, metric_samples[1:])
                if m2.value - m1.value > 0
            )
            production = sum(
                m2.value - m1.value
                for m1, m2 in zip(metric_samples, metric_samples[1:])
                if m2.value - m1.value < 0
            )

            if len(metric_samples) > 1:
                last_value_diff = metric_samples[-1].value - metric_samples[-2].value
                if last_value_diff > 0:
                    consumption += last_value_diff
                elif last_value_diff < 0:
                    production += last_value_diff
    else:
        consumption = production = 0.0

    return CumulativeEnergy(
        start_time=start_time,
        end_time=end_time,
        consumption=consumption,
        production=production,
    )
