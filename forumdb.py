#
# Database access functions for the web forum.
# 

import time
import psycopg2
import bleach

## Database connection
#DB=[]
counter=0
#time to init counter
## Get posts from database.
def GetAllPosts():
    '''Get all the posts from the database, sorted with the newest first.
    
    Returns:
      A list of dictionaries, where each dictionary has a 'content' key
      pointing to the post content, and 'time' key pointing to the time
      it was posted.
    '''
    query = "select * from posts"
    connection = psycopg2.connect(dbname="forum")
    cursor = connection.cursor()
    cursor.execute(query)
    response = cursor.fetchall()
    connection.close()
    posts = [{'content': str(row[1]), 'time': str(row[0])} for row in response]
    posts.sort(key=lambda row: row['time'], reverse=True)
    return posts

## Add a post to the database.
def AddPost(content):
    '''Add a new post to the database.

    Args:
      content: The text content of the new post.
    '''
    content = bleach.clean(content)
    query = "insert into posts values (content, t, counter)"
    coutnter=counter+1
    t = time.strftime('%c', time.localtime())
    connection = psycopg2.connect(dbname="forum")
    cursor = connection.cursor()
    cursor.execute("""insert into posts
                   (content, time) values (%s, %s)""", (content, t,))
    connection.commit()
    connection.close()
    #DB.append((t, content))
