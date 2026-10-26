"""
prepare_data.py
----------------
Turns the raw "Victoria Road Crash Data" tables (DataVic / Department of
Transport and Planning) into the small, chart-ready CSV files in /data.

Only counting and grouping happens here, so the web page loads quickly
(the raw tables are ~80 MB; the outputs are well under 1 MB in total).

Usage
    python scripts/prepare_data.py path/to/raw_folder

The raw folder must contain the DataVic files  accident.csv, person.csv
and node.csv  (any capitalisation). Re-run this script whenever DataVic
publishes a newer release; every chart updates automatically.
"""

import sys
from pathlib import Path

import pandas as pd

RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "raw")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "data"


def read(name):
    for f in RAW.iterdir():
        if f.name.lower() == f"{name}.csv":
            return pd.read_csv(f, dtype=str)
    raise FileNotFoundError(f"{name}.csv not found in {RAW}")


accident = read("accident")
person = read("person")
node = read("node").drop_duplicates("ACCIDENT_NO")

accident["year"] = accident["ACCIDENT_DATE"].str[:4].astype(int)
accident["month"] = accident["ACCIDENT_DATE"].str[5:7].astype(int)
accident["hour"] = accident["ACCIDENT_TIME"].str[:2].astype(int)

# Last complete calendar year in the release (DataVic publishes with a lag)
LAST = int(accident.loc[accident["month"] == 12, "year"].max())
FIRST = int(accident["year"].min())
RECENT = (LAST - 4, LAST)  # five most recent full years
accident = accident[accident["year"] <= LAST]
print(f"Years {FIRST}-{LAST}; recent window {RECENT[0]}-{RECENT[1]}")

SEVERITY = {"1": "Fatal", "2": "Serious injury", "3": "Other injury", "4": "Non-injury"}
accident["severity"] = accident["SEVERITY"].map(SEVERITY)

# ---------------------------------------------------------------- LGA lookup
# Crash records use short upper-case council names; ABS boundaries use the
# official names. Map them to the ABS LGA code so the two sources can join.
pop = pd.read_csv(OUT / "lga_population.csv", dtype={"lgaCode": str})
abs_name = {n.upper().replace(" (VIC.)", ""): c for n, c in zip(pop["lgaName"], pop["lgaCode"])}
SPECIAL = {
    "DANDENONG": "GREATER DANDENONG", "GEELONG": "GREATER GEELONG",
    "BENDIGO": "GREATER BENDIGO", "SHEPPARTON": "GREATER SHEPPARTON",
    "MORELAND": "MERRI-BEK",  # renamed in 2022
}
def to_code(name):
    if not isinstance(name, str) or name.startswith("("):
        return None  # alpine resorts / French Island are unincorporated
    return abs_name.get(SPECIAL.get(name, name))

node["lgaCode"] = node["LGA_NAME"].map(to_code)
metro_codes = set(pop.loc[pop["metro"] == 1, "lgaCode"])
accident = accident.merge(
    node[["ACCIDENT_NO", "lgaCode", "LATITUDE", "LONGITUDE"]], on="ACCIDENT_NO", how="left")
has_node = accident["ACCIDENT_NO"].isin(node["ACCIDENT_NO"])
accident["region"] = accident["lgaCode"].map(
    lambda c: "Metropolitan Melbourne" if c in metro_codes else "Regional Victoria")
accident.loc[~has_node, "region"] = "Unknown"   # no location recorded: not counted in either region

# ------------------------------------------------------------ road users
USER = {
    "Drivers": "Driver", "Passengers": "Passenger",
    "Motorcyclists": "Motorcyclist", "Pillion Passengers": "Motorcyclist",
    "Pedestrians": "Pedestrian", "Bicyclists": "Cyclist",
    "E-scooter Rider": "Other or unknown", "Not Known": "Other or unknown",
}
INJ = {"1": "Killed", "2": "Seriously injured", "3": "Other injury", "4": "Not injured"}
person["road_user"] = person["ROAD_USER_TYPE_DESC"].map(USER).fillna("Other or unknown")
person["outcome"] = person["INJ_LEVEL"].map(INJ)
person = person.merge(accident[["ACCIDENT_NO", "year", "hour", "region"]], on="ACCIDENT_NO")
recent_p = person[person["year"].between(*RECENT)]
recent_a = accident[accident["year"].between(*RECENT)]
ksi = lambda df: df[df["outcome"].isin(["Killed", "Seriously injured"])]

# 1. One row per person killed (waffle chart + road-user trend)
killed = person[person["outcome"] == "Killed"]
killed[["year", "road_user"]].sort_values(["year", "road_user"]).to_csv(
    OUT / "people_killed.csv", index=False)

# 2. Annual killed / seriously injured by region
annual = (ksi(person)[lambda d: d["region"] != "Unknown"].groupby(["year", "region", "outcome"]).size()
          .unstack(fill_value=0).reset_index()
          .rename(columns={"Killed": "killed", "Seriously injured": "seriously_injured"}))
annual.to_csv(OUT / "annual_region.csv", index=False)

# 3. Injury crashes per month (all years)
monthly = (accident.groupby(["year", "month"]).size().rename("crashes").reset_index())
monthly.to_csv(OUT / "monthly_crashes.csv", index=False)

# 4. Outcome of everyone involved, by road user (recent window)
outcome = (recent_p[recent_p["road_user"] != "Other or unknown"]
           .groupby(["road_user", "outcome"]).size().rename("people").reset_index())
outcome.to_csv(OUT / "user_outcome.csv", index=False)

# 5. Crashes by weekday x hour x severity (recent window)
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
hd = (recent_a[recent_a["DAY_WEEK_DESC"].isin(DAYS)]
      .groupby(["DAY_WEEK_DESC", "hour", "severity"]).size().rename("crashes").reset_index()
      .rename(columns={"DAY_WEEK_DESC": "day"}))
hd.to_csv(OUT / "crashes_day_hour.csv", index=False)

# 6. People killed or seriously injured by hour and road user (recent window)
hu = (ksi(recent_p)[lambda d: d["road_user"] != "Other or unknown"]
      .groupby(["road_user", "hour"]).size().rename("people").reset_index())
hu.to_csv(OUT / "ksi_user_hour.csv", index=False)

# 7. Crash severity by posted speed limit (recent window, valid zones only)
sz = recent_a[recent_a["SPEED_ZONE"].isin(["040", "050", "060", "070", "080", "100", "110"])]
speed = (sz.groupby(["SPEED_ZONE", "severity"]).size().unstack(fill_value=0).reset_index())
speed["speed_limit"] = speed["SPEED_ZONE"].astype(int)
speed = speed.rename(columns={"Fatal": "fatal", "Serious injury": "serious", "Other injury": "other"})
speed["crashes"] = speed[["fatal", "serious", "other"]].sum(axis=1)
speed[["speed_limit", "crashes", "fatal", "serious", "other"]].to_csv(OUT / "speed_zone.csv", index=False)

# 8. Crashes per council (recent window) + map label points
lga = (recent_a.dropna(subset=["lgaCode"])
       .assign(ksi=lambda d: d["severity"].isin(["Fatal", "Serious injury"]),
               fatal=lambda d: d["severity"] == "Fatal")
       .groupby("lgaCode").agg(crashes=("ACCIDENT_NO", "size"),
                               ksi_crashes=("ksi", "sum"), fatal_crashes=("fatal", "sum"))
       .reset_index())
pts = pd.read_csv(OUT / "lga_points.csv", dtype={"lgaCode": str})
lga = pts.merge(lga, on="lgaCode", how="left").fillna(0)
lga.to_csv(OUT / "lga_crashes.csv", index=False)

# 9. Location of every fatal crash (recent window)
def zone(z):
    z = int(z)
    if z <= 50: return "50 km/h or less"
    if z <= 60: return "60 km/h"
    if z <= 90: return "70 to 90 km/h"
    if z <= 110: return "100 to 110 km/h"
    return "Not recorded"
fatal = recent_a[recent_a["severity"] == "Fatal"].dropna(subset=["LATITUDE"]).copy()
fatal["speed_group"] = fatal["SPEED_ZONE"].map(zone)
fatal["lat"] = fatal["LATITUDE"].astype(float).round(4)
fatal["lon"] = fatal["LONGITUDE"].astype(float).round(4)
fatal[["year", "lat", "lon", "speed_group", "region"]].to_csv(OUT / "fatal_crashes.csv", index=False)

print("Done. Files written to", OUT)
