#!/usr/bin/env python3
"""
Highs Pipeline
==============
A single, modular, and configurable script that
  1. Logs in to Screener.in, downloads the configured custom screen as CSV;
  2. Ingests the CSV into an SQLite database, tracking first-seen dates and
     market-caps (same logic as the original *etl.py*);
  3. Archives the processed CSV to an "archive" directory so it is ingested
     only once.

Configuration is read from **config.ini** (sample below) but can be overridden
from the command‑line. All paths are resolved relative to the location of this
script unless absolute paths are supplied.

```
[credentials]
username = YOUR_SCREENNER_USERNAME
password = YOUR_SCREENNER_PASSWORD

[screen]
url   = https://www.screener.in/screens/2702802/52weekhigh5/
# The visible title text of the screen on the "My Screens" page. Escape % as %%
# e.g. 52WeekHigh5%%
title = 52WeekHigh5%%

[paths]
# where Screener downloads go
download_dir = ./screener_downloads
# where processed CSVs are parked after ingestion
archive_dir  = ./__screener_downloads
# SQLite database file
db_path      = ./highs.db

[general]
# run Firefox in headless mode? (true/false)
headless = true
```

**Usage**
---------
```bash
pip install selenium pandas
python highs_pipeline.py            # uses ./config.ini
python highs_pipeline.py --config /path/to/custom.ini --verbose
```

The script exits with a non‑zero status code if any step fails, making it easy
to schedule via cron/Task Scheduler/GitHub Actions.
"""
from __future__ import annotations

import argparse
import configparser
import contextlib
import datetime as _dt
import logging
import os
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------------------------------------------------------------------
# Settings & configuration helpers
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    """Runtime configuration loaded from *config.ini* or CLI overrides."""

    username: str
    password: str
    screen_url: str
    screen_title: str
    download_dir: Path
    archive_dir: Path
    db_path: Path
    headless: bool = True

    def ensure_dirs(self) -> None:
        """Create download & archive dirs if they do not yet exist."""
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Selenium helpers (Download phase)
# ---------------------------------------------------------------------------

class ScreenerDownloader:
    """Handles browser automation for downloading a custom Screener screen."""

    def __init__(self, settings: Settings, logger: logging.Logger):
        self.settings = settings
        self.logger = logger
        self.driver: Optional[webdriver.Firefox] = None
        self.wait: Optional[WebDriverWait] = None

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ public API ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def download(self) -> Path:
        """Return path to the freshly downloaded CSV."""
        self.logger.info("Starting Screener download step …")
        self._start_driver()
        try:
            self._login()
            csv_path = self._trigger_download()
        finally:
            with contextlib.suppress(Exception):
                if self.driver:
                    self.driver.quit()
        self.logger.info("Screener download step completed → %s", csv_path)
        return csv_path

    # ~~~~~~~~~~~~~~~~~~~~~~~~~ internal helpers ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _start_driver(self) -> None:
        options = Options()
        if self.settings.headless:
            options.add_argument("--headless")

        # configure automatic downloads
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", str(self.settings.download_dir))
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/csv,application/octet-stream")
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.download.manager.closeWhenDone", True)
        options.set_preference("pdfjs.disabled", True)

        self.driver = webdriver.Firefox(options=options)
        self.wait = WebDriverWait(self.driver, 20)

    def _login(self) -> None:
        assert self.driver and self.wait
        self.logger.debug("Logging in as %s", self.settings.username)
        self.driver.get("https://www.screener.in/login/")
        self.wait.until(EC.presence_of_element_located((By.ID, "id_username")))
        self.driver.find_element(By.ID, "id_username").send_keys(self.settings.username)
        self.driver.find_element(By.ID, "id_password").send_keys(self.settings.password + Keys.RETURN)
        # Wait until we are redirected away from the login page
        self.wait.until(lambda d: "/login" not in d.current_url)
        self.logger.info("Logged in successfully.")

    def _trigger_download(self) -> Path:
        """Navigate to the screen page and export the CSV."""
        assert self.driver and self.wait
        self.logger.debug("Opening screen URL %s", self.settings.screen_url)
        self.driver.get(self.settings.screen_url)

        # 1️⃣ If the URL brought us to the My Screens overview, click the tile.
        #    If the tile isn't present (because we're already on the screen
        #    detail page), we just continue — this avoids the NoSuchElementError
        #    the user saw.
        try:
            tile_xpath = f"//*[contains(normalize-space(), '{self.settings.screen_title}')]"
            tile = self.wait.until(EC.element_to_be_clickable((By.XPATH, tile_xpath)))
            tile.click()
            self.logger.debug("Clicked tile '%s'", self.settings.screen_title)
        except Exception:
            self.logger.debug("Screen tile not found — assuming we are already on the detail page")

        # 2️⃣ Trigger the export.  Screener occasionally renders either
        #    (a) an <a> with text "Export", or (b) a form with submit button.
        #    We'll try both.
        with contextlib.suppress(Exception):
            export_link = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Export')]")))
            export_link.click()
            self.logger.debug("Clicked Export link")

        if not any(f.suffix == ".csv" for f in self.settings.download_dir.iterdir()):
            # If clicking the link didn't start the download, look for form
            export_form = self.wait.until(EC.presence_of_element_located((By.XPATH, "//form[contains(@action, '/api/export/screen/')]")))
            submit_btn = export_form.find_element(By.XPATH, ".//button[@type='submit' or contains(., 'Submit')]")
            submit_btn.click()
            self.logger.debug("Submitted export form")

        # 3️⃣ Wait for a CSV to appear in the download directory
        self.wait.until(lambda _: any(f.suffix == ".csv" for f in self.settings.download_dir.iterdir()))
        latest_file = max((f for f in self.settings.download_dir.glob("*.csv")), key=lambda p: p.stat().st_ctime)
        dated_name = self.settings.download_dir / f"screener_{_dt.date.today():%Y-%m-%d}.csv"
        latest_file.rename(dated_name)
        return dated_name


# ---------------------------------------------------------------------------
# ETL helpers (Ingestion phase)
# ---------------------------------------------------------------------------

class HighsIngestor:
    """Load Screener CSVs into an SQLite DB, recording first‑seen stats."""

    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS highs (
        date DATE,
        name TEXT,
        bse_code TEXT,
        nse_code TEXT,
        industry TEXT,
        current_price REAL,
        market_cap REAL,
        sales REAL,
        operating_profit REAL,
        opm REAL,
        opm_last_year REAL,
        pe REAL,
        pbv REAL,
        peg REAL,
        roa REAL,
        debt_to_equity REAL,
        roe REAL,
        working_capital REAL,
        other_income REAL,
        down_from_52w_high REAL,
        first_seen_date DATE,
        first_market_cap REAL
    )"""

    def __init__(self, settings: Settings, logger: logging.Logger):
        self.settings = settings
        self.logger = logger
        sqlite3.register_adapter(_dt.date, lambda d: d.isoformat())
        sqlite3.register_converter("DATE", lambda s: _dt.date.fromisoformat(s.decode("utf-8")))

    def ingest(self, csv_path: Path) -> None:
        """Read *csv_path* and append rows into the highs table."""
        self.logger.info("Ingesting %s into %s", csv_path.name, self.settings.db_path)
        with sqlite3.connect(self.settings.db_path, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            self._create_table(conn)
            self._ingest_file(conn, csv_path)

    @staticmethod
    def _create_table(conn: sqlite3.Connection):
        conn.execute(HighsIngestor.CREATE_TABLE_SQL)
        conn.commit()

    def _ingest_file(self, conn: sqlite3.Connection, csv_path: Path):
        df = pd.read_csv(csv_path, engine="python")
        df.columns = df.columns.str.strip()
        required = {"Name", "Market Capitalization"}
        if not required.issubset(df.columns):
            self.logger.warning("%s missing %s — skipped", csv_path.name, required - set(df.columns))
            return

        load_date = _dt.date.fromisoformat(csv_path.stem.split("_")[-1])
        df["date"] = load_date

        cur = conn.cursor()
        inserted_rows = 0
        for _, row in df.iterrows():
            name = row.get("Name")
            if pd.isna(name):
                continue
            try:
                market_cap = float(row["Market Capitalization"])
            except (ValueError, TypeError):
                continue

            cur.execute("SELECT MIN(date), MIN(market_cap) FROM highs WHERE name = ?", (name,))
            first_seen_date, first_market_cap = cur.fetchone() or (None, None)
            if first_seen_date is None:
                first_seen_date, first_market_cap = load_date, market_cap

            conn.execute(
                """INSERT INTO highs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    load_date,
                    name,
                    row.get("BSE Code"),
                    row.get("NSE Code"),
                    row.get("Industry"),
                    row.get("Current Price"),
                    market_cap,
                    row.get("Sales"),
                    row.get("Operating profit"),
                    row.get("OPM"),
                    row.get("OPM last year"),
                    row.get("Price to Earning"),
                    row.get("Price to book value"),
                    row.get("PEG Ratio"),
                    row.get("Return on assets"),
                    row.get("Debt to equity"),
                    row.get("Return on equity"),
                    row.get("Working capital"),
                    row.get("Other income"),
                    row.get("Down from 52w high"),
                    first_seen_date,
                    first_market_cap,
                ),
            )
            inserted_rows += 1

        conn.commit()
        self.logger.info("Inserted %d rows from %s", inserted_rows, csv_path.name)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def archive_file(src: Path, dest_dir: Path, logger: logging.Logger) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.move(src, dest)
    logger.info("Archived %s → %s", src, dest)


# ---------------------------------------------------------------------------
# Orchestration (main entry point)
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download & ingest Screener 52-week-highs screen")
    p.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("config.ini"),
        help="Path to configuration file (default: ./config.ini)",
    )
    p.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return p.parse_args()


def _load_settings(cfg_path: Path) -> Settings:
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file {cfg_path} does not exist")

    cp = configparser.ConfigParser()
    cp.read(cfg_path)

    def _g(section: str, key: str, default: Optional[str] = None) -> str:
        if cp.has_option(section, key):
            return cp.get(section, key)
        if default is not None:
            return default
        raise KeyError(f"Missing [{section}] {key} in {cfg_path}")

    settings = Settings(
        username=_g("credentials", "username"),
        password=_g("credentials", "password"),
        screen_url=_g("screen", "url"),
        screen_title=_g("screen", "title"),
        download_dir=Path(_g("paths", "download_dir", "./screener_downloads")).expanduser().resolve(),
        archive_dir=Path(_g("paths", "archive_dir", "./__screener_downloads")).expanduser().resolve(),
        db_path=Path(_g("paths", "db_path", "./highs.db")).expanduser().resolve(),
        headless=cp.getboolean("general", "headless", fallback=True),
    )
    settings.ensure_dirs()
    return settings


def main() -> None:
    import traceback

    args = _parse_args()

    logging.basicConfig(
        format="%(levelname)s | %(asctime)s | %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("highs-pipeline")

    try:
        settings = _load_settings(args.config)
    except Exception as exc:
        logger.error("Failed loading configuration: %s", exc)
        traceback.print_exc()
        sys.exit(1)

    try:
        downloader = ScreenerDownloader(settings, logger)
        csv_file = downloader.download()
    except Exception as exc:
        logger.error("Download step failed: %s", exc)
        traceback.print_exc()
        sys.exit(2)

    try:
        HighsIngestor(settings, logger).ingest(csv_file)
    except Exception as exc:
        logger.error("ETL step failed: %s", exc)
        traceback.print_exc()
        sys.exit(3)

    try:
        archive_file(csv_file, settings.archive_dir, logger)
    except Exception as exc:
        logger.warning("Archiving failed (continuing): %s", exc)
        traceback.print_exc()

    logger.info("All steps completed successfully.")


if __name__ == "__main__":
    main()
