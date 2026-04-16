# Bullpen Report

A weekly MLB bullpen tracking system that pulls Statcast data, calculates fatigue and performance metrics, generates social media graphics, and publishes a live web dashboard — all automated with a single script.

---

## What It Does

Every Monday, this system:

1. **Pulls the last 7 days of Statcast pitch data** via [pybaseball](https://github.com/jldbc/pybaseball)
2. **Identifies relievers** and calculates fatigue + performance metrics for every arm and team
3. **Generates 32 PNG graphics** (30 team cards + 2 league-wide rankings) ready to post on Instagram/Twitter
4. **Updates the live web dashboard** at [mikeharman89.github.io/bullpen-report](https://mikeharman89.github.io/bullpen-report)

---

## Project Structure

```
Projects/
├── Pitcher Fatigue/              ← Data pipeline (this repo's backend)
│   ├── PitcherFatigue.py         ← Main data pipeline script
│   ├── generate_all_graphics.py  ← Generates 32 PNG graphics
│   ├── weekly_update.sh          ← One-click weekly automation script
│   ├── team_data.json            ← Exported team-level data
│   ├── arm_data.json             ← Exported individual arm data
│   ├── graphics/                 ← Output folder for PNGs
│   └── venv/                     ← Python virtual environment
│
└── bullpen-report/               ← Web dashboard (this repo)
    ├── index.html                ← Live dashboard
    └── data/
        ├── team_data.json        ← Copy of weekly export
        └── arm_data.json         ← Copy of weekly export
```

---

## Metrics Explained

### Fatigue Score (0–100)
Calculated from two factors:
- **70% — Pitch volume**: Total pitches thrown by the bullpen over the last 7 days relative to the rest of the league
- **30% — Rest days**: Average days since last appearance for each arm

| Score | Tier |
|-------|------|
| 75+ | Exhausted |
| 50–74 | Fatigued |
| 25–49 | Moderate |
| 0–24 | Fresh |

### Performance Score (0–100)
Calculated from three factors:
- **40% — ERA**: Lower is better
- **40% — WHIP**: Lower is better
- **20% — K/9**: Higher is better

| Score | Tier |
|-------|------|
| 75+ | Elite |
| 50–74 | Above Average |
| 25–49 | Below Average |
| 0–24 | Struggling |

### Arm Status (Rest Days)
| Rest Days | Status |
|-----------|--------|
| 0–1 | High Risk |
| 2–3 | Moderate |
| 4–5 | Rested |
| 6+ | Fresh |

### Bullpen Record
- **Wins/Losses**: Games where the bullpen appeared and the team won or lost
- **Saves**: Games where a reliever finished a game their team won by 3 or fewer runs

---

## Setup

### Requirements
- Python 3.9+
- Mac or Linux (shell script uses bash)
- GitHub account

### 1. Clone the dashboard repo
```bash
cd ~/Projects
git clone https://github.com/mikeharman89/bullpen-report.git
```

### 2. Set up the Python environment
```bash
cd "Pitcher Fatigue"
python3 -m venv venv
source venv/bin/activate
pip install pybaseball pandas pillow
```

### 3. Install Poppins font (required for graphics)
Download from [Google Fonts](https://fonts.google.com/specimen/Poppins), install all `.ttf` files on your system.

On Mac the font paths should be:
```
/Library/Fonts/Poppins-Bold.ttf
/Library/Fonts/Poppins-Medium.ttf
/Library/Fonts/Poppins-Regular.ttf
```

### 4. Configure paths
In `generate_all_graphics.py`, update:
```python
# Font paths (update to match your system)
FONT_BOLD    = "/Library/Fonts/Poppins-Bold.ttf"
FONT_MEDIUM  = "/Library/Fonts/Poppins-Medium.ttf"
FONT_REGULAR = "/Library/Fonts/Poppins-Regular.ttf"

# Output paths
BASE       = "/Users/YOUR_USERNAME/Projects/Pitcher Fatigue"
OUTPUT_DIR = "/Users/YOUR_USERNAME/Projects/Pitcher Fatigue/graphics"
```

In `PitcherFatigue.py`, update:
```python
BASE = '/Users/YOUR_USERNAME/Projects/Pitcher Fatigue'
```

In `weekly_update.sh`, update:
```bash
PITCHER_DIR="/Users/YOUR_USERNAME/Projects/Pitcher Fatigue"
DASHBOARD_DIR="/Users/YOUR_USERNAME/Projects/bullpen-report"
```

### 5. Set up GitHub authentication
GitHub requires a Personal Access Token (PAT) for command line pushes:
1. Go to GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)
2. Generate a new token with **repo** scope
3. Run:
```bash
cd ~/Projects/bullpen-report
git remote set-url origin https://YOUR_TOKEN@github.com/YOUR_USERNAME/bullpen-report.git
```

### 6. Make the automation script executable (first time only)
```bash
cd "/Users/YOUR_USERNAME/Projects/Pitcher Fatigue"
chmod +x weekly_update.sh
```

### 7. Enable GitHub Pages
1. Go to your `bullpen-report` repo on GitHub
2. Click **Settings** → **Pages**
3. Under Source, select **Deploy from a branch**
4. Select **main** branch and **/ (root)** folder
5. Click **Save**

Your dashboard will be live at:
```
https://YOUR_USERNAME.github.io/bullpen-report
```

---

## Weekly Workflow

Every Monday morning, run one command:

```bash
cd "/Users/YOUR_USERNAME/Projects/Pitcher Fatigue"
./weekly_update.sh
```

This will automatically:
1. Pull the latest 7 days of Statcast data
2. Calculate all fatigue, performance, win/loss, and save metrics
3. Export `team_data.json` and `arm_data.json`
4. Generate all 32 PNG graphics into the `graphics/` folder
5. Copy the JSON files to the dashboard repo
6. Commit and push to GitHub

The dashboard at your GitHub Pages URL will update within a minute of the push.

---

## Graphics

The system generates **32 PNG images** (1080×1350px, portrait) each week:

| File | Description |
|------|-------------|
| `LEAGUE_performance.png` | All 30 teams ranked by performance score |
| `LEAGUE_fatigue.png` | All 30 teams ranked by fatigue score |
| `{TEAM}_bullpen_report.png` × 30 | Individual team arm breakdown |

### Team Card Layout
- **Header**: Team code, full name, Week Of date range
- **Summary bar**: Perf score, ERA, WHIP, Fatigue score
- **Arm table**: G, IP, Runs, Pitches, K/9, ERA, WHIP, Status pill
- **Bottom banner**: Bullpen record (W-L) and Saves

### Color Coding
- **ERA**: White (≤3.00) → Yellow (≤5.00) → Orange (≤8.00) → Red (8.00+)
- **WHIP**: White (≤1.00) → Yellow (≤1.30) → Orange (≤1.80) → Red (1.80+)
- **Status pill**: Red (High Risk) → Orange (Moderate) → Green (Rested) → Teal (Fresh)

---

## Dashboard

The live dashboard has two views:

### League View
- Summary metrics (best bullpen, avg ERA, avg WHIP, most fatigued)
- Performance rankings table (sortable)
- Fatigue rankings table (sortable)
- Win / Loss / Saves table

### Teams View
- Team selector dropdown
- Team summary metrics (perf score, ERA/WHIP, fatigue, record)
- Full arm breakdown table (sortable by any column)

---

## Data Source

All data is pulled from [Baseball Savant](https://baseballsavant.mlb.com/) via the [pybaseball](https://github.com/jldbc/pybaseball) library. Pybaseball caches data locally to avoid repeat downloads.

### Reliever Identification
A pitcher is classified as a reliever if they **never appeared in the 1st inning** across the 7-day window. This avulates traditional roster-based SP/RP classification which is unreliable from Statcast data alone.

---

## Known Limitations

- **Season-to-date stats** are not currently included — metrics are last 7 days only
- **Saves** are approximated: a save is counted when a reliever finishes a game their team won by 3 or fewer runs. Official MLB save rules (inherited runners, entry with tying run on base, etc.) are not fully replicated
- **Opener/bulk pitcher edge cases**: Pitchers used in an opener role may occasionally be misclassified as relievers

---

## Future Plans

- [ ] Season-to-date cumulative stats
- [ ] Team logo support on graphics
- [ ] Automated Monday scheduling via cron job
- [ ] Twitter/Instagram auto-posting
- [ ] Pitcher-level historical fatigue tracking

---

## License

MIT License — free to use and modify. If you build on this, a credit would be appreciated.
