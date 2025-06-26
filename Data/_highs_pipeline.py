#!/usr/bin/env python3
"""
Highs Pipeline – unified Screener downloader + ETL
=================================================
Runs end‑to‑end in one command:
  1. Logs in to Screener.in and downloads the configured screen (.csv or .xlsx);
  2. Loads data into an SQLite table `highs`, capturing first‑seen dates / market‑caps;
  3. Archives the processed file to keep the download directory clean.

Everything is driven by **config.ini** (sample below). All paths are resolved
relative to this script unless they are absolute.

```
[credentials]
username = YOUR_SCREENNER_USERNAME
password = YOUR_SCREENNER_PASSWORD

[screen]
url   = https://www.screener.in/screens/2702802/52weekhigh5/
# Escape percent signs as %% in configparser
title = 52WeekHigh5%%

[paths]
download_dir = ./screener_downloads
archive_dir  = ./__screener_downloads
db_path      = ./highs.db

[general]
headless = true  # set false to watch Selenium
```

Usage
-----
```bash
pip install selenium pandas
python highs_pipeline.py --verbose   # uses ./config.ini
```
"""
from __future__ import annotations

import argparse
import configparser
import contextlib
import datetime as _dt
import logging
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
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    username: str
    password: str
    screen_url: str
    screen_title: str
    download_dir: Path
    archive_dir: Path
    db_path: Path
    headless: bool = True

    def ensure_dirs(self) -> None:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Selenium downloader
# ---------------------------------------------------------------------------

class ScreenerDownloader:
    def __init__(self, settings: Settings, logger: logging.Logger):
        self.settings = settings
        self.logger = logger
        self.driver: Optional[webdriver.Firefox] = None
        self.wait: Optional[WebDriverWait] = None

    # Public ---------------------------------------------------------------

    def download(self) -> Path:
        self.logger.info("Starting Screener download …")
        self._start_driver()
        try:
            self._login()
            csv_path = self._trigger_download()
        finally:
            with contextlib.suppress(Exception):
                if self.driver:
                    self.driver.quit()
        self.logger.info("Download complete → %s", csv_path)
        return csv_path

    # Internal helpers -----------------------------------------------------

    def _start_driver(self) -> None:
        options = Options()
        if self.settings.headless:
            options.add_argument("--headless")
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", str(self.settings.download_dir))
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/csv,application/vnd.ms-excel,application/octet-stream")
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.download.manager.closeWhenDone", True)
        self.driver = webdriver.Firefox(options=options)
        self.wait = WebDriverWait(self.driver, 20)

    def _login(self) -> None:
        assert self.driver and self.wait
        self.driver.get("https://www.screener.in/login/")
        self.wait.until(EC.presence_of_element_located((By.ID, "id_username")))
        self.driver.find_element(By.ID, "id_username").send_keys(self.settings.username)
        self.driver.find_element(By.ID, "id_password").send_keys(self.settings.password + Keys.RETURN)
        self.wait.until(lambda d: "/login" not in d.current_url)
        self.logger.debug("Logged in")

    def _trigger_download(self) -> Path:
        """Navigate to the screen page and trigger an export.

        The logic is tolerant to UI changes:
          • If we land on the list of screens, clicks the tile.
          • Then looks for any link/button with text Export/Download.
          • Falls back to a form “export” button if needed.
          • Waits **up to 120 s** for .csv or .xlsx to appear.
        """
        assert self.driver and self.wait
        self.driver.get(self.settings.screen_url)

        # 1️⃣ Click tile if it exists
        try:
            tile = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//*[text()[contains(., '{self.settings.screen_title}')]]"))
            )
            tile.click()
            self.logger.debug("Opened screen tile %s", self.settings.screen_title)
        except Exception:
            self.logger.debug("Screen tile not found — assuming already on detail page")

        # 2️⃣ Click any Export/Download trigger
        click_xpaths = [
            "//a[contains(translate(., 'EXPORTDOWNLOAD', 'exportdownload'), 'export')]",
            "//a[contains(translate(., 'EXPORTDOWNLOAD', 'exportdownload'), 'download')]",
            "//button[contains(translate(., 'EXPORTDOWNLOAD', 'exportdownload'), 'export')]",
            "//button[contains(translate(., 'EXPORTDOWNLOAD', 'exportdownload'), 'download')]",
            "//form[contains(@action, '/export') or contains(@action,'/download')]//button",
        ]
        clicked = False
        for xp in click_xpaths:
            with contextlib.suppress(Exception):
                elem = self.wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
                elem.click()
                self.logger.debug("Clicked export element – xpath: %s", xp)
                clicked = True
                break
        if not clicked:
            raise RuntimeError("Could not locate an Export/Download control on Screener page")

        # 3️⃣ Wait up to 120 s for a download (csv/xlsx)
        def _download_ready(_):
            return any(f.suffix.lower() in (".csv", ".xlsx") for f in self.settings.download_dir.iterdir())

        self.wait._timeout = 120
        self.wait.until(_download_ready)

        latest_file = max(
            (f for f in self.settings.download_dir.iterdir() if f.suffix.lower() in (".csv", ".xlsx")),
            key=lambda p: p.stat().st_ctime,
        )
        dated_name = self.settings.download_dir / f"screener_{_dt.date.today():%Y-%m-%d}{latest_file.suffix}"
        latest_file.rename(dated_name)
        return dated_name


# ---------------------------------------------------------------------------
# ETL loader – identical behaviour to original etl.py
# ---------------------------------------------------------------------------

class HighsIngestor:
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
        sqlite3.register_converter("DATE", lambda s: _dt.date.fromisoformat(s.decode()))

    # -------------------------------------------------------------------
    def ingest(self, csv_path: Path):
        self.logger.info("Ingesting %s …", csv_path.name)
        with sqlite3.connect(self.settings.db_path, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            self._create_table(conn)
            self._ingest_file(conn, csv_path)

    # -------------------------------------------------------------------
    @staticmethod
    def _create_table(conn: sqlite3.Connection):
        conn.execute(HighsIngestor.CREATE_TABLE_SQL)
        conn.commit()

    def _ingest_file(self, conn: sqlite3.Connection, csv_path: Path):
        df = pd.read_csv(csv_path, engine="python") if csv_path.suffix == ".csv" else pd.read_excel(csv_path)
        df.columns = df.columns.str.strip()
        required = {"Name", "Market Capitalization"}
        if not required.issubset(df.columns):
            self.logger.warning("Missing required columns in %s – skipped", csv_path.name)
            return
        load_date = _dt.date.fromisoformat(csv_path.stem.split("_")[-1])
        df["date"] = load_date

        cur = conn.cursor()
        inserted = 0
        for _, row in df.iterrows():
            name = row.get("Name")
            if pd.isna(name):
                continue
            try:
                mcap = float(row["Market Capitalization"])
            except Exception:
                continue
            cur.execute("SELECT MIN(date), MIN(market_cap) FROM highs WHERE name = ?", (name,))
            first_date, first_mcap = cur.fetchone() or (None, None)
            if first_date is None:
                first_date, first_mcap = load_date, mcap
            conn.execute(
                "INSERT INTO highs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    load_date,
                    name,
                    row.get("BSE Code"),
                    row.get("NSE Code"),
                    row.get("Industry"),
                    row.get("Current Price"),
                    mcap,
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
                    first_date,
                    first_mcap,
                ),
            )
            inserted += 1
        conn.commit()
        self.logger.info("Inserted %d rows from %s", inserted, csv_path.name)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def archive_file(src: Path, dest_dir: Path, logger: logging.Logger) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.move(src, dest)
    logger.info("Archived %s → %s", src.name, dest)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.ini"))
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def _load_settings(path: Path) -> Settings:
    if not path.exists():
        raise FileNotFoundError(f"No config file: {path}")
    cp = configparser.ConfigParser()
    cp.read(path)
    def get(section: str, key: str, fallback: Optional[str] = None) -> str:
        if cp.has_option(section, key):
            return cp.get(section, key)
        if fallback is not None:
            return fallback
        raise KeyError(f"Missing [{section}] {key}")
    return Settings(
        username=get("credentials", "username"),
        password=get("credentials", "password"),
        screen_url=get("screen", "url"),
        screen_title=get("screen", "title"),
        download_dir=Path(get("paths", "download_dir", "./screener_downloads")).expanduser().resolve(),
        archive_dir=Path(get("paths", "archive_dir", "./__screener_downloads")).expanduser().resolve(),
        db_path=Path(get("paths", "db_path", "./highs.db")).expanduser().resolve(),
        headless=cp.getboolean("general", "headless", fallback=True),
    )


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
        settings.ensure_dirs()
    except Exception as e:
        logger.error("Failed to load settings: %s", e)
        traceback.print_exc()
        sys.exit(1)

    try:
        downloader = ScreenerDownloader(settings, logger)
        csv_file = downloader.download()
    except Exception as e:
        logger.error("Download step failed: %s", e)
        traceback.print_exc()
        sys.exit(2)

    try:
        HighsIngestor(settings, logger).ingest(csv_file)
    except Exception as e:
        logger.error("ETL step failed: %s", e)
        traceback.print_exc()
        sys.exit(3)

    try:
        archive_file(csv_file, settings.archive_dir, logger)
    except Exception as e:
        logger.warning("Archiving failed: %s", e)
        traceback.print_exc()

    logger.info("✓ All steps completed successfully.")


if __name__ == "__main__":
    main()
