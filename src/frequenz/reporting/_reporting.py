# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""A highlevel interface for the reporting API."""

from collections import namedtuple
from datetime import datetime, timedelta

from frequenz.client.common.metric import Metric
from frequenz.client.reporting import ReportingApiClient

CumulativeEnergy = namedtuple(
    "CumulativeEnergy", ["start_time", "end_time", "consumption", "production"]
)
"""Type for cumulative energy consumption and production over a specified time."""


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
