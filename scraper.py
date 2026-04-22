### Scrapes Data Aggregators (SoccerSTATs.com, Fotmob, etc.) for statistics:
#       - Context: Year, Country, League, Team Name
#       - Interval: Home, away scoring rate per min interval: [0-15 to 75-90]
#                   Home, away conceding rate per min interval: [0-15 to 75-90]
#       - Aux Stats: Home/away xG(A), corners, possession, penalties, fouls, cards
#       - Multipliers: Home/away scoring/defense multipliers.

import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import json
import os
import sys

BASE = "https://www.soccerstats.com/"
INTERVALS = ["0-15", "16-30", "31-45", "46-60", "61-75", "76-90"]
LEAGUES = ["italy", "england", "spain", "france", "germany"]
CACHE_DIR = "cache"

class Scraper:
    def __init__(self, delay=1.5, timeout=15):
        self.session = requests.session()
        self.delay = delay
        self.timeout = timeout

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })

    def __sleep(self):
        time.sleep(self.delay)
    
    def __get(self, url):
        self.__sleep()
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp
    
    def __soup(self, url):
        resp = self.__get(url)
        return BeautifulSoup(resp.text, "html.parser")
    
    def league_url(self, league):
        return urljoin(BASE, f"latest.asp?league={league}")
    
    def get_league(self, league):
        lgurl = self.league_url(league)
        soup = self.__soup(lgurl)

        return lgurl, soup

    ## Get all teams in a league
    def get_teams(self, league):
        lgurl, soup = self.get_league(league)

        teams = []
        seen = set() # NO DUPLICATES

        for a in soup.find_all("a", href=True): 
            href = a["href"]
            text = a.get_text(" ", strip=True)

            if "teamstats.asp" in href and f"league={league}" in href:
                full_url = urljoin(lgurl, href)
                if full_url not in seen and text:
                    seen.add(full_url)
                    teams.append({
                        "team_name": text,
                        "team_url": full_url
                    })

        return teams
    
    def get_xga(self, soup):
        result = {
            "home_xg": 0.0,
            "away_xg": 0.0,
            "home_xga": 0.0,
            "away_xga": 0.0
        }

        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if not cells: continue

            label = cells[0].text.strip().lower()

            if label == "gf per match":
                result["home_xg"] = float(cells[1].text.strip())
                result["away_xg"] = float(cells[2].text.strip())
            elif label == "ga per match":
                result["home_xga"] = float(cells[1].text.strip())
                result["away_xga"] = float(cells[2].text.strip())
        
        return result

    def get_games(self, soup):
        def __get_ha(ha_string):
            return (soup
              .find("div", style="width:642px;margin-left:4px;margin-right:3px;float:left;")
              .find("td", string=lambda c: c and ha_string.lower() in c.lower())
              .find_next("td").text.strip()
              ) 
        
        return {
            "home": int(__get_ha("Home")),
            "away": int(__get_ha("Away"))
        }

    def get_intervals(self, soup, games):

        def __get_goals(suffix, scored, conceded, games_ct):
            label = soup.find("label", attrs={"for": lambda f: f and "SCT" in f and f.endswith(suffix)})
            rows = label.find_next("div", class_="tab").find_all("table")[1].find_all("tr", class_=["trow2", "trow8"])
            if not rows: return None

            flip = 1 # GF/GA extraction helper
            counter = 0 # Early break
        
            for row in rows: 
                if counter > 11: break
                # For GF, use 2nd entry in the table. For GA, use 1st entry.
                goals = row.find_all("td")[flip+1].text.strip()
                if flip: scored.append(round(float(goals) / games_ct, 4))
                else: conceded.append(round(float(goals) / games_ct, 4))

                flip ^= 1
                counter += 1
        home_scored, home_conceded = [], [];
        away_scored, away_conceded = [], [];

        __get_goals("_2", home_scored, home_conceded, games["home"])
        __get_goals("_3", away_scored, away_conceded, games["away"])
            
        return {
            "home_scored": home_scored,
            "away_scored": away_scored,
            "home_conceded": home_conceded,
            "away_conceded": away_conceded,
        }
    
    ## Scrape interval data for single team
    def get_team_stats(self, team_name, team_url, league):
        soup = self.__soup(team_url)

        # xg(a) stats
        xga_stats = self.get_xga(soup)
        game_stats = self.get_games(soup)
        interval_stats = self.get_intervals(soup, game_stats)

        result = {
            "league": league,
            "team_name": team_name,
            "team_url": team_url,
            "home_games": game_stats["home"],
            "away_games": game_stats["away"],
            "interval_stats": {
                "home_scored": interval_stats["home_scored"],
                "away_scored": interval_stats["away_scored"],
                "home_conceded": interval_stats["home_conceded"],
                "away_conceded": interval_stats["away_conceded"],
            },
            "home_xg": xga_stats["home_xg"],
            "away_xg": xga_stats["away_xg"],
            "home_xga": xga_stats["home_xga"],
            "away_xga": xga_stats["away_xga"],
            # "raw_soup": soup,
        }

        return result

    def save_team(self, team_data):
        league = team_data["league"]
        league_dir = os.path.join(CACHE_DIR, league)
        os.makedirs(league_dir, exist_ok=True)
        name = team_data["team_name"].lower().replace(" ", "_")
        path = os.path.join(league_dir, f"{name}.json")
        team_data["cached_at"] = time.time()
        with open(path, "w") as f:
            json.dump(team_data, f, indent=2)
        return path

    def load_team(self, team_name, league, max_age_days=100):
        path = os.path.join(CACHE_DIR, league, f"{team_name.lower().replace(' ', '_')}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            data = json.load(f)
        age = time.time() - data.get("cached_at", 0)
        if age > max_age_days * 86400:
            return None
        return data 
    
if __name__ == "__main__":
    scraper = Scraper(delay=3.0)
    use_cache = "--cache" in sys.argv

    if "--help" in sys.argv:
        print("USAGE: python scraper.py; --cache to save/overwrite cache directory.")

    ### === GET TEAM STATS === ###
    # Get all teams in t5 leagues
    for league in LEAGUES:
        for r in scraper.get_teams(league=league):
            try:
                if not use_cache:
                    cached = scraper.load_team(team_name=r["team_name"], league=league)
                    if cached: continue
                    else: 
                        print(f"Error on {r["team_name"]}, no Cache found. Run program again with arg: --cache", file=sys.stderr)
                        continue
                stats = scraper.get_team_stats(team_name=r["team_name"], team_url=r["team_url"], league=league)
                if use_cache: scraper.save_team(stats)
            except Exception as e:
                print(f"Error on {r["team_name"]}: {e}", file=sys.stderr)
