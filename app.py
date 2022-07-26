import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
os.environ["API_KEY"] = "pk_a36d33e5855f44209169f2f3dc2f2c24"
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Query database for username
    user_id = session["user_id"]
    stocks = db.execute("SELECT symbol, sum(shares) AS shares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]

    sum = 0

    for stock in stocks:
        quotes = lookup(stock["symbol"])
        stock["price"] = quotes["price"]
        stock["name"] = quotes["name"]
        stock["sum"] = stock["shares"] * stock["price"]
        sum += stock["sum"]

    total = sum + user["cash"]

    return render_template("index.html", stocks=stocks, cash=user["cash"], total=total, usd=usd)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Ensure symbol is valid and get quotes info
        quotes = lookup(request.form.get("symbol"))
        if not quotes:
            return apology("invalid symbol", 400)

        try:
            shares = int(request.form.get("shares"))
        except (KeyError, TypeError, ValueError):
            return apology("shares must be a positive number", 400)

        if not (shares > 0):
            return apology("shares must be a positive number", 400)

        user_id = session["user_id"]
        user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]

        user_future_cash = float(user["cash"]) - (quotes["price"] * int(shares))

        if user_future_cash < 0:
            return apology("You can't afford the number of shares at the current price.", 400)

        # Save in database current transactions
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (%s, %s, %s, %s)", user_id, quotes["symbol"], shares, quotes["price"])
        # Update in database new user cash value
        db.execute('UPDATE users SET cash = (?) WHERE id = (?)', user_future_cash, user_id)

        flash("Bought!")
        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Query database for username
    user_id = session["user_id"]
    stocks = db.execute("SELECT symbol, shares, price, time FROM transactions WHERE user_id = ?", user_id)
    return render_template("history.html", stocks=stocks, usd=usd)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # Ensure username was submitted
        quotes = lookup(request.form.get("symbol"))
        if not quotes:
            return apology("missing symbol", 400)

        return render_template("quoted.html", quotes=quotes, usd=usd)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("missing username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("missing password", 400)

        elif not request.form.get("confirmation"):
            return apology("passwords don't mutch", 400)

        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("passwords don't mutch", 400)

        username = request.form.get("username")
        password = request.form.get("password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username is correct
        if len(rows) != 0:
            return apology("username is already taken", 400)

        db.execute("INSERT INTO users (username, hash) VALUES (%s, %s)", username, generate_password_hash(password))

        flash("Thanks for registering!")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
         # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    if request.method == "POST":
        # Ensure symbol is valid and get quotes info
        symbol = request.form.get("symbol")
        if symbol == None:
            return apology("invalid symbol", 400)
        quotes = lookup(symbol)
        if not quotes:
            return apology("invalid symbol", 400)

        shares_to_sell = int(request.form.get("shares"))
        if not (shares_to_sell > 0):
            return apology("shares must be a positive number", 400)

        user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
        stocks = db.execute("SELECT symbol, sum(shares) AS shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, quotes["symbol"])
        shares_available = 0
        if len(stocks) > 0:
            shares_available = stocks[0]["shares"]
        if shares_available < shares_to_sell:
            return apology("not enought shares", 400)

        user_future_cash = float(user["cash"]) + (quotes["price"] * int(shares_to_sell))

        if user_future_cash < 0:
            return apology("You can't afford the number of shares at the current price.", 400)

        # Save in database current transactions
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (%s, %s, %s, %s)", user_id, quotes["symbol"], -shares_to_sell, quotes["price"])
        # Update in database new user cash value
        db.execute('UPDATE users SET cash = (?) WHERE id = (?)', user_future_cash, user_id)

        flash("Sold!")
        # Redirect user to home page
        return redirect("/")

    else:
        symbols = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", symbols=symbols)

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Cash deposit"""
    if request.method == "POST":
        user_id = session["user_id"]
        cash_to_deposit = int(request.form.get("cash"))
        if not (cash_to_deposit > 0):
            return apology("cash must be a positive number", 403)

        user_cash = db.execute("SELECT cash FROM users WHERE id = (?)", user_id)[0]["cash"]
        db.execute('UPDATE users SET cash = (?) WHERE id = (?)', cash_to_deposit + user_cash, user_id)
        flash("Deposited!")
        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("deposit.html")
