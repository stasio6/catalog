from flask import Flask, render_template, request
from flask import redirect, url_for, flash, jsonify
from flask import session as login_session
from flask import make_response
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
import requests
import random
import string
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Restaurant, MenuItem, User

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu Application"

engine = create_engine('sqlite:///restaurantmenuwithusers.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


#function to create new user
def createUser(login_session):
    newUser = User(name=login_session['username'],
                   email=login_session['email'],
                   picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id

#function that gets user's ID by searching his email
def getUserID(email):
    try:
        user = session.query(User).filter_by(
            email=login_session['email']).one()
        return user.id
    except:
        return None


#function that return user's info by grabing it's ID
def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


#functions that log's user into his g+ account
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    print url
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = access_token
    print "aaaaaaaaaaaaaaaaaaaaaaaa"
    print access_token
    print login_session['access_token']
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    login_session['provider'] = 'google'

    if getUserID(login_session['email']) is None:
        login_session['user_id'] = createUser(login_session)
    else:
        login_session['user_id'] = getUserID(login_session['email'])

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ''' " style = "width: 300px; height: 300px;border-radius:
    150px;-webkit-border-radius:
    150px;-moz-border-radius: 150px;"> '''
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

    # DISCONNECT - Revoke a current user's token and reset their login_session


#function that logs user into his fb account
@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print "access token received %s " % access_token

    app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(
        open('fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/' \
          'access_token' \
          '?grant_type=fb_exchange_token' \
          '&client_id=%s&client_secret=%s&fb_exchange_token=%s' \
          % (app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.4/me"
    # strip expire tag from access token
    token = result.split("&")[0]

    url = 'https://graph.facebook.com/v2.4/me?%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout
    # let's strip out the information before the equals sign in our token
    stored_token = token.split("=")[1]
    login_session['access_token'] = stored_token

    # Get user picture
    url = 'https://graph.facebook.com/v2.4/me/picture?%' \
          's&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: ' \
              '150px;-webkit-border-radius: ' \
              '150px;-moz-border-radius: 150px;"> '

    flash("Now logged in as %s" % login_session['username'])
    return output


#function that disconnects the user
@app.route('/disconnect')
def disconnect():
    access_token = login_session['access_token']
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps(
            'Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    if login_session['gplus_id'] is not None:
        url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' \
              % (login_session['access_token'],)
        print "The url: " + url
        h = httplib2.Http()
        result = h.request(url, 'GET')[0]
        print 'result is '
        print result
        if result['status'] == '200':
            del login_session['access_token']
            login_session['gplus_id'] = None
            login_session['username'] = None
            del login_session['email']
            del login_session['picture']
            response = make_response(json.dumps(
                'Successfully disconnected.'), 200)
            response.headers['Content-Type'] = 'application/json'
            flash("you have been disconnected")
            return redirect('/')
        else:
            response = make_response(
                json.dumps('Failed to revoke token for given user.', 400))
            response.headers['Content-Type'] = 'application/json'
            return response
    else:
        facebook_id = login_session['facebook_id']
        # The access token must me included to successfully logout
        access_token = login_session['access_token']
        url = 'https://graph.facebook.com/%s/permissions?access_token=%s' \
              % (facebook_id, access_token)
        h = httplib2.Http()
        result = h.request(url, 'DELETE')[1]
        print result
        del login_session['access_token']
        login_session['facebook_id'] = None
        login_session['username'] = None
        del login_session['email']
        del login_session['picture']
        response = make_response(
            json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        flash("you have been disconnected")
        return redirect('/')
        return "you have been logged out"


#function that displays all the menu's
@app.route('/')
@app.route('/restaurant')
@app.route('/restaurants')
def showRestaurants():
    if "username" not in login_session:
        login_session["username"] = None
    restaurants = session.query(Restaurant).all()
    print login_session
    if login_session['username'] is not None:
        return render_template("restaurants.html", restaurants=restaurants,
                               login_session=login_session)
    return render_template("publicrestaurant.html", restaurants=restaurants)

#function that displays particular menu
@app.route('/restaurants/<int:restaurant_id>')
def restaurantMenu(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(
        restaurant_id=restaurant.id).all()
    if login_session['username'] is not None \
            and getUserID(login_session['email']) == restaurant.user_id:
        return render_template("menu.html", restaurant=restaurant,
                               items=items, login_session=login_session)
    creator = getUserInfo(restaurant.user_id)
    return render_template("publicmenu.html", restaurant=restaurant,
                           items=items, creator=creator,
                           login_session=login_session)


#Here I'm making the forms to create, edit and delete menu items
@app.route('/restaurants/<int:restaurant_id>/create', methods=["GET", "POST"])
def createMenuItem(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if getUserID(login_session['email']) is not restaurant.user_id:
        return redirect('/login')
    if request.method == "POST":
        newItem = MenuItem(name=request.form["name"],
                           description=request.form["description"],
                           price=request.form["price"],
                           course=request.form["course"],
                           restaurant_id=restaurant_id,
                           user_id=login_session['username'])
        session.add(newItem)
        session.commit()
        flash("New menu item created")
        return redirect(url_for("restaurantMenu",
                                restaurant_id=restaurant_id,
                                login_session=login_session))
    else:
        return render_template("newmenuitem.html",
                               restaurant_id=restaurant_id,
                               login_session=login_session)


@app.route('/restaurants/<int:restaurant_id>/edit/<int:item_id>',
           methods=["GET", "POST"])
def editMenuItem(restaurant_id, item_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if getUserID(login_session['email']) is not restaurant.user_id:
        return redirect('/login')
    editedItem = session.query(MenuItem).filter_by(id=item_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['price']:
            editedItem.price = request.form['price']
        if request.form['course']:
            editedItem.course = request.form['course']
        session.add(editedItem)
        session.commit()
        flash("Item was edited")
        return redirect(url_for('restaurantMenu',
                                restaurant_id=restaurant_id,
                                login_session=login_session))
    else:
        return render_template("editmenuitem.html",
                               restaurant_id=restaurant_id, item=editedItem,
                               login_session=login_session)


@app.route('/restaurants/<int:restaurant_id>/delete/<int:item_id>',
           methods=["GET", "POST"])
def deleteMenuItem(restaurant_id, item_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if getUserID(login_session['email']) is not restaurant.user_id:
        return redirect('/login')
    deletedItem = session.query(MenuItem).filter_by(id=item_id).one()
    if request.method == 'POST':
        session.delete(deletedItem)
        session.commit()
        flash("Item was deleted")
        return redirect(url_for('restaurantMenu',
                                restaurant_id=restaurant_id,
                                login_session=login_session))
    else:
        return render_template("deletemenuitem.html",
                               restaurant_id=restaurant_id, item=deletedItem,
                               login_session=login_session)


#Here's some code to create, edit and delete restaurants
@app.route('/restaurants/create', methods=["GET", "POST"])
def createRestaurant():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == "POST":
        newRestaurant = Restaurant(name=request.form["name"],
                                   user_id=getUserID(login_session['email']))
        session.add(newRestaurant)
        session.commit()
        flash("New restaurant created")
        return redirect(url_for('showRestaurants'))
    else:
        return render_template("newrestaurant.html",
                               login_session=login_session)


@app.route('/restaurants/edit/<int:restaurant_id>', methods=["GET", "POST"])
def editRestaurant(restaurant_id):
    editedRestaurant = session.query(Restaurant).filter_by(
                                    id=restaurant_id).one()
    if getUserID(login_session['email']) is not editedRestaurant.user_id:
        return redirect('/login')
    if request.method == 'POST':
        if request.form['name']:
            editedRestaurant.name = request.form['name']
        session.add(editedRestaurant)
        session.commit()
        flash("Restaurant was edited")
        return redirect(url_for('showRestaurants'))
    else:
        return render_template("editrestaurant.html",
                               restaurant=editedRestaurant,
                               login_session=login_session)


@app.route('/restaurants/delete/<int:restaurant_id>', methods=["GET", "POST"])
def deleteRestaurant(restaurant_id):
    deletedRestaurant = session.query(Restaurant).filter_by(
                                        id=restaurant_id).one()
    print getUserID(login_session['email'])
    print deletedRestaurant.user_id
    if getUserID(login_session['email']) is not deletedRestaurant.user_id:
        return redirect('/login')
    if request.method == 'POST':
        session.delete(deletedRestaurant)
        session.commit()
        flash("Restaurant was deleted")
        return redirect(url_for('showRestaurants'))
    else:
        return render_template("deleterestaurant.html",
                               restaurant=deletedRestaurant,
                               login_session=login_session)


#Here are the JSON files that I will create
@app.route('/restaurants/JSON')
def restaurantsJSON():
    restaurants = session.query(Restaurant).all()
    return jsonify(Restaurants=[i.serialize for i in restaurants])


@app.route('/restaurants/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(
        restaurant_id=restaurant_id).all()
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/restaurants/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def itemJSON(restaurant_id, menu_id):
    item = session.query(MenuItem).filter_by(id=menu_id).one()
    return jsonify(MenuItem=item.serialize)


def application(environ, start_response):
    status = '200 OK'
    output = 'Hello World!'

    response_headers = [('Content-type', 'text/plain'), ('Content-Length', str(len(output)))]
    start_response(status, response_headers)

    if environ['PATH'] == "/" or environ['PATH'] == "/restaurant" or environ['PATH'] == "/restaurants":
        return showRestaurants()
    if environ['PATH'] == '/login':
        return showLogin()
    if environ['PATH'] == '/gconnect':
        return gconnect()
    if environ['PATH'] == '/fbconnect':
        return fbconnect()
    if environ['PATH'] == '/disconnect':
        return disconnect()

    return [output]

if __name__ == '__main__':
    app.secret_key = "supersecretkey"
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
