from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time
import pymongo

"""
    Quick Readme:

    Before using any other methods, call all three of the 'update' methods to generate their respective JSON files.
    After they've been run once they needn't be run again unless the season changes/new players/teams are added to the 
    league. For all subsequent executions use the 'load' function for players, teams, and season to load everything at the 
    top of the 'main' section.

    Requesting 'totals' for many players consecutively/iteratively is still buggy -- the browser/NBA doesn't like the 
    rapid-fire autoclicking, and will sometimes just stop showing the stats for a few players at a time.

    If you remove the try-finally loop from the 'main' section be sure to close all the windows after the program runs.
"""

# Put in your MongoDB user information in the client connection String
# Mongo's Atlas can autogenerate a String for you upon trying to connect to your database via a Python shell
client = pymongo.MongoClient("[CLIENT_CONNECTION_STRING]")
db = client['stats']

# Sets up (Firefox) webdriver used for Selenium scraping
options = webdriver.FirefoxOptions()
# Replace the path String with the path to your gecko driver (make sure that folder's in your system PATH too)
driver = webdriver.Firefox(executable_path=r'PATH_TO_GECKO_DRIVER')

players = {}
teams = {}
current_season = {}

# The two starting zeroes allow for easier indexing in get_stat/format_statline methods
stat_types = ['0', '0', 'age', 'gp', 'gs', 'min', 'pts', 'fgm', 'fga', 'fg%',
                '3pm', '3pa', '3p%', 'ftm', 'fta', 'ft%', 'oreb', 'dreb',
                'reb', 'ast', 'stl', 'blk', 'tov', 'pf']

# Creates a JSON file with the current season (only need to run once)
def update_season():
    driver.get('https://stats.nba.com/team/1610612747/traditional/')
    driver.find_element_by_class_name('label').click()
    current_season = driver.find_element_by_tag_name('option').get_attribute('label')  
    with open('currentseason.json', 'w+') as seasonfile:
        seasonfile.write('{\n\t"current_season":"')
        seasonfile.write(current_season)
        seasonfile.write('"\n}')

# Creates a JSON file with all current players / their ID (only need to run once)
def update_players():
    driver.get('https://stats.nba.com/players/list')
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.players-list__name a')))

    containerlist = driver.find_elements_by_css_selector('.players-list__name a')

    playersfile = open('players.json', 'w+')

    # JSON wasn't cooperating -- devised a (janky) manual file creation
    playersfile.truncate(0)
    playersfile.write('{\n')
    first = True

    for player in containerlist:
        if not first: playersfile.write('",\n')
        else: first = False
        playersfile.write('\t"' + player.get_attribute('innerHTML').replace('.', '') + '":"' + player.get_attribute('href').split('/player/')[1].split('/')[0])
    playersfile.write('"\n}')

# Creates a JSON file with all current players / their ID (only need to run once)
def update_teams():
    driver.get('https://stats.nba.com/teams/')
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.stats-team-list__link')))

    teamids = driver.find_elements_by_css_selector('.stats-team-list__link')
    teamnames = driver.find_elements_by_css_selector('.stats-team-list__link img')

    teamsfile = open('teams.json', 'w+')

    # JSON wasn't being particularly cooperative -- devised a (janky) manual file creation
    teamsfile.truncate(0)
    teamsfile.write('{\n')
    first = True

    for i in range(0, len(teamnames)):
        if not first: teamsfile.write('",\n')
        else: first = False
        teamname = teamnames[i].get_attribute('title').split(' logo')[0]
        teamid = teamids[i].get_attribute('href').split('/')[4]
        teamsfile.write('\t"' + teamname + '":"' + teamid)
    teamsfile.write('"\n}')

# Loads either player or team IDs from their respective JSON files
def load_from_json(param):
    if param == 'players':
        file = open('players.json', 'r')
    elif param == 'teams':
        file = open('teams.json', 'r')
    elif param == 'season':
        file = open('currentseason.json', 'r')

    for line in file:
        try:
            e1 = line.split('"')[1]
            e2 = line.split('"')[3]
        except:
            continue
        if param == 'players':
            players[e1] = e2
        elif param == 'teams':
            teams[e1] = e2
        elif param == 'season':
            current_season['current'] = e2

# Gets a stat row for a player during a particular year (params are the player's name (not their ID))
def get_stat_line(player, *args, **kwargs):
    permode = kwargs.get('permode', 'pergame')
    season = kwargs.get('season', current_season['current'])
    seasontype = kwargs.get('seasontype', 'regular')

    driver.get('https://stats.nba.com/player/' + players[player] + '/career')
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.player span a')))

    try:
        # Set per mode if specified (default is 'per game')
        driver.find_element_by_name('PerMode').click()
        if permode == 'totals':
            driver.find_elements_by_css_selector('option')[0].click()
        elif permode == 'per36':
            driver.find_element_by_css_selector('option')[2].click()

        # Sets stat type -- regular season (default) or playoffs
        if seasontype == 'regular':
            seasontype = 0
        else:
            seasontype = 1

        table = driver.find_elements_by_tag_name('nba-stat-table')[seasontype].find_element_by_tag_name('tbody')
        statlines = table.find_elements_by_tag_name('tr')
        for statline in statlines:
            if statline.find_elements_by_tag_name('td')[0].find_element_by_tag_name('a').get_attribute('innerHTML') == season:
                return statline.find_elements_by_tag_name('td')
        return None
    except:
        return None

# Formats a statline
def format_statline(player, *args, **kwargs):
    season = kwargs.get('season', current_season['current'])
    seasontype = kwargs.get('seasontype', 'regular')
    permode = kwargs.get('permode', 'pergame')

    stats = {}

    statline = get_stat_line(player, *args, **kwargs)

    if statline == None: return None
    try:
        stats['_id'] = players[player]
        stats['name'] = player
        stats['season'] = season
        stats['seasontype'] = seasontype
        stats['permode'] = permode
        stats['team'] = statline[1].find_element_by_css_selector('.text span').get_attribute('innerHTML')
        for i in range(2, len(statline)):
            stats[stat_types[i]] = statline[i].get_attribute('innerHTML')
        return stats
    except:
        return None
    
#Returns a list of the games for the next week
def get_schedule():
    driver.get('https://stats.nba.com/schedule/#')
    try:
        # Pop-up -- may need changing to id future ads
        WebDriverWait(driver, 9).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.denver-CloseButton')))
        driver.find_element_by_css_selector('.denver-CloseButton').click()
    except Exception as e: print(e)

    dates = []

    game_days = driver.find_elements_by_css_selector('.schedule-content')

    for gd in game_days:
        gd_date = gd.find_element_by_css_selector('a').get_attribute('href').split('scores/')[1]
        sched_games = gd.find_elements_by_class_name('schedule-game__inner')
        for g in sched_games:   
            g_dict = {}
            g_dict['date'] = gd_date     
            g_dict['_id'] = g.get_attribute('id').split('_')[1]
            g_dict['time'] = g.find_element_by_css_selector('.schedule-game__status').find_element_by_tag_name('span').get_attribute('innerHTML')
            gd_card = g.find_element_by_class_name('schedule-game__score-card')
            gd_teams = gd_card.find_elements_by_css_selector('.schedule-game__team')
            g_dict['teams'] = []
            for t in gd_teams:
                g_dict['teams'].append(t.find_element_by_tag_name('a').get_attribute('innerHTML'))
            dates.append(g_dict)
    return dates

# Returns a list of the games today
def get_games_today(*args, **kwargs):
    printall = kwargs.get('printall', False)

    driver.get('https://www.nba.com/scores#/')
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CLASS_NAME, 'calendar_day')))

    games = []
    for game in driver.find_elements_by_class_name('score-tile-wrapper'):
        games.append(game.get_attribute('metadata-gameid'))
    
    if printall:
        for game in games:
            print(game)
        if not games:
            print('No games scheduled for today')
    return games

# Gets all players' stats in a game (only for completed games)
def get_game_stats(game):
    gameurl = 'https://stats.nba.com/game/' + game
    driver.get(gameurl)
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.player a')))

    teamnames = []
    for name in driver.find_elements_by_class_name('nba-stat-table__caption'):
        teamnames.append(name.get_attribute('innerHTML').strip())
    ti = 0
    
    ps = []
    for table in driver.find_elements_by_class_name('nba-stat-table__overflow'):
        ps.append((teamnames[ti],table.find_elements_by_css_selector('tbody tr')))
        ti = 1

    stats_dicts = write_players_stats(ps)
    over_dict = {game: {}}
    over_dict[game][list(stats_dicts[0])[0]] = stats_dicts[0][list(stats_dicts[0])[0]]
    over_dict[game][list(stats_dicts[1])[0]] = stats_dicts[1][list(stats_dicts[1])[0]]
    return over_dict

# Helper method for get_game_stats
def write_players_stats(ps):
    dicts = []
    statheaders = ['minutes', 'fgm', 'fga', 'fg%', '3pm', '3pa', '3p%', 'ftm', 'fta', 'ft%', 'oreb', 'dreb', 'reb', 'ast', 'tov', 'stl', 'blk', 'pf','pts', '+/-']

    for player in ps:
        team_dict = {player[0]: {}}
        for p in player[1]:
            statline = p.find_elements_by_tag_name('td')
            pnsplit = statline[0].find_element_by_tag_name('a').get_attribute('innerHTML').split('<')
            player_name = pnsplit[0].replace('.', '')
            team_dict[player[0]][player_name] = {}
            try:
                if p.find_element_by_tag_name('sup').get_attribute('innerHTML') != '':
                    started = 'yes'
                else:
                    started = 'no'
            except:
                started = 'no'
            team_dict[player[0]][player_name]['started'] = started
       
            for i in range(1, len(statline)):
                try:
                    nextstat = statline[i].get_attribute('innerHTML').split('>')[1].split('<')[0].strip()
                except:
                    nextstat = statline[i].get_attribute('innerHTML').strip()
                if nextstat == '':
                    nextstat = '0'
                team_dict[player[0]][player_name][statheaders[i-1]] = nextstat
                if nextstat == '0' and statheaders[i-1] == 'minutes':
                    break
        dicts.append(team_dict)       
    return dicts

# Writes player data to Atlas based on a char
def write_by_alpha(alphastring):
    for player in players:
        try:
            if player.startswith(alphastring):
                sl = format_statline(player)
                send_data(sl)
        except Exception as e:
            print(player)
            continue

# Sends data to a database
def send_data(entry):
    if not entry:
        print('Invalid entry:')
        return

    # Make sure you're sending to the right database collection


    # Use for adding games to db.schedule; duplicates will appear in the console as a key error (and not be added)
    # try:
    #     db.schedule.insert_one(entry)
    # except Exception as e: print(e)
    
    # Use for adding game stats to db.games
    # try:
    #     db.games.insert_one(entry)
    # except:
    #     db.games.delete_one({'_id':entry['_id']})
    #     db.games.insert_one(entry)

# 'main' section
try:
    load_from_json('teams')
    load_from_json('players')
    load_from_json('season')

finally:
     driver.quit()