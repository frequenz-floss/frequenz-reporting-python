# Reporting Highlevel Interface

[![Build Status](https://github.com/frequenz-floss/frequenz-reporting-python/actions/workflows/ci.yaml/badge.svg)](https://github.com/frequenz-floss/frequenz-reporting-python/actions/workflows/ci.yaml)
[![PyPI Package](https://img.shields.io/pypi/v/frequenz-reporting-python)](https://pypi.org/project/frequenz-reporting-python/)
[![Docs](https://img.shields.io/badge/docs-latest-informational)](https://frequenz-floss.github.io/frequenz-reporting-python/)

## Introduction

A highlevel interface for the reporting API

## Supported Platforms

The following platforms are officially supported (tested):

- **Python:** 3.11
- **Operating System:** Ubuntu Linux 20.04
- **Architectures:** amd64, arm64

## Contributing

If you want to know how to build this project and contribute to it, please
check out the [Contributing Guide](CONTRIBUTING.md).


### Installation

```bash
# Choose the version you want to install
VERSION=0.3.0
pip install frequenz-reporting-python==$VERSION
```


### Initialize the client

```python
from datetime import datetime

from frequenz.client.common.metric import Metric
from frequenz.client.reporting import ReportingApiClient
from frequenz.reporting._reporting import cumulative_energy

# Change server address
SERVICE_ADDRESS = "grpc://replace-this-with-your-server-url:port"
API_KEY = open('api_key.txt').read().strip()
client = ReportingApiClient(service_address=SERVICE_ADDRESS, key=API_KEY)
```

### Calculate cumulative energy for a single microgrid and component:

If the component does not measure `Metric.AC_ACTIVE_ENERGY`, set `use_active_power=True`
to utilize `Metric.AC_ACTIVE_POWER` instead.

A resampling period can be set that alters how NaNs are handled, resulting in varying
results. NaN values are ignored in sums, which may lead to significant data loss
if many are present in the raw data. There is no universally correct method for
handling NaNs, as their causes can vary.

```python
energy_reading = await cumulative_energy(
			client=client,
                        microgrid_id=1,
                        component_id=100,
                        start_time=datetime.fromisoformat("2024-09-01T00:00:00"),
                        end_time=datetime.fromisoformat("2024-09-30T00:00:00"),
                        use_active_power=True,
                        resampling_period=timedelta(seconds=10),
    )

print(energy_reading)
```
