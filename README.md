# 📊 Market Tracker

Market Tracker is a Python application designed to monitor vehicle marketplaces, collect listing data, and analyze market activity trends over time.

The used car market changes constantly, with new listings appearing every day and prices varying depending on demand, availability, and vehicle characteristics. Manually tracking these changes is difficult and does not provide a clear overview of market movements.

Market Tracker solves this problem by automatically collecting vehicle listing data, storing historical information, and helping users understand market activity through continuous monitoring and trend analysis.

The application provides a data-driven approach to tracking vehicle marketplaces and identifying changes in supply and listing activity.

## Features

- Real-time vehicle marketplace monitoring
- Automatic detection of new listings
- Historical vehicle data storage
- Market activity trend analysis
- Multiple marketplace radar support
- SQLite database for storing collected data
- Telegram notifications for important updates
- Simple Tkinter desktop interface
- Automated data collection using Playwright

## Technologies Used

- Python
- Playwright
- SQLite
- Tkinter
- Telegram Bot API

## How It Works

1. The application monitors selected vehicle marketplaces.
2. New vehicle listings are automatically collected and processed.
3. Listing information is stored in a local SQLite database.
4. Historical data is used to analyze market activity and changes over time.
5. Users can receive Telegram notifications about important marketplace updates.

This allows users to track market behavior and better understand trends instead of relying only on individual listings.

## Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/market-tracker.git
```

Navigate into the project folder:

```bash
cd market-tracker
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Install Playwright browser:

```bash
playwright install chromium
```

Run the application:

```bash
python markettracker.py
```

## Project Purpose

Market Tracker was developed to solve the challenge of understanding vehicle marketplace activity and tracking changes that are difficult to notice through manual browsing.

The goal of the project was to build an automated system capable of collecting, storing, and analyzing marketplace data to provide useful insights about vehicle availability and market trends.

The project demonstrates practical software development skills through:

- Data collection and processing
- Web scraping and browser automation
- Historical data management
- Database integration
- Trend analysis
- API integration
- Desktop application development
- Real-world problem solving

## Future Improvements

- Interactive market analytics dashboard
- Price trend visualization
- Machine learning based market predictions
- Advanced vehicle segmentation
- Additional marketplace integrations
- More detailed statistical analysis

## Author

Mihajlo Blagojevic
