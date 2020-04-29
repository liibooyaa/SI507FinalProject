from bs4 import BeautifulSoup
import requests
import json
import secrets
import sqlite3
from flask import Flask, render_template, request
import plotly.graph_objects as go

base_url='https://www.rottentomatoes.com/'
endpoint_url='http://www.omdbapi.com/'
client_key = secrets.API_KEY
DB_NAME = 'bestmovies.sqlite'

CACHE_FILENAME = "cache.json"
CACHE_DICT = {}


# PART 1 Web Crawling in Rotten Tomatoes

def open_cache():
    ''' Opens the cache file if it exists and loads the JSON into
    the CACHE_DICT dictionary.
    if the cache file doesn't exist, creates a new cache dictionary
    
    Parameters
    ----------
    None
    
    Returns
    -------
    The opened cache: dict
    '''
    try:
        cache_file = open(CACHE_FILENAME, 'r')
        cache_contents = cache_file.read()
        cache_dict = json.loads(cache_contents)
        cache_file.close()
    except:
        cache_dict = {}
    return cache_dict

def save_cache(cache_dict):
    ''' Saves the current state of the cache to disk
    
    Parameters
    ----------
    cache_dict: dict
        The dictionary to save
    
    Returns
    -------
    None
    '''
    dumped_json_cache = json.dumps(cache_dict)
    fw = open(CACHE_FILENAME,"w")
    fw.write(dumped_json_cache)
    fw.close() 

def build_genre_url_dict():
    ''' Make a dictionary that maps genre to genre page url from "https://www.rottentomatoes.com/top/bestofrt/"

    Parameters
    ----------
    None

    Returns
    -------
    dict
        key is a genre name and value is the url
        e.g. {'comedy':'https://www.rottentomatoes.com/top/bestofrt/top_100_comedy_movies/', ...}
    '''

    genre_url_dict={}
    url=base_url+'/top/bestofrt/'
    if url in CACHE_DICT.keys():
        print("Using Cache")
        response = CACHE_DICT[url]
        soup = BeautifulSoup(response, 'html.parser')
    else:
        print("Fetching")
        response = requests.get(url)
        CACHE_DICT[url] = response.text
        save_cache(CACHE_DICT)
        soup = BeautifulSoup(response.text, 'html.parser')
    lis=soup.find('ul',class_='dropdown-menu').find_all('li')
    for li in lis:
        genre_url=base_url+li.find('a')['href']
        genre=li.find('a').text.strip().lower()
        genre_url_dict[genre]=genre_url 
    return genre_url_dict


class Movie:
    '''a movie

    Instance Attributes
    -------------------
    rank: string
        the rank of a movie in a certain category(e.g. '1.', '2.')
    
    title: string
        the title of a movie (e.g. 'Coco')

    score: string
        the score of a movie (e.g. '97%')

    url: string
        the url of a movie (e.g. 'https://www.rottentomatoes.com/m/lady_bird')
    '''
    def __init__(self,tr):
        self.rank=int(tr.find('td', class_='bold').text.strip().strip('.'))
        self.title=tr.find('a', class_='unstyled articleLink').text.strip()
        self.score=int(tr.find('span', class_='tMeterScore').text.strip().strip('%'))
        self.url='https://www.rottentomatoes.com'+tr.find('a', class_='unstyled articleLink')['href']
    

    def info(self):
        '''Get basic information of a movie.

        Parameters
        ----------
        none

        Returns
        -------
        str
            The basic information about a movie in the format of "rank title: scores
        '''
        info=f"{self.rank} {self.title}: {self.score}"
        return info
    
    def create_bestmovies_json(self):
        bestmoviesdic={'rank':self.rank, 'title':self.title, 'score':self.score}
        bestmovies=json.dumps(bestmoviesdic)
        return bestmovies

def get_movies_for_genre(genre_url):
    '''Make a list of movie instances from a genre URL.
    
    Parameters
    ----------
    genre_url: string
        The URL for a movie genre
        
    
    Returns
    -------
    list
        a list of movie instances of the certain genre
    '''
    movies_for_genre=[]
    if genre_url in CACHE_DICT.keys():
        print("Using Cache")
        response= CACHE_DICT[genre_url]
        soup = BeautifulSoup(response, 'html.parser')
    else:
        print("Fetching")
        response = requests.get(genre_url)
        CACHE_DICT[genre_url] = response.text
        save_cache(CACHE_DICT)
        soup = BeautifulSoup(response.text, 'html.parser')
    trs=soup.find('table', class_='table').find_all('tr')
    for tr in trs[1:]:
        instance=Movie(tr)
        movies_for_genre.append(instance)      
    return movies_for_genre




# Part 2 Working with API of The Open Movie Database

def construct_unique_key(endpoint_url, params):
    ''' constructs a key that is guaranteed to uniquely and 
    repeatably identify an API request by its endpoint_url and params
    
    Parameters
    ----------
    endpoint_url: string
        The URL for the API endpoint
    params: dict
        A dictionary of param:value pairs
    
    Returns
    -------
    string
        the unique key as a string
    '''
    param_strings = []
    connector = '_'
    for k in params.keys():
        param_strings.append(f'{k}_{params[k]}')
    param_strings.sort()
    unique_key = endpoint_url + connector + connector.join(param_strings)
    return unique_key


def make_request_with_cache(endpoint_url, client_key, name):
    '''Check the cache for a saved result for this baseurl+params:values
    combo. If the result is found, return it. Otherwise send a new 
    request, save it, then return it.
    
    Parameters
    ----------
    baseurl: string
        The URL for the API endpoint
    phashtag: string
        The hashtag to search (i.e. “#2020election”)
    count: int
        The number of tweets to retrieve
    
    Returns
    -------
    dict
        the results of the query as a dictionary loaded from cache
        JSON
    '''
    params = {'apikey': client_key, 't':name}
    unique_key=construct_unique_key(endpoint_url, params)
    if unique_key in CACHE_DICT.keys():
	    results = CACHE_DICT[unique_key]
    else:
        results = requests.get(endpoint_url, params=params).json()
        CACHE_DICT[unique_key] = results
        save_cache(CACHE_DICT)
    return results




# Part 3 Data Storage
class Film:
    '''a film

    Instance Attributes
    -------------------
    synopsis: string
        the synopsis of a movie 
    
    rating: string
        the rating a national site (e.g. 'G','R')

    genre: string
        the genres of a movie (e.g. 'Classics', 'Comedy', 'Romance')

    director: string
        the director(s) of a movie (e.g. 'Mark Sandrich')

    writer: string
        the writers a movie (e.g. 'Dwight Taylor, Allan Scott')

    time: string
        the release time of a movie (e.g. 'Sep 6, 1935')

    box: string
        the box office of a movie (e.g. '$48,285,330')

    length: string
        the length of a movie in minutes (e.g. '93 minutes')

    studio: string
        the studio that produced the movie (e.g. 'Turner Home Entertainment')

    actors: string
        the actors of a movie (e.g. 'Tom Hanks, Tim Allen, Annie Potts, Tony Hale')
    '''
    def __init__(self,movie_title, movie_url):
        if movie_url in CACHE_DICT.keys():
            print("Using Cache")
            response= CACHE_DICT[movie_url]
            soup = BeautifulSoup(response, 'html.parser')
        else:
            print("Fetching")
            response = requests.get(movie_url)
            CACHE_DICT[movie_url] = response.text
            save_cache(CACHE_DICT)
            soup = BeautifulSoup(response.text, 'html.parser')
        
        self.synopsis=soup.find('div',id='movieSynopsis').text.strip()

        lis=soup.find('ul', class_='content-meta info').find_all('li')

        self.rating=lis[0].find('div',class_='meta-value').text.strip()

        director_list=''
        directors=lis[2].find('div', class_='meta-value').find_all('a')
        for director in directors:
            if director_list=='':
                director_list=director_list+director.text.strip()
            else:
                director_list=director_list+", "+director.text.strip()
        self.director=director_list

        writer_list=''
        writers=lis[3].find('div', class_='meta-value').find_all('a')
        for writer in writers:
            if writer_list=='':
                writer_list=writer_list+writer.text.strip()
            else:
                writer_list=writer_list+", "+writer.text.strip()
        self.writer=writer_list

        self.time=lis[4].find('div',class_='meta-value').find('time').text.strip()
        self.studio=lis[-1].find('div',class_='meta-value').text.strip()

        results=make_request_with_cache(endpoint_url, client_key, movie_title[0:-7])  
        try:
            self.length=results['Runtime']
        except:
            self.length=None
        
        try:
            self.actors=results['Actors']
        except:
            self.actors=None
        
        try:
            self.language=results['Language']
        except:
            self.language=None
        
        try:
            self.country=results['Country']
        except:
            self.country=None

        try:
            self.awards=results['Awards']
        except:
            self.awards=None
        
        try:
            self.metascore=results['Metascore']
        except:
            self.metascore=None
        
        try:
            self.imdb=results['imdbRating']
        except:
            self.imdb=None

        self.rottentomatoes=None
        
        try:
            ratings=results['Ratings']
            for source in ratings:
                if source['Source']=='Rotten Tomatoes':
                    self.rottentomatoes=int(source['Value'].strip("%"))
        except:
            pass
                


    def info(self):
        '''Get detailed information of a film.

        Parameters
        ----------
        none

        Returns
        -------
        str
            The detailed information about a movie including a synopsis, its rating, genres, director, writers, release time, box office, runtime and studio
        '''
        info=f"Synopsis:\n{self.synopsis}\nRating:{self.rating}\nDirected By: {self.director}\nWritten By: {self.writer}\nIn Theaters: {self.time}\nRuntime: {self.length}\nStudio: {self.studio}\nActors: {self.actors}\nMetascore: {self.metascore}\nimdbRating: {self.imdb}"
        return info


def create_db():
    '''Create a database to store information of movies.
    
    Parameters
    ----------
    none

    Returns
    -------
    none
    '''
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    drop_bestmovies_sql = 'DROP TABLE IF EXISTS "BestMovies"'
    drop_ratings_sql = 'DROP TABLE IF EXISTS "Ratings"'
    drop_movieinfo_sql = 'DROP TABLE IF EXISTS "MovieInfo"'

    create_bestmovies_sql = '''
        CREATE TABLE IF NOT EXISTS "BestMovies" (
            "Rank" INTEGER PRIMARY KEY,
            "Title" TEXT NOT NULL, 
            "Score" INTEGER
        )
    '''
    create_ratings_sql = '''
        CREATE TABLE IF NOT EXISTS 'Ratings'(
            "Rank" INTEGER PRIMARY KEY,
            'Title' TEXT NOT NULL,
            'RottenTomatoes' INTEGER,
            'Metacritic' REAL,
            'IMDB' REAL
        )
    '''
    create_movieinfo_sql = '''
        CREATE TABLE IF NOT EXISTS 'MovieInfo'(
            "Rank" INTEGER PRIMARY KEY,
            'Title' TEXT NOT NULL,
            'Rating' TEXT NOT NULL,
            'Synopsis' TEXT NOT NULL,
            'Director' TEXT NOT NULL,
            'Writers' TEXT NOT NULL,
            'ReleaseTime' TEXT NOT NULL,
            'Length' INTEGER,
            'Studio' TEXT NOT NULL,
            'Actors' TEXT,
            'Language' TEXT,
            'Country' TEXT,
            'Awards' TEXT
        )
    '''
    cur.execute(drop_bestmovies_sql)
    cur.execute(drop_ratings_sql)
    cur.execute(drop_movieinfo_sql)
    cur.execute(create_ratings_sql)
    cur.execute(create_bestmovies_sql)
    cur.execute(create_movieinfo_sql)
    conn.commit()
    conn.close()


def load_bestmovies(movies_for_genre): 
    '''Fill the table of BestMovies with data 
    
    Parameters
    ----------
    movies_for_genre: list
        a list of instances of class Film with attribiutes of rank, title and score scraped from Rotten Tomatos website

    Returns
    -------
    none
    '''
    insert_country_sql = '''
        INSERT INTO BestMovies
        VALUES (?, ?, ?)
    '''

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    for c in movies_for_genre:
        cur.execute(insert_country_sql,
            [
                c.rank,
                c.title,
                c.score
            ]
        )
    conn.commit()
    conn.close()

def load_ratings(index, movie_title, movie_url): 
    '''Fill the table of Ratings with data 
    
    Parameters
    ----------
    index: integer
        the rank of a movie selected by a user
    movie_title: str
        the title of a movie selected by a user
    movie_url: 
        the url of a movie selected by a user

    Returns
    -------
    none
    '''
    rank=index+1
    film=Film(movie_title, movie_url)

    insert_country_sql = '''
        INSERT INTO Ratings
        VALUES (?, ?, ?, ?, ?)
    '''

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(insert_country_sql,
        [   
            rank,
            movie_title,
            film.rottentomatoes,
            film.metascore,
            film.imdb
        ]
    )
    conn.commit()
    conn.close()


def load_movieinfo(index, movie_title, movie_url): 
    '''Fill the table of MovieInfo with data 
    
    Parameters
    ----------
    index: integer
        the rank of a movie selected by a user
    movie_title: str
        the title of a movie selected by a user
    movie_url: 
        the url of a movie selected by a user

    Returns
    -------
    none
    '''
    rank=index+1
    movieinfo = Film(movie_title, movie_url)

    insert_country_sql = '''
        INSERT INTO MovieInfo
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(insert_country_sql,
        [
            rank,
            movie_title,
            movieinfo.rating,
            movieinfo.synopsis,
            movieinfo.director,
            movieinfo.writer,
            movieinfo.time,
            movieinfo.length,
            movieinfo.studio,
            movieinfo.actors,
            movieinfo.language,
            movieinfo.country,
            movieinfo.awards
        ]
    )
    conn.commit()
    conn.close()



#Part 4 Data Presentation

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/best_movies', methods=['POST'])
def handle_the_form():

    genre = request.form["genre"]
    genre_url_dict=build_genre_url_dict()
    movies_for_genre=get_movies_for_genre(genre_url_dict[genre.lower()])
    create_db()
    load_bestmovies(movies_for_genre)
    for index in range(len(movies_for_genre)):
        load_ratings(index, movies_for_genre[index].title, movies_for_genre[index].url)
        load_movieinfo(index, movies_for_genre[index].title, movies_for_genre[index].url)


    conn = sqlite3.connect('bestmovies.sqlite')
    cur = conn.cursor()
    q = '''
        SELECT Rank, Title, Score
        FROM BestMovies
    '''
    results = cur.execute(q).fetchall()
    conn.close()
    
    return render_template('results.html', genre=genre, results=results)


@app.route('/movie_info', methods=['POST'])
def handle_the_movie():

    number = request.form["name"]

    conn = sqlite3.connect('bestmovies.sqlite')
    cur = conn.cursor()
    q = '''
        SELECT Rank, Title, RottenTomatoes, Metacritic, IMDB
        FROM Ratings
    '''
    q2 = '''
        SELECT *
        FROM MovieInfo
    '''
    results = cur.execute(q).fetchall()
    results2 = cur.execute(q2).fetchall()
    conn.close()

    x_vals = ['Average', 'Rotten Tomatoes', 'Metacritic', 'IMDB']
    y_vals=[]
    for row in results:
        if row[0]==int(number):
            try:
                avg=(row[2]+row[3]+(row[4]*10))/3
                y_vals.append(avg)
                y_vals.append(row[2])
                y_vals.append(row[3])
                y_vals.append(row[4]*10)
                bars_data = go.Bar(
                x=x_vals,
                y=y_vals
                )
                fig = go.Figure(data=bars_data)
                div = fig.to_html(full_html=False)
            except:
                div=None

        for row in results2:
            if row[0]==int(number):
                title=row[1]
                synopsis=row[3]
                rating=row[2]
                director=row[4]
                writer=row[5]
                time=row[6]
                length=row[7]
                studio=row[8]
                actors=row[9]
                language=row[10]
                country=row[11]
                awards=row[12]
    
    return render_template("plot.html", plot_div=div, title=title, synopsis=synopsis, rating=rating, director=director, writer=writer, time=time, length=length, 
            studio=studio, actors=actors, language=language, country=country, awards=awards) 


if __name__ == "__main__":
    app.run(debug=True)
    # genre_url_dict=build_genre_url_dict()
    # while True:
    #     genre_name=input('Enter a movie genre or "exit": ')
    #     if genre_name=="exit":
    #         break
    #     elif genre_name.lower() in genre_url_dict.keys():
    #         movies_for_genre=get_movies_for_genre(genre_url_dict[genre_name.lower()])
    #         print("-----------------------------------")
    #         print(f"List of top {genre_name} movies")
    #         print("-----------------------------------")
    #         for movies in movies_for_genre:
    #             print(movies.info())
    #         while True:
    #             number=input('Choose the number for detailed information or "exit" or "back": ')
    #             if number=="back":
    #                 break
    #             elif number.isnumeric():
    #                 if 0<int(number)<=len(movies_for_genre):
    #                     index=int(number)-1
    #                     print(Film(movies_for_genre[index].title, movies_for_genre[index].url).info())
    #                 else:
    #                     print("[Error] Invalid input")
    #                     print("-------------------------------\n")
    #             elif number=="exit":
    #                 quit()
    #             else:
    #                 print("[Error] Invalid input")
    #                 print("-------------------------------\n")


