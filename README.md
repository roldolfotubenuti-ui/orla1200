<p align="center">
  <img src="assets/icon.ico" alt="TikTok Scheduler" width="80" />
</p>

<h1 align="center">TikTok Scheduler</h1>

<p align="center">
  A Windows desktop application for scheduling and uploading TikTok videos in bulk<br/>
  using a real Chromium browser driven by Playwright automation.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/PyQt6-6.6+-41CD52?logo=qt&logoColor=white" alt="PyQt6" />
  <img src="https://img.shields.io/badge/Playwright-1.40+-2EAD33?logo=playwright&logoColor=white" alt="Playwright" />
  <img src="https://img.shields.io/badge/Pydantic-2.0+-E92063?logo=pydantic&logoColor=white" alt="Pydantic" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License" />
</p>

## Overview

TikTok Scheduler is a PyQt6 desktop client built for creators and operators who need a repeatable workflow for preparing uploads, generating schedule windows, and managing multiple TikTok accounts. The application automates the TikTok web upload flow through Playwright while keeping account cookies, scheduled uploads, published history, and UI state organized locally.

## Highlights

- Bulk upload preparation from local `.mp4` folders
- Configurable scheduling windows with date and time rules
- Cookie-based multi-account management
- Published and scheduled file tracking per account
- Modern desktop UI with multiple application themes
- Rich terminal logging for execution feedback
- Optional headless browser execution
- Copyright and content quality feedback surfaced during upload

## Requirements

- Python 3.10 or newer
- Windows 10 or Windows 11
- Chromium installed through Playwright

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/davins/tiktok-scheduler.git
cd tiktok-scheduler
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install the Playwright browser runtime

```bash
python -m playwright install chromium
```

> Tip: `RUN.bat` can bootstrap dependencies and launch the application automatically.

## Running the application

### Option A: use the Windows launcher

Double-click `RUN.bat` from the project root.

### Option B: run from a terminal

```bash
python main.py
```

## Account setup

TikTok Scheduler uses exported browser cookies instead of username/password login inside the app.

1. Sign in to TikTok Creator in your browser.
2. Export cookies as JSON with a browser cookie extension.
3. Open the application and go to the Accounts tab.
4. Add the TikTok username and paste the cookie JSON.
5. Save the account for future scheduling sessions.

An example payload is included in `example_cookie.json`.

## Configuration

Runtime options are loaded from `config.json`.

| Key | Description | Default |
| --- | --- | --- |
| `windowSize` | Initial application window size | `1200 x 800` |
| `minWindowSize` | Minimum configured window size | `900 x 600` |
| `theme` | Initial theme name | `system` |
| `primaryColor` | Accent color used by the base palette | `#1E66FF` |
| `headlessDefault` | Default browser visibility mode | `true` |
| `logLevel` | Logging verbosity | `INFO` |
| `scheduleRules.minOffsetMinutes` | Minimum delay before a schedule can start | `15` |
| `scheduleRules.maxOffsetMonths` | Maximum schedule range | `1` |
| `scheduleRules.minuteStep` | Minute rounding step | `5` |

## Project structure

```text
tiktok-scheduler/
|-- main.py
|-- config.json
|-- setup.py
|-- requirements.txt
|-- RUN.bat
|-- assets/
|-- core/
|   |-- browser_manager.py
|   |-- config_manager.py
|   |-- cookie_manager.py
|   |-- dom_handler.py
|   |-- logger_manager.py
|   |-- schedule_rule_engine.py
|   |-- scheduler.py
|   `-- uploader.py
|-- gui/
|   |-- controller.py
|   |-- main_window.py
|   |-- components/
|   |-- controllers/
|   |-- dialogs/
|   |-- layouts/
|   |-- pages/
|   |-- services/
|   |-- tables/
|   |-- theme/
|   `-- widgets/
|-- storage/
|   |-- publishes/
|   `-- schedules/
|-- cookies/
`-- utils/
```

## Notes

- Storage and cookie data are intended to remain local to the workstation.
- The GUI and core upload logic are separated so UI changes do not require rewriting the automation pipeline.
- Published records are stored under `storage/publishes/` and scheduled records under `storage/schedules/`.

## License

This project is licensed under the [MIT License](LICENSE).
