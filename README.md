# Store Data Extractor

A web data extractor designed to monitor online stores and track product updates in real-time.

## Project Information

- **Version**: 1.1.0
- **Author**: [yumeangelica](https://github.com/yumeangelica)
- **License**: [CC BY-NC-ND 4.0](LICENSE.txt)

## Project Overview

The data extractor monitors specified online stores, tracks products and their current prices, and stores product state in a database.

Key features:

- Automated monitoring of specified online stores
- Product tracking and price change detection
- New item notifications via console output
- Database storage for historical data

## Technical Implementation

### Project Structure

```
store_data_extractor/
├── data/
│   ├── store_db.sqlite                 # SQLite database for store data
├── store_data_extractor/
│   ├── config/                         # Configuration files for store data extractor
│   │   ├── last_user_agent_index.txt   # User agent index tracking
│   │   ├── stores.json                 # Store configurations
│   │   └── user_agents.txt             # List of user agents
│   ├── src/                            # Core functionality for data extraction
│   │   ├── data_extractor.py           # Data extraction logic
│   │   ├── user_agent_manager.py       # User agent rotation
│   │   └── store_database.py           # Database logic for stores
│   ├── store_manager.py                # Store monitor entry point
│   └── store_types.py                  # Type definitions for store data extractor
├── utils/
│   ├── helpers.py                      # Helper functions
│   └── logger.py                       # Logging functionality
├── venv/                               # Python virtual environment
├── .env                                # Environment variables
├── .gitignore                          # Git ignore file
├── LICENSE.txt                         # Project license
├── README.md                           # Project documentation
├── requirements.txt                    # Python dependencies
├── run.py                              # Script for running the store monitor
└── main_file.py                        # Main script file
```

### Required Configuration Files

The project needs these configuration files in store_data_extractor/config/:

#### stores.json (required)

- Store configurations and monitoring schedules. Determines which stores to monitor and how often.
- Must be created manually
- Intentionally ignored by Git and Docker builds; provide it locally or mount it into runtime environments.
- Defines store URLs, selectors, fetch options, and update intervals
- Selectors can be XPath or CSS. XPath is tried first by default. Use `xpath:` or `css:` prefixes to force a selector type.

Structure:
stores.json

```json
[
  {
    "name": "store_name",
    "name_format": "Formatted Store Name",
    "run_on_start": true,
    "options": {
      "base_url": "base_url_for_data_extraction",
      "site_main_url": "main_site_url",
      "item_container_selector": "selector_for_item_containers",
      "item_name_selector": "selector_for_item_names",
      "item_price_selectors": [
        {
          "currency": "currency_code",
          "selector": "selector_for_price"
        }
      ],
      "item_link_selector": "selector_for_item_links",
      "item_image_selector": "selector_for_item_images",
      "sold_out_selector": "selector_for_sold_out_items",
      "next_page_selector": "selector_for_next_page",
      "next_page_selector_text": "Text_for_next_page_element",
      "next_page_attribute": "attribute_containing_next_page_url",
      "delay_between_requests": "time_in_seconds_between_requests",
      "encoding": "character_encoding_used",
      "fetch_backend": "auto",
      "curl_impersonate": "chrome",
      "request_timeout": 30,
      "proxy_url": "optional_proxy_url",
      "request_headers": {
        "Header-Name": "optional_header_value"
      }
    },
    "schedule": {
      "minutes": "list_of_minutes_for_execution",
      "hours": "list_of_hours_or_*",
      "days": "list_of_days_or_*",
      "months": "list_of_months_or_*",
      "years": "list_of_years_or_*"
    }
  }
]
```

Explanation:

- `name`: Unique identifier for the store.
- `name_format`: User-friendly name for the store.
- `run_on_start`: Optional. If `true`, fetch this store once immediately when the process starts, then continue normal scheduling.
- `options`: Configuration options for data extraction.
  - `base_url`: Starting URL for extracting data.
  - `site_main_url`: Main website URL.
  - `item_container_selector`: Selector for locating items.
  - `item_name_selector`: Selector for item names.
  - `item_price_selectors`: List of price selectors with currency type.
  - `item_link_selector`: Selector for item links.
  - `item_image_selector`: Selector for item images.
  - `sold_out_selector`: Selector to identify sold-out items.
  - `next_page_selector`: Selector for pagination element.
  - `next_page_selector_text`: Text identifying the next page link.
  - `next_page_attribute`: Attribute containing the next page URL.
  - `delay_between_requests`: Delay (in seconds) between requests.
  - `encoding`: Website's character encoding.
  - `fetch_backend`: Optional. `auto` tries the normal async HTTP client first and falls back to the browser-fingerprint client. `aiohttp` or `curl_cffi` can be used to force one backend.
  - `curl_impersonate`: Optional browser profile for the `curl_cffi` backend. Defaults to `chrome`.
  - `request_timeout`: Optional request timeout in seconds.
  - `proxy_url`: Optional proxy URL used by HTTP fetches.
  - `request_headers`: Optional extra headers merged into the default browser-like request headers.
- `schedule`: Monitoring schedule.
  - `minutes`: Minute intervals.
  - `hours`: Hour intervals or `*` for every hour.
  - `days`: Day intervals or `*` for every day.
  - `months`: Month intervals or `*` for every month.
  - `years`: Year intervals or `*` for every year.

#### user_agents.txt (required)

- List of browser user agents for web data extraction
- Must be created manually
- One user agent per line
- Used to prevent request blocking

#### last_user_agent_index.txt (auto-generated)

- Tracks the current user agent rotation
- Created automatically by the system
- Do not modify manually

### Running

Create a virtual environment, install dependencies, and start the scheduler:

```bash
python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
venv/bin/python run.py
```

The scheduler checks store schedules once per minute. Stores with `run_on_start: true` are fetched immediately on startup.

### Store database

SQLite database is automatically created in the `data/` directory, storing:

- Store information
- Product details
- Current price data
- Update timestamps

The application logs the SQLite database path and a sync summary for each store run.

### Technology Stack

- Python 3.13
- SQLite3 for data storage
- Lxml for web data extraction
- aiohttp for async HTTP requests
- curl_cffi for sites that require browser-like TLS fingerprinting
- Additional dependencies listed in requirements.txt

## License and Copyright

Copyright (c) 2024-present yumeangelica. All rights reserved.

This project is protected under Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License (CC BY-NC-ND 4.0).

For complete license terms, see LICENSE.txt.
