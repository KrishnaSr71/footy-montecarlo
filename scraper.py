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

BASE = "https://www.soccerstats.com/"
INTERVALS = ["0-15", "16-30", "31-45", "46-60", "61-75", "76-90"]
LEAGUES = ["italy", "england", "spain", "france", "germany"]

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
            "home": __get_ha("Home"),
            "away": __get_ha("Away")
        }

    def get_intervals(self, soup, games):

        def __get_goals(suffix, scored, conceded):
            label = soup.find("label", attrs={"for": lambda f: f and "SCT" in f and f.endswith(suffix)})
            rows = label.find_next("div", class_="tab").find_all("table")[1].find_all("tr", class_=["trow2", "trow8"])
            if not rows: return None

            flip = 1 # GF/GA extraction helper
            counter = 0 # Early break
        
            for row in rows: 
                if counter > 11: break
                # For GF, use 2nd entry in the table. For GA, use 1st entry.
                goals = row.find_all("td")[flip+1].text.strip()
                if flip: scored.append(round(float(goals) / float(games["home"]), 4))
                else: conceded.append(round(float(goals) / float(games["away"]), 4))

                flip ^= 1
                counter += 1

            print(f'scored: {scored}')
            print(f'conceded: {conceded}')
        
        home_scored, home_conceded = [], [];
        away_scored, away_conceded = [], [];

        __get_goals("_2", home_scored, home_conceded)
        __get_goals("_3", away_scored, away_conceded)
            
        return {
            "home_scored": home_scored,
            "away_scored": away_scored,
            "home_conceded": home_conceded,
            "away_conceded": away_conceded,
        }
    
    ## Scrape interval data for single team
    def get_team_stats(self, team_name, team_url):
        soup = self.__soup(team_url)

        # xg(a) stats
        xga_stats = self.get_xga(soup)
        game_stats = self.get_games(soup)
        interval_stats = self.get_intervals(soup, game_stats)

        result = {
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
    
if __name__ == "__main__":
    scraper = Scraper(delay=2.0)

    ### === GET TEAMS IN LEAGUE === ###
    # Get all teams in Serie A
    for league in LEAGUES:
        teams = scraper.get_teams(league=league)
        # Print name + url
        for r in teams:
            print(r["team_name"], r["team_url"])
        print("/==========================/")

    
    # print("/==========================/")
    
    # ### === GET TEAM STATS === ###
    # # Get first team
    # stats = scraper.get_team_stats(team_name="Inter Milan",  team_url="https://www.soccerstats.com/teamstats.asp?league=italy&stats=u1289-inter-milan")
    # print(f"Stats: {stats}")


