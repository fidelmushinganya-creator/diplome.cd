from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3
import os
import secrets
import uuid

app = Flask(__name__)

app.secret_key = "CHANGE-MOI-PAR-UNE-CLE-SECRETE"

DATABASE = "diplome.db"
UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS attestations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            numero TEXT UNIQUE NOT NULL,
            nom TEXT NOT NULL,
            formation TEXT NOT NULL,
            institution TEXT NOT NULL,
            date_reussite TEXT NOT NULL,
            description TEXT,
            fichier TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def admin_required():
    return session.get("admin") is True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:

            session["admin"] = True

            return redirect(url_for("admin"))

        flash("Identifiants incorrects.")

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("index"))


@app.route("/admin")
def admin():

    if not admin_required():
        return redirect(url_for("login"))

    connection = get_db()

    attestations = connection.execute(
        "SELECT * FROM attestations ORDER BY id DESC"
    ).fetchall()

    connection.close()

    return render_template(
        "admin.html",
        attestations=attestations
    )


@app.route("/admin/publier", methods=["GET", "POST"])
def publier():

    if not admin_required():
        return redirect(url_for("login"))

    if request.method == "POST":

        nom = request.form.get("nom", "").strip()
        formation = request.form.get("formation", "").strip()
        institution = request.form.get("institution", "").strip()
        date_reussite = request.form.get("date_reussite", "").strip()
        numero = request.form.get("numero", "").strip()
        description = request.form.get("description", "").strip()

        fichier = request.files.get("fichier")

        if not all([
            nom,
            formation,
            institution,
            date_reussite,
            numero
        ]):
            flash("Veuillez remplir tous les champs obligatoires.")
            return render_template("publish.html")

        if not fichier or fichier.filename == "":
            flash("Veuillez sélectionner l'attestation.")
            return render_template("publish.html")

        if not allowed_file(fichier.filename):
            flash("Format non autorisé. Utilisez JPG, PNG, WEBP ou PDF.")
            return render_template("publish.html")

        connection = get_db()

        existing = connection.execute(
            "SELECT id FROM attestations WHERE numero = ?",
            (numero,)
        ).fetchone()

        if existing:
            connection.close()
            flash("Ce numéro d'attestation existe déjà.")
            return render_template("publish.html")

        extension = fichier.filename.rsplit(".", 1)[1].lower()

        filename = secure_filename(
            f"{uuid.uuid4().hex}.{extension}"
        )

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        fichier.save(filepath)

        token = secrets.token_urlsafe(10)

        connection.execute("""
            INSERT INTO attestations
            (
                token,
                numero,
                nom,
                formation,
                institution,
                date_reussite,
                description,
                fichier
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            token,
            numero,
            nom,
            formation,
            institution,
            date_reussite,
            description,
            filename
        ))

        connection.commit()
        connection.close()

        flash("Attestation publiée avec succès.")

        return redirect(url_for(
            "admin"
        ))

    return render_template("publish.html")


@app.route("/attestation/<token>")
def attestation(token):

    connection = get_db()

    attestation_data = connection.execute(
        "SELECT * FROM attestations WHERE token = ?",
        (token,)
    ).fetchone()

    connection.close()

    if not attestation_data:
        return render_template(
            "attestation.html",
            attestation=None
        ), 404

    return render_template(
        "attestation.html",
        attestation=attestation_data
    )


@app.route("/fichier/<filename>")
def fichier(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


@app.route("/admin/supprimer/<int:attestation_id>", methods=["POST"])
def supprimer(attestation_id):

    if not admin_required():
        return redirect(url_for("login"))

    connection = get_db()

    attestation_data = connection.execute(
        "SELECT * FROM attestations WHERE id = ?",
        (attestation_id,)
    ).fetchone()

    if attestation_data:

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            attestation_data["fichier"]
        )

        if os.path.exists(filepath):
            os.remove(filepath)

        connection.execute(
            "DELETE FROM attestations WHERE id = ?",
            (attestation_id,)
        )

        connection.commit()

    connection.close()

    return redirect(url_for("admin"))


@app.context_processor
def inject_globals():

    return {
        "site_name": "DIPLÔME.CD"
    }

init_database()

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8081,
        debug=True
    )
