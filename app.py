
from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")
DB=os.environ.get("DATABASE_PATH", "soframgel.db")

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'customer');
    CREATE TABLE IF NOT EXISTS restaurants(id INTEGER PRIMARY KEY, name TEXT, owner_id INTEGER);
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, restaurant_id INTEGER, name TEXT, price REAL);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, user_id INTEGER, total REAL, status TEXT DEFAULT 'Hazırlanıyor');
    """)
    if not c.execute("SELECT 1 FROM users WHERE email='restoran@soframgel.local'").fetchone():
        c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",("Restoran Sahibi","restoran@soframgel.local",generate_password_hash("demo123"),"restaurant"))
        oid=c.execute("SELECT id FROM users WHERE email='restoran@soframgel.local'").fetchone()[0]
        c.execute("INSERT INTO restaurants(name,owner_id) VALUES(?,?)",("Ciğerci Usta",oid))
        rid=c.execute("SELECT id FROM restaurants WHERE owner_id=?",(oid,)).fetchone()[0]
        c.executemany("INSERT INTO products(restaurant_id,name,price) VALUES(?,?,?)",[(rid,"Ciğer Şiş",120),(rid,"Adana Dürüm",180),(rid,"Karışık Izgara",280)])
    c.commit(); c.close()
init()

@app.route("/")
def home():
    c=db(); products=c.execute("SELECT products.*,restaurants.name restaurant FROM products JOIN restaurants ON restaurants.id=products.restaurant_id").fetchall()
    return render_template("index.html", products=products)

@app.route("/register",methods=["POST"])
def register():
    try:
        c=db(); c.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",(request.form["name"],request.form["email"],generate_password_hash(request.form["password"])))
        c.commit()
    except sqlite3.IntegrityError: return "Bu e-posta kayıtlı",400
    return redirect("/")

@app.route("/login",methods=["POST"])
def login():
    c=db(); u=c.execute("SELECT * FROM users WHERE email=?",(request.form["email"],)).fetchone()
    if not u or not check_password_hash(u["password"],request.form["password"]): return "Hatalı giriş",401
    session["uid"],session["name"],session["role"]=u["id"],u["name"],u["role"]
    return redirect("/panel" if u["role"]=="restaurant" else "/")

@app.route("/logout")
def logout(): session.clear(); return redirect("/")

@app.route("/panel")
def panel():
    if session.get("role")!="restaurant": return redirect("/")
    c=db(); r=c.execute("SELECT * FROM restaurants WHERE owner_id=?",(session["uid"],)).fetchone()
    products=c.execute("SELECT * FROM products WHERE restaurant_id=?",(r["id"],)).fetchall()
    return render_template("panel.html",r=r,products=products)

@app.route("/product",methods=["POST"])
def product():
    if session.get("role")!="restaurant": return "Yetkisiz",403
    c=db(); r=c.execute("SELECT id FROM restaurants WHERE owner_id=?",(session["uid"],)).fetchone()
    c.execute("INSERT INTO products(restaurant_id,name,price) VALUES(?,?,?)",(r["id"],request.form["name"],float(request.form["price"])))
    c.commit(); return redirect("/panel")

@app.route("/checkout",methods=["POST"])
def checkout():
    if not session.get("uid"): return jsonify(ok=False,message="Önce giriş yap"),401
    data=request.get_json(); total=float(data.get("total",0))
    if total<=0:return jsonify(ok=False,message="Sepet boş"),400
    # Gerçek ödeme sağlayıcısı burada sunucu tarafında doğrulanmalıdır.
    c=db(); c.execute("INSERT INTO orders(user_id,total,status) VALUES(?,?,?)",(session["uid"],total,"Ödeme bekliyor")); c.commit()
    return jsonify(ok=True,message="Sipariş oluşturuldu. Canlı ödeme için sağlayıcı anahtarı bağlanmalı.")

if __name__=="__main__": app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
