# 🏭 IndiaMART Lead Scraper (CLI-Based)

A **Python + Selenium–based automation tool** to **extract verified business leads from IndiaMART** using product keywords.
The scraper supports **OTP-based login**, **advanced result expansion**, **lead relevancy scoring**, and **CSV export**, making it suitable for **sales, market research, and B2B lead generation**.

---

## ✨ Key Features

* 🔐 **OTP-based IndiaMART Buyer Login**
* 🔍 **Keyword-based product search**
* 🌍 **All-India seller coverage**
* 📈 **Relevancy scoring using fuzzy matching**
* 📞 Extracts:

  * Company Name
  * Product Description
  * Phone Number
  * Email (if available)
  * Address
  * Company Profile URL
  * Product Catalog URL (PDFs)
* 📊 **Exports clean CSV files**
* 🧠 **Retry & error-handling logic**
* 🧾 **Detailed logging with timestamps**
* ⚙️ **Headless browser support**
* 🖥️ **CLI-friendly + Windows batch runners**

---

## 📁 Project Structure

```
indiamart-lead-scraper/
│
├── cli.py                     # Command-line interface entry point
├── indiamart_scraper_new.py   # Core scraping logic (Selenium)
├── utils.py                   # Logging, retry, validation helpers
├── requirements.txt           # Python dependencies
├── run_cli.bat                # Windows runner for CLI mode
├── run_scraper.bat            # Windows runner for scraper
├── logs/                      # Auto-generated logs (ignored in git)
└── leads.csv                  # Output file (generated)
```

---

## 🧰 Tech Stack

* **Python 3.9+**
* **Selenium**
* **Chrome WebDriver**
* **pandas**
* **fuzzywuzzy + Levenshtein**
* **webdriver-manager**
* **fake-useragent**

---

## 📦 Installation & Setup

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
```

---

### 2️⃣ Create Virtual Environment (Recommended)

```bash
python -m venv ai-env
ai-env\Scripts\activate   # Windows
```

---

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4️⃣ Install Google Chrome

Make sure **Google Chrome** is installed and updated
(Required for Selenium automation)

---

## ⚙️ Configuration (Important)

### 🔐 Add Your Mobile Number for OTP Login

Open **`indiamart_scraper_new.py`**
Replace this line:

```python
default_mobile = "<Mobile Number Here>"
```

With:

```python
default_mobile = "9XXXXXXXXX"
```

⚠️ OTP will be sent to this number during login.

---

## 🚀 How to Run

### ✅ Option 1: Run via CLI (Recommended)

```bash
python cli.py --keyword "solar panel" --min-leads 100 --output leads.csv
```

#### CLI Options

| Flag              | Description                  |
| ----------------- | ---------------------------- |
| `-k, --keyword`   | Product keyword to search    |
| `-m, --min-leads` | Minimum number of leads      |
| `-o, --output`    | Output CSV filename          |
| `-H, --headless`  | Run browser in headless mode |

Example:

```bash
python cli.py -k "industrial pump" -m 200 -o pumps.csv -H
```

---

### ✅ Option 2: Windows Batch Files

```bash
run_cli.bat
```

or

```bash
run_scraper.bat
```

Useful for **non-technical users** or quick execution.

---

## 📤 Output

* Leads are exported as **CSV**
* Sorted by **Relevancy Score (highest first)**
* UTF-8 encoded (Excel compatible)

Example columns:

```
Company Name
Product Title/Description
Price
Address
Phone Number
Email
Company Profile URL
Product Catalog URL
Relevancy Score (%)
```

---

## 📜 Logging & Debugging

* Logs stored in `/logs/`
* Timestamped log files:

  ```
  logs/scraper_YYYYMMDD_HHMMSS.log
  ```
* Automatic screenshots on failures:

  * Login errors
  * Page load timeouts
  * Element changes

---

## ⚠️ Important Notes

* This tool **uses real browser automation**
* OTP must be entered manually
* Excessive scraping may trigger IndiaMART anti-bot systems
* Use **reasonable delays & limits**
