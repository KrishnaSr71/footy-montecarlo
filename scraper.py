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
    
    ## Scrape interval data for single team
    def get_team_stats(self, team_name, team_url):
        soup = self.__soup(team_url)

        # xg(a) stats
        xga_stats = self.get_xga(soup)


        result = {
            "team_name": team_name,
            "team_url": team_url,
            "interval_stats": {
                "home_scored": None,
                "away_scored": None,
                "home_conceded": None,
                "away_conceded": None,
            },
            "home_xg": xga_stats["home_xg"],
            "away_xg": xga_stats["away_xg"],
            "home_xga": xga_stats["home_xga"],
            "away_xga": xga_stats["away_xga"],
            "raw_soup": soup,
        }

        return result
    
if __name__ == "__main__":
    scraper = Scraper(delay=2.0)

    ### === GET TEAMS IN LEAGUE === ###
    # Get all teams in Serie A
    teams = scraper.get_teams(league="italy")
    # Print name + url
    for r in teams:
        print(r["team_name"], r["team_url"])

    
    print("/==========================/")
    
    ### === GET TEAM STATS === ###
    # Get first team
    stats = scraper.get_team_stats(team_name=teams[0]["team_name"],  team_url=teams[0]["team_url"])
    print(teams[0]["team_name"])
    # Print home xg, xga
    print(f"Home: {stats["home_xg"]} scored, {stats["home_xga"]} conceded")
    # Print away xg, xga
    print(f"Away: {stats["away_xg"]} scored, {stats["away_xga"]} conceded")
                
    


