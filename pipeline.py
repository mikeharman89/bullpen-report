#!/usr/bin/env python3
# ============================================================
# BULLPEN TRACKER — GitHub Actions Pipeline
# Runs every Monday at 1pm MST via GitHub Actions
# Generates dated JSON + updates latest.json + weeks_index.json
# ============================================================

from pybaseball import statcast, cache
import pandas as pd
import json
import os
import shutil
from datetime import datetime, timedelta

cache.enable()

FIP_CONSTANT = 3.10
DATA_DIR     = "data"
WEEKS_DIR    = os.path.join(DATA_DIR, "weeks")
os.makedirs(WEEKS_DIR, exist_ok=True)

# ── Date range — previous Mon–Sun ─────────────────────────────────────────
def get_week_range():
    today          = datetime.today()
    days_since_mon = today.weekday()
    last_sunday    = today - timedelta(days=days_since_mon+1)
    last_monday    = last_sunday - timedelta(days=6)
    return last_monday, last_sunday

monday, sunday = get_week_range()
week_key   = monday.strftime('%Y-%m-%d')
start_str  = monday.strftime('%Y-%m-%d')
end_str    = sunday.strftime('%Y-%m-%d')
week_label = f"{monday.strftime('%b %d')} – {sunday.strftime('%b %d, %Y')}"

print(f"Processing week: {week_label}")

# ── Pull data ─────────────────────────────────────────────────────────────
df = statcast(start_dt=start_str, end_dt=end_str)
print(f"Pulled {len(df)} pitches")

# ── Relievers ─────────────────────────────────────────────────────────────
pitcher_innings = (
    df.groupby(['pitcher','game_pk'])['inning']
    .min().reset_index().rename(columns={'inning':'first_inning'})
)
pitcher_min = pitcher_innings.groupby('pitcher')['first_inning'].min().reset_index()
relievers   = pitcher_min[pitcher_min['first_inning']>1]['pitcher'].tolist()
dfr         = df[df['pitcher'].isin(relievers)].copy()
dfr['fielding_team'] = dfr.apply(
    lambda x: x['home_team'] if x['inning_topbot']=='Top' else x['away_team'], axis=1
)
print(f"Relievers: {len(relievers)}, pitches: {len(dfr)}")

# ── Fatigue ───────────────────────────────────────────────────────────────
arm_game = (
    dfr.groupby(['player_name','pitcher','fielding_team','game_date'])
    .size().reset_index(name='pitches')
)
ref_date = pd.Timestamp(sunday.date())
arm_data = (
    arm_game.groupby(['player_name','pitcher','fielding_team'])
    .agg(last_appearance=('game_date','max'),
         total_pitches=('pitches','sum'),
         games_appeared=('game_date','count'))
    .reset_index()
)
arm_data['last_appearance'] = pd.to_datetime(arm_data['last_appearance'])
arm_data['days_rest']       = (ref_date - arm_data['last_appearance']).dt.days

team_fatigue = (
    arm_data.groupby('fielding_team')
    .agg(total_pitches=('total_pitches','sum'),
         arms_used=('pitcher','nunique'),
         avg_pitches_per_arm=('total_pitches','mean'),
         avg_days_rest=('days_rest','mean'))
    .reset_index()
)
team_fatigue['avg_pitches_per_arm'] = team_fatigue['avg_pitches_per_arm'].round(1)
team_fatigue['avg_days_rest']       = team_fatigue['avg_days_rest'].round(1)

mp = team_fatigue['total_pitches'].max()
mr = team_fatigue['avg_days_rest'].max()
team_fatigue['fatigue_score'] = (
    (team_fatigue['total_pitches']/mp)*70 +
    ((mr-team_fatigue['avg_days_rest'])/mr)*30
).round(1)

def fatigue_tier(s):
    if s>=75: return 'Exhausted'
    if s>=50: return 'Fatigued'
    if s>=25: return 'Moderate'
    return 'Fresh'
team_fatigue['fatigue_tier'] = team_fatigue['fatigue_score'].apply(fatigue_tier)

# ── Performance ───────────────────────────────────────────────────────────
at_bats    = dfr[dfr['events'].notna()].copy()
out_events = ['field_out','strikeout','grounded_into_double_play','force_out',
              'double_play','triple_play','strikeout_double_play','fielders_choice_out',
              'fielders_choice','sac_fly','sac_bunt','caught_stealing_2b',
              'caught_stealing_3b','caught_stealing_home']
hit_events = ['single','double','triple','home_run']

def grp(evts, col):
    return (at_bats[at_bats['events'].isin(evts)]
            .groupby('fielding_team').size().reset_index(name=col))

outs       = grp(out_events, 'outs')
walks      = grp(['walk'],   'walks')
hits       = grp(hit_events, 'hits')
strikeouts = grp(['strikeout','strikeout_double_play'], 'strikeouts')
home_runs  = grp(['home_run'],       'home_runs')
hbp        = grp(['hit_by_pitch'],   'hbp')

at_bats['runs_scored'] = (at_bats['post_bat_score']-at_bats['bat_score']).clip(lower=0)
runs = at_bats.groupby('fielding_team')['runs_scored'].sum().reset_index(name='runs_allowed')

perf = outs
for d in [walks,hits,strikeouts,home_runs,hbp,runs]:
    perf = perf.merge(d, on='fielding_team', how='left')
perf = perf.fillna(0)

perf['ip']      = (perf['outs']/3).round(1)
perf['whip']    = ((perf['walks']+perf['hits'])/perf['ip']).round(2)
perf['era']     = ((perf['runs_allowed']/perf['ip'])*9).round(2)
perf['k_per_9'] = ((perf['strikeouts']/perf['ip'])*9).round(1)
perf['fip']     = (
    ((13*perf['home_runs'])+(3*(perf['walks']+perf['hbp']))-(2*perf['strikeouts']))
    /perf['ip']+FIP_CONSTANT
).round(2)

me=perf['era'].max(); mw=perf['whip'].max(); mk=perf['k_per_9'].max()
perf['perf_score'] = (
    ((me-perf['era'])/me)*40 +
    ((mw-perf['whip'])/mw)*40 +
    (perf['k_per_9']/mk)*20
).round(1)

def perf_tier(s):
    if s>=75: return 'Elite'
    if s>=50: return 'Above Average'
    if s>=25: return 'Below Average'
    return 'Struggling'
perf['perf_tier'] = perf['perf_score'].apply(perf_tier)

# ── Per-arm performance ───────────────────────────────────────────────────
def arm_grp(evts, col):
    return (at_bats[at_bats['events'].isin(evts)]
            .groupby(['player_name','pitcher','fielding_team']).size().reset_index(name=col))

arm_outs  = arm_grp(out_events, 'outs')
arm_walks = arm_grp(['walk'],   'walks')
arm_hits  = arm_grp(hit_events, 'hits')
arm_ks    = arm_grp(['strikeout','strikeout_double_play'], 'strikeouts')
arm_hrs   = arm_grp(['home_run'],     'home_runs')
arm_hbp   = arm_grp(['hit_by_pitch'], 'hbp')
arm_runs  = (at_bats.groupby(['player_name','pitcher','fielding_team'])['runs_scored']
             .sum().reset_index(name='runs_allowed'))

arm_perf = arm_outs
for d in [arm_walks,arm_hits,arm_ks,arm_hrs,arm_hbp,arm_runs]:
    arm_perf = arm_perf.merge(d, on=['player_name','pitcher','fielding_team'], how='left')
arm_perf = arm_perf.fillna(0)
ip_s = arm_perf['outs'].div(3).replace(0, float('nan'))
arm_perf['ip']      = ip_s.round(1).fillna(0)
arm_perf['whip']    = ((arm_perf['walks']+arm_perf['hits'])/ip_s).round(2).fillna(0)
arm_perf['era']     = ((arm_perf['runs_allowed']/ip_s)*9).round(2).fillna(0)
arm_perf['k_per_9'] = ((arm_perf['strikeouts']/ip_s)*9).round(1).fillna(0)
arm_perf['fip']     = (
    ((13*arm_perf['home_runs'])+(3*(arm_perf['walks']+arm_perf['hbp']))-(2*arm_perf['strikeouts']))
    /ip_s+FIP_CONSTANT
).round(2).fillna(0)

arm_combined = arm_data.merge(
    arm_perf[['pitcher','ip','whip','era','fip','k_per_9',
              'runs_allowed','hits','walks','strikeouts','home_runs']],
    on='pitcher', how='left'
)

# ── Team combined ─────────────────────────────────────────────────────────
team_combined = team_fatigue.merge(
    perf[['fielding_team','ip','era','whip','fip','k_per_9',
          'runs_allowed','hits','walks','strikeouts','home_runs','perf_score','perf_tier']],
    on='fielding_team', how='left'
)

# ── Wins / losses / saves ─────────────────────────────────────────────────
game_results = (
    dfr.groupby(['game_pk','fielding_team'])
    .agg(home_team=('home_team','first'), away_team=('away_team','first'),
         post_home_score=('post_home_score','max'),
         post_away_score=('post_away_score','max'))
    .reset_index()
)
def bullpen_won(row):
    if row['fielding_team']==row['home_team']:
        return row['post_home_score']>row['post_away_score']
    return row['post_away_score']>row['post_home_score']
game_results['won'] = game_results.apply(bullpen_won, axis=1)
team_record = (
    game_results.groupby('fielding_team')
    .agg(wins=('won','sum'), losses=('won',lambda x:(~x).sum()))
    .reset_index()
)

last_pitch = (
    dfr.sort_values(['game_pk','at_bat_number','pitch_number'])
    .groupby(['game_pk','fielding_team']).last().reset_index()
)
def is_save(row):
    ts = row['post_home_score'] if row['fielding_team']==row['home_team'] else row['post_away_score']
    os_ = row['post_away_score'] if row['fielding_team']==row['home_team'] else row['post_home_score']
    return ts>os_ and (ts-os_)<=3
last_pitch['is_save'] = last_pitch.apply(is_save, axis=1)
saves = (last_pitch[last_pitch['is_save']]
         .groupby('fielding_team').size().reset_index(name='saves'))

team_combined = team_combined.merge(team_record, on='fielding_team', how='left')
team_combined = team_combined.merge(saves,       on='fielding_team', how='left')
team_combined['wins']   = team_combined['wins'].fillna(0).astype(int)
team_combined['losses'] = team_combined['losses'].fillna(0).astype(int)
team_combined['saves']  = team_combined['saves'].fillna(0).astype(int)

# ── Save week JSON ────────────────────────────────────────────────────────
week_data = {
    "meta": {
        "week_start": monday.strftime('%Y-%m-%d'),
        "week_end":   sunday.strftime('%Y-%m-%d'),
        "label":      week_label,
        "generated":  datetime.now().strftime('%Y-%m-%d %H:%M')
    },
    "teams": json.loads(team_combined.to_json(orient='records')),
    "arms":  json.loads(arm_combined.to_json(orient='records'))
}

week_path = os.path.join(WEEKS_DIR, f"{week_key}.json")
with open(week_path, 'w') as f:
    json.dump(week_data, f)
print(f"Saved: {week_path}")

# Update latest.json
shutil.copy(week_path, os.path.join(DATA_DIR, "latest.json"))
print("Updated: data/latest.json")

# Update weeks_index.json
index_path = os.path.join(DATA_DIR, "weeks_index.json")
index = []
if os.path.exists(index_path):
    with open(index_path) as f:
        index = json.load(f)

# Add this week if not already in index
week_entry = {
    "week_start": monday.strftime('%Y-%m-%d'),
    "week_end":   sunday.strftime('%Y-%m-%d'),
    "label":      week_label,
    "file":       f"weeks/{week_key}.json"
}
if not any(w['week_start']==week_key for w in index):
    index.append(week_entry)
    index.sort(key=lambda x: x['week_start'])

with open(index_path, 'w') as f:
    json.dump(index, f, indent=2)
print(f"Updated: {index_path} ({len(index)} weeks)")

print(f"\nDone! Week of {week_label} processed successfully.")
