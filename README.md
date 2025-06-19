⸻

## 📌 Task: Facebook Marketplace Scraper – Newest Listings

⸻

### Objective:

Build a scraper that automatically pulls the newest Facebook Marketplace listings based on specific keywords and filters.

⸻

### Key Requirements:
	1.	Search Terms:
	•	Scraper should search for specific keywords (e.g. “iPhone 13”, “MacBook”, etc.)
	•	These terms should be editable in a config file or list.
	2.	Location-Based Filtering:
	•	Target listings in specific cities or zip codes (e.g. Miami, FL or 33101).
	•	Location input should be flexible and editable.
	3.	Listing Filters:
	•	Only scrape listings posted recently (e.g., within the last 10 minutes).
	•	Skip listings that contain any anti-keywords (e.g., “shipping”, “firm price”, “not negotiable”).
	•	Skip any listings with shipping enabled.
	4.	Data to Capture:
	•	Title
	•	Price
	•	Image URL(s)
	•	Post time
	•	Location
	•	Direct link to the listing
	5.	Deduplication:
	•	Avoid saving listings already scraped (based on link or ID).
	6.	Output Format:
	•	Save data as JSON or CSV.
	•	File should update or append every time the script runs.
	7.	Run Automatically:
	•	Script should run every 5–10 minutes.
	•	Can be scheduled with Windows Task Scheduler or Linux cronjob.
	8.	Optional (Bonus Features):
	•	Push new listings to a Slack/Telegram channel.
	•	Integrate with your offer messaging bot after scraping.

⸻

✅ Example Use:

Run this command to start scraping:

python scraper.py miami iphone13

Or to run all cities and terms from config:

python scraper.py all


⸻