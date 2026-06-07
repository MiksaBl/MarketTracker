import tkinter as tk
import re
import sqlite3
import threading
import time
import requests
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# =========================
# TELEGRAM
# =========================
BOT_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass


# =========================
# DATABASE
# =========================
conn = sqlite3.connect("market.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS radars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_key TEXT UNIQUE,
    url TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_key TEXT,
    url TEXT UNIQUE,
    first_seen TEXT,
    last_seen TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_key TEXT,
    total_ads INTEGER,
    new_ads INTEGER,
    activity_trend REAL,
    status TEXT,
    created_at TEXT
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS baselines (
    market_key TEXT PRIMARY KEY,
    first_total_ads INTEGER,
    created_at TEXT
)
""")

conn.commit()


# =========================
# GLOBAL STATE
# =========================
running = False
thread = None
checkboxes = []
last_valid_total = None

def load_last_state():
    global last_valid_total

    cursor.execute("""
        SELECT total_ads FROM snapshots
        ORDER BY created_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()

    if row and row[0] is not None:
        last_valid_total = row[0]

# =========================
# UI HELPERS
# =========================
def log(text):
    logs.insert(tk.END, text + "\n")
    logs.see(tk.END)


def normalize(url):
    return url.split("?")[0]


# =========================
# SCRAPER
# =========================
def extract_listings(page):
    links = set()

    for a in page.query_selector_all("a"):
        try:
            href = a.get_attribute("href")
            if not href:
                continue

            if "offer" in href or "autoscout24" in href:
                if href.startswith("/"):
                    href = "https://www.autoscout24.com" + href

                if "autoscout24.com" in href:
                    links.add(normalize(href))
        except:
            continue

    return links


# 🔥 NEW FUNCTION (UBACENO)
def extract_total_ads(page):
    try:
        # 1. JS STATE (current page ONLY)
        try:
            state = page.evaluate("""
                () => {
                    return JSON.stringify(
                        window.__INITIAL_STATE__ ||
                        window.__APOLLO_STATE__ ||
                        null
                    );
                }
            """)

            if state:
                match = re.search(r'"totalResults"\s*:\s*(\d+)', state)
                if match:
                    return int(match.group(1))
        except:
            pass

        # 2. HTML fallback (clean)
        text = page.inner_text("body")

        match = re.search(r'([\d.,]+)\s*(offers|results|vehicles|cars)', text, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(",", "").replace(".", ""))

        return None

    except:
        return None
# =========================
# CORE LOOP
# =========================
def radar_loop():
    global running

    send_telegram("🚗 MARKET TRACKER STARTED")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        while running:
            try:
                selected = [x for x in checkboxes if x["var"].get()]

                if not selected:
                    log("⚠ NO RADARS SELECTED")
                    time.sleep(5)
                    continue

                for r in selected:
                    if not running:
                        break

                    market_key = r["name"]
                    url = r["url"]

                    log(f"📡 SCANNING {market_key}")

                    try:
                        page.goto(url, timeout=60000)
                        page.wait_for_timeout(4000)
                    except:
                        log(f"❌ {market_key} FAILED")
                        send_telegram(f"❌ {market_key} FAILED")
                        continue

                    listings = extract_listings(page)

                    # =========================
                    # TOTAL ADS
                    # =========================
                    global last_valid_total

                    total_ads = extract_total_ads(page)

                    if total_ads is None:
                        total_ads = last_valid_total
                    else:
                        last_valid_total = total_ads

                    now = datetime.now()

                    # load old listings
                    cursor.execute("""
                        SELECT url FROM listings WHERE market_key=?
                    """, (market_key,))
                    old_urls = set([x[0] for x in cursor.fetchall()])

                    new_ads = listings - old_urls

                    for link in new_ads:
                        cursor.execute("""
                            INSERT OR IGNORE INTO listings
                            (market_key, url, first_seen, last_seen)
                            VALUES (?, ?, ?, ?)
                        """, (market_key, link, now, now))

                    for link in listings:
                        cursor.execute("""
                            UPDATE listings SET last_seen=?
                            WHERE url=?
                        """, (now, link))

                    conn.commit()

                    # NEW ADS (3 MIN)
                    cursor.execute("""
                        SELECT COUNT(*) FROM listings
                        WHERE market_key=?
                        AND first_seen >= ?
                    """, (market_key, now - timedelta(minutes=3)))

                    new_ads_3min = cursor.fetchone()[0]

                    # 24H activity
                    cursor.execute("""
                        SELECT COUNT(*) FROM listings
                        WHERE market_key=?
                        AND first_seen >= ?
                    """, (market_key, now - timedelta(hours=24)))

                    last_24h = cursor.fetchone()[0]
                    if last_24h < 5:
                        avg_24h = max(last_24h, 1)
                    else:
                        avg_24h = last_24h / 24

                    if avg_24h > 0:
                        activity_trend = ((new_ads_3min - avg_24h) / avg_24h) * 100
                    else:
                        activity_trend = 0

                    # =========================
                    # TOTAL TREND (NEW BASELINE SYSTEM)
                    # =========================

                    baseline = get_baseline(market_key)

                    # FIX: ako nema total_ads → ne diraj ništa
                    if total_ads is None:
                        total_trend = 0

                    else:
                        if baseline is None:
                            # LOCK FIRST EVER VALUE
                            cursor.execute("""
                                INSERT INTO baselines (market_key, first_total_ads, created_at)
                                VALUES (?, ?, ?)
                            """, (market_key, total_ads, now))

                            conn.commit()
                            total_trend = 0

                        else:
                            # NORMAL MODE
                            if baseline and baseline > 0:
                                total_trend = ((total_ads - baseline) / baseline) * 100
                            else:
                                total_trend = 0

                    # status
                    if activity_trend > 50:
                        status = "🔥 Strong Growth"
                    elif activity_trend > 10:
                        status = "📈 Increasing"
                    elif activity_trend > -10:
                        status = "➖ Stable"
                    else:
                        status = "❄ Cooling"

                    # INSERT SNAPSHOT
                    cursor.execute("""
                        INSERT INTO snapshots
                        (market_key, total_ads, new_ads, activity_trend, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        market_key,
                        total_ads,
                        new_ads_3min,
                        activity_trend,
                        status,
                        now
                    ))

                    conn.commit()

                    # =========================
                    # RADARS TOUCH UPDATE (EXACT REQUEST)
                    # =========================
                    cursor.execute("""
                        UPDATE radars
                        SET url = url
                        WHERE market_key=?
                    """, (market_key,))

                    conn.commit()

                    # TELEGRAM REPORT
                    msg = f"""
📊 MARKET REPORT

🚗 {market_key}

📦 Total Ads: {total_ads}
📈 Total Trend: {total_trend:.2f}%

🆕 New Ads (3min): {new_ads_3min}
⚡ Activity Trend: {activity_trend:.2f}%

📊 Status:
{status}
"""

                    log(msg)
                    send_telegram(msg)

            except Exception as e:
                log(f"ERROR: {e}")

            time.sleep(30)
            
def smooth(prev, new, alpha=0.2):
    if prev is None:
        return new
    return int(prev * (1 - alpha) + new * alpha)

def get_baseline(market_key):
    cursor.execute("""
        SELECT first_total_ads FROM baselines
        WHERE market_key=?
    """, (market_key,))
    row = cursor.fetchone()
    return row[0] if row else None

# =========================
# UI (UNCHANGED)
# =========================
def start():
    global running, thread
    
    load_last_state()   # 🔥 OVO DODAJ
    
    if running:
        return
    running = True
    log("🚀 STARTED")
    thread = threading.Thread(target=radar_loop, daemon=True)
    thread.start()


def stop():
    global running
    running = False
    log("🛑 STOPPED")
    send_telegram("🛑 MARKET TRACKER STOPPED")


def delete_selected():
    global checkboxes
    for x in checkboxes:
        if x["var"].get():
            cursor.execute("DELETE FROM radars WHERE market_key=?", (x["name"],))
    conn.commit()
    refresh()
    log("🗑 DELETED SELECTED RADARS")


def add_radar():
    name = name_entry.get()
    url = url_entry.get()

    if not name or not url:
        return

    cursor.execute("""
        INSERT OR IGNORE INTO radars (market_key, url)
        VALUES (?, ?)
    """, (name, url))

    conn.commit()

    name_entry.delete(0, tk.END)
    url_entry.delete(0, tk.END)

    refresh()


def refresh():
    for w in radar_frame.winfo_children():
        w.destroy()

    checkboxes.clear()

    cursor.execute("SELECT market_key, url FROM radars")
    rows = cursor.fetchall()

    for r in rows:
        var = tk.BooleanVar()

        cb = tk.Checkbutton(
            radar_frame,
            text=r[0],
            variable=var,
            bg="#0f1115",
            fg="#d0d0d0",
            activebackground="#0f1115",
            selectcolor="#1e2430"
        )
        cb.pack(anchor="w")

        checkboxes.append({
            "name": r[0],
            "url": r[1],
            "var": var
        })


# =========================
# GUI
# =========================
root = tk.Tk()
root.title("🚗 Market Tracker")
root.geometry("900x650")
root.configure(bg="#0f1115")

title = tk.Label(root, text="🚗 Market Tracker",
                 fg="#e6e6e6", bg="#0f1115",
                 font=("Segoe UI", 18, "bold"))
title.pack(pady=10)

frame = tk.Frame(root, bg="#161a22")
frame.pack(pady=10)

name_entry = tk.Entry(frame, width=20)
name_entry.grid(row=0, column=0)

url_entry = tk.Entry(frame, width=60)
url_entry.grid(row=0, column=1)

tk.Button(frame, text="ADD", command=add_radar,
          bg="#2a7fff", fg="white").grid(row=0, column=2)

radar_frame = tk.LabelFrame(root, text="Radars",
                            bg="#0f1115", fg="#bdbdbd")
radar_frame.pack(fill="x", padx=10, pady=10)

btn = tk.Frame(root, bg="#0f1115")
btn.pack(pady=10)

tk.Button(btn, text="START", command=start,
          bg="#1f8f4e", fg="white", width=12).grid(row=0, column=0)

tk.Button(btn, text="STOP", command=stop,
          bg="#b23b3b", fg="white", width=12).grid(row=0, column=1)

tk.Button(btn, text="DELETE", command=delete_selected,
          bg="#444a55", fg="white", width=12).grid(row=0, column=2)

logs = tk.Text(root, bg="#0b0d10", fg="#d6d6d6",
               insertbackground="white")
logs.pack(fill="both", expand=True, padx=10, pady=10)

refresh()
root.mainloop()

