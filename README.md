# Facebook Marketplace Scraper – Newest Listings

![Python Version](https://img.shields.io/badge/python-3.9%2B-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

> **Automatically discover and export the *newest* Facebook Marketplace listings for the things you care about – in real time.**

---

## ✨ Features

* **Keyword Search** – monitor any number of search terms via a simple config file.
* **Location‑Based Filtering** – scrape only the cities or ZIP codes you specify.
* **Fresh‑Only Mode** – ignore anything older than *N* minutes (default `10`).
* **Smart Skips** – filter out listings that mention words like “shipping” or have shipping enabled.
* **Deduplication** – never see the same listing twice.
* **Flexible Output** – append to `output.jsonl` or `output.csv` every run.
* **Auto‑Run Ready** – schedule with `cron` (Linux/macOS) or Windows Task Scheduler.
* **(Bonus)** Send new deals straight to Slack or Telegram, or hand them to your own offer bot.

---

## 📂 Project Structure

```text
.
├── scraper.py
├── config.ini
├── requirements.txt
└── README.md
```

## 🔧 Requirements

* **Python 3.9 or newer**
* A Facebook account capable of passing 2‑Factor‑Auth (see [Authentication](#authentication)).
* Google Chrome or Chromium if you use Selenium / undetected‑chromedriver.

---

## 🛠️ Installation

```bash
git clone https://github.com/<your‑user>/facebook‑mp‑scraper.git
cd facebook‑mp‑scraper
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## ⚙️ Configuration

All user‑editable options live in **`config.ini`**.

```yaml
# config.ini
search_terms:
  - "iphone 13"
  - "macbook"
locations:
  - "Miami, FL"
  - "33101"
anti_keywords:
  - "shipping"
  - "firm price"
  - "not negotiable"
max_age_minutes: 10          # ignore listings older than this
output:
  format: "json"            # json or csv
  path: "data/output.jsonl"
dedup_file: "data/seen.txt" # simple newline‑delimited id store
slack:
  webhook_url: ""           # optional
telegram:
  bot_token: ""
  chat_id: ""
headless: true               # run browser in the background
use_cookies: false           # set true if supplying cookies.json
```

### Authentication

Keep your credentials out of source control by exporting **environment variables**:

```bash
export FB_EMAIL="you@example.com"
export FB_PASSWORD="yourPassword"
export FB_2FA_SECRET="base32secret"   # if you use TOTP; otherwise leave empty
```

Alternatively, drop a `cookies.json` (created from an authenticated browser session) in the project root and set `use_cookies: true` in `config.ini`.

---

## 🚀 Usage

```bash
# Scrape Miami for "iphone13"
python scraper.py miami iphone13

# Scrape every city & keyword defined in config.ini
python scraper.py all
```

Additional flags:

| Flag           | Description                                  |
| -------------- | -------------------------------------------- |
| `--headless 0` | Show the browser window (default is hidden). |
| `--once`       | Run one cycle and exit.                      |
| `--age 5`      | Override `max_age_minutes` for this run.     |

---

## 🕒 Scheduling

### Linux (cron)

Add a line like the following with `crontab -e` to run every 5 minutes:

```cron
*/5 * * * * /path/to/venv/bin/python /home/user/facebook-mp-scraper/scraper.py all >> /var/log/fbmp.log 2>&1
```

### Windows (Task Scheduler)

1. Open **Task Scheduler** → *Create Basic Task*.
2. Trigger → *Daily* → Repeat task every *5 minutes*.
3. Action → *Start a program* → browse to `python.exe` and set arguments to `C:\path\to\scraper.py all`.

---

## 📤 Output

Each run appends new records to the file specified in `config.yaml`.

### JSON example

```json
{
  "id": "123456789012345",
  "title": "iPhone 13 – 128 GB (Mint)",
  "price": 450,
  "image_urls": [
    "https://scontent.xx.fbcdn.net/..."
  ],
  "posted_at": "2025‑06‑19T08:23:00Z",
  "location": "Miami, FL",
  "url": "https://www.facebook.com/marketplace/item/123456789012345"
}
```

---

## 🤖 Integrations (Optional)

* **Slack** – set `slack.webhook_url` to post a message for each fresh deal.
* **Telegram** – fill `telegram.bot_token` and `chat_id`.
* **Bring‑Your‑Own Bot** – import `scraper.on_new_listing()` and plug in your logic.

---

## 🗺️ Roadmap

* Captcha bypass via 2Captcha.
* Docker image & Helm chart.
* Multi‑threaded / async scraper core.
* Web UI for live feed.

---

## 🤝 Contributing

Pull requests are welcome! Please open an issue to discuss improvements or new features.

---

## 📜 License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

<sub>Not affiliated with or endorsed by Facebook, Inc. Use responsibly and respect all applicable terms of service.</sub>
