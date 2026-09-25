from flask import Flask, render_template, request, redirect, url_for, Response, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import io
import datetime

app = Flask(__name__)

# ============================================================
# CONFIGURACIÓN
# ============================================================
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///juridico.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ============================================================
# CATÁLOGO DE ÁREAS
# Los responsables se dejan vacíos por ahora.
# ============================================================
AREAS = [
    "Dirección General",
    "Administración",
    "Jurídico",
    "Dirección de la Familia",
    "Asistencia Social",
    "PMA",
    "COMUDIS",
]

RESPONSABLES = {
    "Dirección General": "",
    "Administración": "",
    "Jurídico": "",
    "Dirección de la Familia": "",
    "Asistencia Social": "",
    "PMA": "",
    "COMUDIS": "",
}

# ============================================================
# MODELO DE OFICIOS / DEMANDAS
# ============================================================
class Oficio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    folio = db.Column(db.String(30), unique=True, nullable=False)

    fecha_recepcion = db.Column(
        db.DateTime, default=datetime.datetime.now, nullable=False
    )

    fecha_entrega = db.Column(db.DateTime, nullable=False)
    fecha_limite = db.Column(db.DateTime, nullable=False)

    tipo_documento = db.Column(db.String(100), nullable=False)
    autoridad_remitente = db.Column(db.String(200))
    asunto = db.Column(db.Text, nullable=False)

    area = db.Column(db.String(100), nullable=False)
    responsable = db.Column(db.String(200), default="")

    estatus = db.Column(db.String(30), default="PENDIENTE", nullable=False)

    observaciones = db.Column(db.Text)
    documento = db.Column(db.String(300))

    fecha_contestacion = db.Column(db.DateTime)

    def semaforo(self):
        """
        Calcula el estado visual del plazo.
        La contestación/conclusión prevalece sobre el plazo.
        """
        if self.estatus in ["CONTESTADO", "CONCLUIDO"]:
            return "🔵"

        ahora = datetime.datetime.now()

        if ahora > self.fecha_limite:
            return "🔴"

        diferencia = self.fecha_limite - ahora

        if diferencia.total_seconds() <= 24 * 60 * 60:
            return "🟡"

        return "🟢"


# ============================================================
# CREACIÓN DE BASE DE DATOS
# ============================================================
with app.app_context():
    db.create_all()


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================
def siguiente_folio():
    """
    Genera folios consecutivos:
    JUR-2026-000001
    """
    anio = datetime.datetime.now().year

    ultimo = (
        Oficio.query
        .filter(Oficio.folio.like(f"JUR-{anio}-%"))
        .order_by(Oficio.id.desc())
        .first()
    )

    if ultimo:
        try:
            numero = int(ultimo.folio.split("-")[-1]) + 1
        except (ValueError, IndexError):
            numero = Oficio.query.count() + 1
    else:
        numero = 1

    return f"JUR-{anio}-{numero:06d}"


def calcular_fecha_limite(fecha_entrega):
    """
    Primera versión solicitada:
    3 días naturales después de la fecha de entrega.
    """
    return fecha_entrega + datetime.timedelta(days=3)


# ============================================================
# INICIO / RECEPCIÓN
# ============================================================
@app.route("/", methods=["GET", "POST"])
def index():

    confirmacion = None
    error = None

    if request.method == "POST":

        try:
            tipo_documento = request.form.get("tipo_documento", "").strip()
            autoridad = request.form.get("autoridad_remitente", "").strip()
            asunto = request.form.get("asunto", "").strip()
            area = request.form.get("area", "").strip()
            observaciones = request.form.get("observaciones", "").strip()

            if not tipo_documento:
                raise ValueError("Debes indicar el tipo de documento.")

            if not asunto:
                raise ValueError("Debes indicar el asunto.")

            if area not in AREAS:
                raise ValueError("Debes seleccionar un área válida.")

            fecha_entrega = datetime.datetime.now()
            fecha_limite = calcular_fecha_limite(fecha_entrega)

            responsable = RESPONSABLES.get(area, "")

            nuevo = Oficio(
                folio=siguiente_folio(),
                fecha_recepcion=fecha_entrega,
                fecha_entrega=fecha_entrega,
                fecha_limite=fecha_limite,
                tipo_documento=tipo_documento,
                autoridad_remitente=autoridad,
                asunto=asunto,
                area=area,
                responsable=responsable,
                estatus="PENDIENTE",
                observaciones=observaciones,
            )

            db.session.add(nuevo)
            db.session.commit()

            confirmacion = nuevo.folio

        except Exception as e:
            db.session.rollback()
            error = str(e)

    return render_template(
        "index.html",
        folio=confirmacion,
        error=error,
        areas=AREAS,
        responsables=RESPONSABLES,
    )


# ============================================================
# PANEL DE ADMINISTRACIÓN
# ============================================================
@app.route("/admin")
def admin_panel():

    auth = request.authorization

    if not auth or not (
        auth.username == "admin"
        and auth.password == "Santander2026"
    ):
        return Response(
            "Acceso denegado.",
            401,
            {"WWW-Authenticate": 'Basic realm="Login"'},
        )

    oficios = (
        Oficio.query
        .order_by(Oficio.fecha_limite.asc())
        .all()
    )

    return render_template(
        "admin.html",
        oficios=oficios,
        areas=AREAS,
    )


# ============================================================
# VER DETALLE DE UN OFICIO
# ============================================================
@app.route("/oficio/<int:oficio_id>")
def detalle_oficio(oficio_id):

    auth = request.authorization

    if not auth or not (
        auth.username == "admin"
        and auth.password == "Santander2026"
    ):
        return Response(
            "Acceso denegado.",
            401,
            {"WWW-Authenticate": 'Basic realm="Login"'},
        )

    oficio = Oficio.query.get_or_404(oficio_id)

    return render_template(
        "detalle.html",
        oficio=oficio,
    )


# ============================================================
# ACTUALIZAR ESTATUS
# ============================================================
@app.route("/oficio/<int:oficio_id>/estatus", methods=["POST"])
def actualizar_estatus(oficio_id):

    auth = request.authorization

    if not auth or not (
        auth.username == "admin"
        and auth.password == "Santander2026"
    ):
        return Response(
            "Acceso denegado.",
            401,
            {"WWW-Authenticate": 'Basic realm="Login"'},
        )

    oficio = Oficio.query.get_or_404(oficio_id)

    nuevo_estatus = request.form.get("estatus", "").strip()

    estatus_validos = [
        "PENDIENTE",
        "EN REVISION",
        "CONTESTADO",
        "CONCLUIDO",
    ]

    if nuevo_estatus in estatus_validos:
        oficio.estatus = nuevo_estatus

        if nuevo_estatus == "CONTESTADO":
            oficio.fecha_contestacion = datetime.datetime.now()

        db.session.commit()

    return redirect(url_for("admin_panel"))


# ============================================================
# EXPORTAR EXCEL
# ============================================================
@app.route("/descargar_excel")
def descargar_excel():

    auth = request.authorization

    if not auth or not (
        auth.username == "admin"
        and auth.password == "Santander2026"
    ):
        return Response(
            "Acceso denegado.",
            401,
            {"WWW-Authenticate": 'Basic realm="Login"'},
        )

    oficios = Oficio.query.order_by(Oficio.fecha_recepcion.desc()).all()

    datos = []

    for o in oficios:
        datos.append({
            "Folio": o.folio,
            "Recepción": o.fecha_recepcion.strftime("%Y-%m-%d %H:%M"),
            "Entrega": o.fecha_entrega.strftime("%Y-%m-%d %H:%M"),
            "Fecha límite": o.fecha_limite.strftime("%Y-%m-%d %H:%M"),
            "Tipo": o.tipo_documento,
            "Autoridad remitente": o.autoridad_remitente,
            "Asunto": o.asunto,
            "Área": o.area,
            "Responsable": o.responsable or "PENDIENTE",
            "Estatus": o.estatus,
            "Fecha contestación": (
                o.fecha_contestacion.strftime("%Y-%m-%d %H:%M")
                if o.fecha_contestacion
                else ""
            ),
            "Observaciones": o.observaciones or "",
        })

    df = pd.DataFrame(datos)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Oficios")

    output.seek(0)

    return send_file(
        output,
        download_name="reporte_juridico.xlsx",
        as_attachment=True,
    )


# ============================================================
# EJECUCIÓN
# ============================================================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False
    )
