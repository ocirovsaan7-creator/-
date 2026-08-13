import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                          login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

app = Flask(__name__)
app.config["SECRET_KEY"] = "buryatia-esports-secret-key-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'esports.db')}"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "admin_login"
login_manager.login_message = "Войдите, чтобы попасть в админку"

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def save_image(file, subfolder):
    if not file or file.filename == "" or not allowed_file(file.filename):
        return None
    filename = secure_filename(file.filename)
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    filename = f"{ts}_{filename}"
    folder = os.path.join(app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    file.save(path)
    return f"uploads/{subfolder}/{filename}"


# ---------------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------------

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    tag = db.Column(db.String(20))
    logo = db.Column(db.String(255))
    game = db.Column(db.String(80))
    city = db.Column(db.String(80), default="Улан-Удэ")
    description = db.Column(db.Text)
    contact = db.Column(db.String(120))
    approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    players = db.relationship("Player", backref="team", lazy=True)


class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), nullable=False)
    real_name = db.Column(db.String(120))
    photo = db.Column(db.String(255))
    game = db.Column(db.String(80))
    role = db.Column(db.String(80))
    rating = db.Column(db.Float, default=0.0)
    kd = db.Column(db.Float, default=0.0)
    maps_played = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    game = db.Column(db.String(80))
    description = db.Column(db.Text)
    prize_pool = db.Column(db.String(80))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="upcoming")  # upcoming/ongoing/finished
    cover = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    registrations = db.relationship("TournamentRegistration", backref="tournament", lazy=True)


class TournamentRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending/approved/rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship("Team")


class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(400))
    content = db.Column(db.Text)
    cover = db.Column(db.String(255))
    published_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


# ---------------------------------------------------------------------------
# PUBLIC ROUTES
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    news = News.query.order_by(News.published_at.desc()).limit(6).all()
    upcoming = Tournament.query.filter_by(status="upcoming").order_by(Tournament.start_date).limit(4).all()
    top_players = Player.query.order_by(Player.rating.desc()).limit(5).all()
    return render_template("index.html", news=news, upcoming=upcoming, top_players=top_players)


@app.route("/news")
def news_list():
    all_news = News.query.order_by(News.published_at.desc()).all()
    return render_template("news_list.html", news=all_news)


@app.route("/news/<int:news_id>")
def news_detail(news_id):
    item = News.query.get_or_404(news_id)
    return render_template("news_detail.html", item=item)


@app.route("/players")
def players_list():
    game = request.args.get("game", "")
    q = Player.query
    if game:
        q = q.filter_by(game=game)
    players = q.order_by(Player.rating.desc()).all()
    games = sorted({p.game for p in Player.query.all() if p.game})
    return render_template("players_list.html", players=players, games=games, current_game=game)


@app.route("/players/<int:player_id>")
def player_detail(player_id):
    player = Player.query.get_or_404(player_id)
    return render_template("player_detail.html", player=player)


@app.route("/teams")
def teams_list():
    teams = Team.query.filter_by(approved=True).order_by(Team.name).all()
    return render_template("teams_list.html", teams=teams)


@app.route("/teams/<int:team_id>")
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    return render_template("team_detail.html", team=team)


@app.route("/teams/register", methods=["GET", "POST"])
def team_register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Укажите название команды", "error")
            return redirect(url_for("team_register"))
        if Team.query.filter_by(name=name).first():
            flash("Команда с таким названием уже существует", "error")
            return redirect(url_for("team_register"))
        logo_path = save_image(request.files.get("logo"), "teams")
        team = Team(
            name=name,
            tag=request.form.get("tag", "").strip(),
            game=request.form.get("game", "").strip(),
            city=request.form.get("city", "Улан-Удэ").strip(),
            description=request.form.get("description", "").strip(),
            contact=request.form.get("contact", "").strip(),
            logo=logo_path,
            approved=False,
        )
        db.session.add(team)
        db.session.commit()
        flash("Заявка отправлена! После проверки модератором команда появится на сайте.", "success")
        return redirect(url_for("teams_list"))
    return render_template("team_register.html")


@app.route("/tournaments")
def tournaments_list():
    tournaments = Tournament.query.order_by(Tournament.start_date.desc()).all()
    return render_template("tournaments_list.html", tournaments=tournaments)


@app.route("/tournaments/<int:tournament_id>")
def tournament_detail(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    teams = Team.query.filter_by(approved=True).order_by(Team.name).all()
    return render_template("tournament_detail.html", tournament=tournament, teams=teams)


@app.route("/tournaments/<int:tournament_id>/register", methods=["POST"])
def tournament_register(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    team_id = request.form.get("team_id")
    if not team_id:
        flash("Выберите команду", "error")
        return redirect(url_for("tournament_detail", tournament_id=tournament_id))
    existing = TournamentRegistration.query.filter_by(
        tournament_id=tournament_id, team_id=team_id
    ).first()
    if existing:
        flash("Эта команда уже зарегистрирована на турнир", "error")
        return redirect(url_for("tournament_detail", tournament_id=tournament_id))
    reg = TournamentRegistration(tournament_id=tournament_id, team_id=team_id)
    db.session.add(reg)
    db.session.commit()
    flash("Заявка на турнир отправлена и ожидает подтверждения!", "success")
    return redirect(url_for("tournament_detail", tournament_id=tournament_id))


# ---------------------------------------------------------------------------
# ADMIN AUTH
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin)
            return redirect(url_for("admin_dashboard"))
        flash("Неверный логин или пароль", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------------------------

@app.route("/admin")
@login_required
def admin_dashboard():
    stats = {
        "players": Player.query.count(),
        "teams": Team.query.count(),
        "pending_teams": Team.query.filter_by(approved=False).count(),
        "tournaments": Tournament.query.count(),
        "news": News.query.count(),
        "pending_regs": TournamentRegistration.query.filter_by(status="pending").count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


# --- Players CRUD ---

@app.route("/admin/players")
@login_required
def admin_players():
    players = Player.query.order_by(Player.id.desc()).all()
    teams = Team.query.all()
    return render_template("admin/players.html", players=players, teams=teams)


@app.route("/admin/players/add", methods=["POST"])
@login_required
def admin_players_add():
    photo_path = save_image(request.files.get("photo"), "players")
    player = Player(
        nickname=request.form.get("nickname"),
        real_name=request.form.get("real_name"),
        game=request.form.get("game"),
        role=request.form.get("role"),
        rating=float(request.form.get("rating") or 0),
        kd=float(request.form.get("kd") or 0),
        maps_played=int(request.form.get("maps_played") or 0),
        wins=int(request.form.get("wins") or 0),
        team_id=request.form.get("team_id") or None,
        photo=photo_path,
    )
    db.session.add(player)
    db.session.commit()
    flash("Игрок добавлен", "success")
    return redirect(url_for("admin_players"))


@app.route("/admin/players/<int:player_id>/edit", methods=["POST"])
@login_required
def admin_players_edit(player_id):
    player = Player.query.get_or_404(player_id)
    player.nickname = request.form.get("nickname")
    player.real_name = request.form.get("real_name")
    player.game = request.form.get("game")
    player.role = request.form.get("role")
    player.rating = float(request.form.get("rating") or 0)
    player.kd = float(request.form.get("kd") or 0)
    player.maps_played = int(request.form.get("maps_played") or 0)
    player.wins = int(request.form.get("wins") or 0)
    player.team_id = request.form.get("team_id") or None
    new_photo = save_image(request.files.get("photo"), "players")
    if new_photo:
        player.photo = new_photo
    db.session.commit()
    flash("Данные игрока обновлены", "success")
    return redirect(url_for("admin_players"))


@app.route("/admin/players/<int:player_id>/delete", methods=["POST"])
@login_required
def admin_players_delete(player_id):
    player = Player.query.get_or_404(player_id)
    db.session.delete(player)
    db.session.commit()
    flash("Игрок удалён", "success")
    return redirect(url_for("admin_players"))


# --- Teams CRUD ---

@app.route("/admin/teams")
@login_required
def admin_teams():
    teams = Team.query.order_by(Team.id.desc()).all()
    return render_template("admin/teams.html", teams=teams)


@app.route("/admin/teams/add", methods=["POST"])
@login_required
def admin_teams_add():
    logo_path = save_image(request.files.get("logo"), "teams")
    team = Team(
        name=request.form.get("name"),
        tag=request.form.get("tag"),
        game=request.form.get("game"),
        city=request.form.get("city") or "Улан-Удэ",
        description=request.form.get("description"),
        contact=request.form.get("contact"),
        logo=logo_path,
        approved=True,
    )
    db.session.add(team)
    db.session.commit()
    flash("Команда добавлена", "success")
    return redirect(url_for("admin_teams"))


@app.route("/admin/teams/<int:team_id>/approve", methods=["POST"])
@login_required
def admin_teams_approve(team_id):
    team = Team.query.get_or_404(team_id)
    team.approved = True
    db.session.commit()
    flash(f"Команда «{team.name}» одобрена", "success")
    return redirect(url_for("admin_teams"))


@app.route("/admin/teams/<int:team_id>/edit", methods=["POST"])
@login_required
def admin_teams_edit(team_id):
    team = Team.query.get_or_404(team_id)
    team.name = request.form.get("name")
    team.tag = request.form.get("tag")
    team.game = request.form.get("game")
    team.city = request.form.get("city")
    team.description = request.form.get("description")
    team.contact = request.form.get("contact")
    new_logo = save_image(request.files.get("logo"), "teams")
    if new_logo:
        team.logo = new_logo
    db.session.commit()
    flash("Команда обновлена", "success")
    return redirect(url_for("admin_teams"))


@app.route("/admin/teams/<int:team_id>/delete", methods=["POST"])
@login_required
def admin_teams_delete(team_id):
    team = Team.query.get_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    flash("Команда удалена", "success")
    return redirect(url_for("admin_teams"))


# --- Tournaments CRUD ---

@app.route("/admin/tournaments")
@login_required
def admin_tournaments():
    tournaments = Tournament.query.order_by(Tournament.id.desc()).all()
    return render_template("admin/tournaments.html", tournaments=tournaments)


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@app.route("/admin/tournaments/add", methods=["POST"])
@login_required
def admin_tournaments_add():
    cover_path = save_image(request.files.get("cover"), "news")
    tournament = Tournament(
        title=request.form.get("title"),
        game=request.form.get("game"),
        description=request.form.get("description"),
        prize_pool=request.form.get("prize_pool"),
        start_date=parse_date(request.form.get("start_date")),
        end_date=parse_date(request.form.get("end_date")),
        status=request.form.get("status", "upcoming"),
        cover=cover_path,
    )
    db.session.add(tournament)
    db.session.commit()
    flash("Турнир создан", "success")
    return redirect(url_for("admin_tournaments"))


@app.route("/admin/tournaments/<int:tournament_id>/edit", methods=["POST"])
@login_required
def admin_tournaments_edit(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    t.title = request.form.get("title")
    t.game = request.form.get("game")
    t.description = request.form.get("description")
    t.prize_pool = request.form.get("prize_pool")
    t.start_date = parse_date(request.form.get("start_date"))
    t.end_date = parse_date(request.form.get("end_date"))
    t.status = request.form.get("status", "upcoming")
    new_cover = save_image(request.files.get("cover"), "news")
    if new_cover:
        t.cover = new_cover
    db.session.commit()
    flash("Турнир обновлён", "success")
    return redirect(url_for("admin_tournaments"))


@app.route("/admin/tournaments/<int:tournament_id>/delete", methods=["POST"])
@login_required
def admin_tournaments_delete(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    db.session.delete(t)
    db.session.commit()
    flash("Турнир удалён", "success")
    return redirect(url_for("admin_tournaments"))


@app.route("/admin/registrations/<int:reg_id>/<action>", methods=["POST"])
@login_required
def admin_registration_action(reg_id, action):
    reg = TournamentRegistration.query.get_or_404(reg_id)
    if action == "approve":
        reg.status = "approved"
    elif action == "reject":
        reg.status = "rejected"
    db.session.commit()
    return redirect(url_for("admin_tournaments"))


# --- News CRUD ---

@app.route("/admin/news")
@login_required
def admin_news():
    news = News.query.order_by(News.id.desc()).all()
    return render_template("admin/news.html", news=news)


@app.route("/admin/news/add", methods=["POST"])
@login_required
def admin_news_add():
    cover_path = save_image(request.files.get("cover"), "news")
    item = News(
        title=request.form.get("title"),
        summary=request.form.get("summary"),
        content=request.form.get("content"),
        cover=cover_path,
    )
    db.session.add(item)
    db.session.commit()
    flash("Новость опубликована", "success")
    return redirect(url_for("admin_news"))


@app.route("/admin/news/<int:news_id>/edit", methods=["POST"])
@login_required
def admin_news_edit(news_id):
    item = News.query.get_or_404(news_id)
    item.title = request.form.get("title")
    item.summary = request.form.get("summary")
    item.content = request.form.get("content")
    new_cover = save_image(request.files.get("cover"), "news")
    if new_cover:
        item.cover = new_cover
    db.session.commit()
    flash("Новость обновлена", "success")
    return redirect(url_for("admin_news"))


@app.route("/admin/news/<int:news_id>/delete", methods=["POST"])
@login_required
def admin_news_delete(news_id):
    item = News.query.get_or_404(news_id)
    db.session.delete(item)
    db.session.commit()
    flash("Новость удалена", "success")
    return redirect(url_for("admin_news"))


# ---------------------------------------------------------------------------
# CLI: init db + create admin
# ---------------------------------------------------------------------------

@app.cli.command("init-db")
def init_db():
    db.create_all()
    if not Admin.query.filter_by(username="admin").first():
        admin = Admin(username="admin")
        admin.set_password("buryatia2026")
        db.session.add(admin)
        db.session.commit()
        print("Создан администратор: admin / buryatia2026")
    print("База данных готова.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not Admin.query.filter_by(username="admin").first():
            admin = Admin(username="admin")
            admin.set_password("buryatia2026")
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True, host="0.0.0.0", port=5000)
