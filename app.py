import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import date, datetime, timedelta
from pathlib import Path
import mimetypes
import uuid


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

st.set_page_config(
    page_title="Expedientes Jurídicos",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==========================================================
# ESTILOS
# ==========================================================

st.markdown("""
<style>

.stApp {
    background-color: #eef1f5;
}

/* BARRA LATERAL */
[data-testid="stSidebar"] {
    background-color: #0b1f3a;
}

[data-testid="stSidebar"] * {
    color: white !important;
}

/* TÍTULOS */
h1 {
    color: #0b1f3a !important;
    font-weight: 700 !important;
}

h2, h3 {
    color: #163a63 !important;
}

/* MÉTRICAS */
[data-testid="stMetric"] {
    background-color: white;
    padding: 18px;
    border-radius: 12px;
    border-top: 4px solid #c9a227;
    box-shadow: 0px 3px 10px rgba(0,0,0,0.08);
}

/* BOTONES */
.stButton > button {
    background-color: #0b1f3a;
    color: white;
    border-radius: 8px;
    border: none;
    font-weight: 600;
}

.stButton > button:hover {
    background-color: #163a63;
    color: white;
}

/* INPUTS */
.stTextInput input,
.stTextArea textarea {
    border-radius: 7px;
}

/* EXPANDERS */
[data-testid="stExpander"] {
    background-color: white;
    border-radius: 10px;
}

/* SEPARADORES */
hr {
    border-color: #d5dbe3;
}

</style>
""", unsafe_allow_html=True)


# ==========================================================
# FIREBASE
# ==========================================================

@st.cache_resource
def inicializar_firebase():

    if not firebase_admin._apps:

        firebase_config = dict(st.secrets["firebase"])

        cred = credentials.Certificate(firebase_config)

        firebase_admin.initialize_app(cred)

    return firestore.client()



# ==========================================================
# CONFIGURACIÓN DE COLECCIONES
# ==========================================================

COLECCION_EXPEDIENTES = "expedientes_juridicos"


# ==========================================================
# DOCUMENTOS / DIGITALIZACIÓN
# ==========================================================
EXTENSIONES_PERMITIDAS = ["pdf", "jpg", "jpeg", "png", "tif", "tiff"]


def obtener_documentos(expediente_id):
    docs = (db.collection(COLECCION_EXPEDIENTES).document(expediente_id)
            .collection("documentos")
            .order_by("fecha_registro", direction=firestore.Query.DESCENDING)
            .stream())
    resultado = []
    for doc in docs:
        datos = doc.to_dict()
        datos["id"] = doc.id
        resultado.append(datos)
    return resultado


def guardar_documento(expediente_id, archivo, categoria):
    nombre_original = Path(archivo.name).name
    extension = Path(nombre_original).suffix.lower().replace(".", "")
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ValueError("Tipo no permitido. Usa PDF, JPG, JPEG, PNG o TIFF.")

    nombre_storage = f"{uuid.uuid4().hex}_{nombre_original}"
    ruta = f"expedientes_juridicos/{expediente_id}/{nombre_storage}"
    contenido = archivo.getvalue()
    content_type = archivo.type or mimetypes.guess_type(nombre_original)[0] or "application/octet-stream"

    blob = bucket.blob(ruta)
    blob.upload_from_string(contenido, content_type=content_type)

    ref = (db.collection(COLECCION_EXPEDIENTES).document(expediente_id)
           .collection("documentos").document())
    ref.set({
        "nombre": nombre_original,
        "categoria": categoria,
        "tipo": content_type,
        "tamano": len(contenido),
        "storage_path": ruta,
        "fecha_registro": datetime.now()
    })

    total = len(obtener_documentos(expediente_id))
    db.collection(COLECCION_EXPEDIENTES).document(expediente_id).update({
        "documentos": total,
        "ultima_actualizacion": datetime.now()
    })


def url_documento(storage_path):
    blob = bucket.blob(storage_path)
    return blob.generate_signed_url(version="v4", expiration=timedelta(hours=24), method="GET")


def eliminar_documento(expediente_id, documento_id, storage_path):
    blob = bucket.blob(storage_path)
    if blob.exists():
        blob.delete()
    (db.collection(COLECCION_EXPEDIENTES).document(expediente_id)
     .collection("documentos").document(documento_id).delete())
    total = len(obtener_documentos(expediente_id))
    db.collection(COLECCION_EXPEDIENTES).document(expediente_id).update({
        "documentos": total,
        "ultima_actualizacion": datetime.now()
    })


def modulo_documentos(expediente_id):
    st.subheader("📂 Digitalización del expediente")
    st.caption("Escanea el documento y guárdalo como PDF/JPG/PNG; después súbelo aquí. Quedará asociado automáticamente al expediente.")

    categoria = st.selectbox("Tipo de documento", [
        "Demanda / escrito", "Oficio", "Contrato", "Convenio", "Resolución",
        "Notificación", "Identificación", "Comprobante", "Evidencia",
        "Acuerdo", "Dictamen", "Anexo", "Otro"
    ], key=f"cat_{expediente_id}")

    archivo = st.file_uploader(
        "📤 Seleccionar documento escaneado",
        type=EXTENSIONES_PERMITIDAS,
        key=f"upload_{expediente_id}"
    )

    if archivo:
        st.info(f"📄 {archivo.name} — {archivo.size / 1024 / 1024:.2f} MB")
        if st.button("☁️ GUARDAR EN EL EXPEDIENTE", type="primary", key=f"save_doc_{expediente_id}"):
            try:
                with st.spinner("Subiendo documento a Firebase Storage..."):
                    guardar_documento(expediente_id, archivo, categoria)
                st.success("✅ Documento guardado correctamente.")
                st.rerun()
            except Exception as e:
                st.error("No fue posible guardar el documento.")
                st.exception(e)

    st.divider()
    documentos = obtener_documentos(expediente_id)
    if not documentos:
        st.info("📭 Este expediente todavía no tiene documentos digitalizados.")
        return

    st.write(f"**Documentos digitalizados: {len(documentos)}**")
    for doc in documentos:
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 2, 1])
            with c1:
                st.write(f"📄 **{doc.get('nombre', 'Documento')}**")
                st.caption(f"Categoría: {doc.get('categoria', 'Sin categoría')}")
            with c2:
                try:
                    st.link_button("👁️ Abrir documento", url_documento(doc["storage_path"]))
                except Exception:
                    st.warning("No se pudo generar el enlace.")
            with c3:
                if st.button("🗑️", key=f"del_{expediente_id}_{doc['id']}"):
                    try:
                        eliminar_documento(expediente_id, doc["id"], doc["storage_path"])
                        st.success("Documento eliminado.")
                        st.rerun()
                    except Exception as e:
                        st.error("No fue posible eliminar el documento.")
                        st.exception(e)


# ==========================================================
# OBTENER EXPEDIENTES
# ==========================================================

def obtener_expedientes():

    documentos = (
        db.collection(COLECCION_EXPEDIENTES)
        .order_by("numero_control", direction=firestore.Query.DESCENDING)
        .stream()
    )

    expedientes = []

    for documento in documentos:

        datos = documento.to_dict()

        datos["id"] = documento.id

        expedientes.append(datos)

    return expedientes


# ==========================================================
# OBTENER SIGUIENTE NÚMERO
# ==========================================================

def obtener_siguiente_numero():

    referencia = db.collection("configuracion").document("folios")

    documento = referencia.get()

    if documento.exists:

        datos = documento.to_dict()

        ultimo = datos.get("ultimo", 0)

    else:

        ultimo = 0

    siguiente = ultimo + 1

    referencia.set({
        "ultimo": siguiente,
        "actualizado": datetime.now()
    })

    return siguiente


# ==========================================================
# CREAR FOLIO
# ==========================================================

def crear_folio(numero):

    return f"JUR-{date.today().year}-{numero:04d}"


# ==========================================================
# GUARDAR EXPEDIENTE
# ==========================================================

def guardar_expediente(
    numero_control,
    numero_expediente,
    fecha,
    nombre,
    asunto,
    tipo,
    responsable,
    estado,
    observaciones
):

    referencia = db.collection(
        COLECCION_EXPEDIENTES
    ).document()

    datos = {

        "numero_control": numero_control,

        "numero_expediente": numero_expediente,

        "fecha_expediente": fecha.strftime("%Y-%m-%d"),

        "nombre_relacionado": nombre,

        "asunto": asunto,

        "tipo_asunto": tipo,

        "responsable": responsable,

        "estado": estado,

        "observaciones": observaciones,

        "documentos": 0,

        "fecha_registro": datetime.now(),

        "ultima_actualizacion": datetime.now()

    }

    referencia.set(datos)

    return referencia.id


# ==========================================================
# BUSCAR EXPEDIENTES
# ==========================================================

def buscar_expedientes(texto):

    documentos = (
        db.collection(COLECCION_EXPEDIENTES)
        .stream()
    )

    resultados = []

    texto = texto.lower().strip()

    for documento in documentos:

        datos = documento.to_dict()

        campos = [

            datos.get("numero_expediente", ""),

            datos.get("nombre_relacionado", ""),

            datos.get("asunto", ""),

            datos.get("tipo_asunto", ""),

            datos.get("responsable", ""),

            datos.get("estado", ""),

            datos.get("observaciones", "")

        ]

        encontrado = False

        for campo in campos:

            if texto in str(campo).lower():

                encontrado = True
                break

        if encontrado:

            datos["id"] = documento.id

            resultados.append(datos)

    return resultados


# ==========================================================
# ELIMINAR EXPEDIENTE
# ==========================================================

def eliminar_expediente(documento_id):

    db.collection(
        COLECCION_EXPEDIENTES
    ).document(documento_id).delete()


# ==========================================================
# ENCABEZADO
# ==========================================================

st.title(
    "⚖️ Plataforma de Expedientes Jurídicos"
)

st.caption(
    "Sistema de Digitalización, Administración y Consulta "
    "de Expedientes Jurídicos"
)

st.divider()


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.title("⚖️ JURÍDICO")

st.sidebar.caption(
    "Expedientes Digitales"
)

st.sidebar.divider()

opcion = st.sidebar.radio(
    "MENÚ PRINCIPAL",
    [
        "🏠 Inicio",
        "➕ Nuevo expediente",
        "📋 Expedientes",
        "🔎 Buscar"
    ]
)

st.sidebar.divider()

st.sidebar.caption(
    "Base de datos: Firebase + Storage"
)


# ==========================================================
# INICIO
# ==========================================================

if opcion == "🏠 Inicio":

    st.header("Panel principal")

    try:

        expedientes = obtener_expedientes()

        total = len(expedientes)

        tramite = sum(
            1 for x in expedientes
            if x.get("estado") == "En trámite"
        )

        concluidos = sum(
            1 for x in expedientes
            if x.get("estado") == "Concluido"
        )

        pendientes = sum(
            1 for x in expedientes
            if x.get("estado") == "Pendiente"
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "📁 Expedientes",
                total
            )

        with col2:

            st.metric(
                "🟡 En trámite",
                tramite
            )

        with col3:

            st.metric(
                "🟢 Concluidos",
                concluidos
            )

        with col4:

            st.metric(
                "🟠 Pendientes",
                pendientes
            )

        st.divider()

        st.subheader(
            "📂 Expedientes recientes"
        )

        if expedientes:

            for expediente in expedientes[:10]:

                numero = expediente.get(
                    "numero_expediente",
                    "Sin número"
                )

                nombre = expediente.get(
                    "nombre_relacionado",
                    "Sin nombre"
                )

                estado = expediente.get(
                    "estado",
                    "Sin estado"
                )

                asunto = expediente.get(
                    "asunto",
                    "Sin asunto"
                )

                with st.expander(
                    f"📁 {numero} — {nombre}"
                ):

                    col1, col2 = st.columns(2)

                    with col1:

                        st.write(
                            f"**Asunto:** {asunto}"
                        )

                        st.write(
                            f"**Tipo:** "
                            f"{expediente.get('tipo_asunto', '')}"
                        )

                        st.write(
                            f"**Fecha:** "
                            f"{expediente.get('fecha_expediente', '')}"
                        )

                    with col2:

                        st.write(
                            f"**Estado:** {estado}"
                        )

                        st.write(
                            f"**Responsable:** "
                            f"{expediente.get('responsable', 'Sin asignar')}"
                        )

                        st.write(
                            f"**Documentos:** "
                            f"{expediente.get('documentos', 0)}"
                        )

        else:

            st.info(
                "Todavía no existen expedientes registrados."
            )

    except Exception as e:

        st.error(
            "No fue posible consultar Firebase."
        )

        st.exception(e)


# ==========================================================
# NUEVO EXPEDIENTE
# ==========================================================

elif opcion == "➕ Nuevo expediente":

    st.header("➕ Nuevo expediente")

    try:

        siguiente = obtener_siguiente_numero()

        folio = crear_folio(siguiente)

    except Exception as e:

        st.error(
            "No fue posible generar el folio."
        )

        st.exception(e)

        st.stop()

    st.info(
        f"📌 Folio sugerido por el sistema: **{folio}**"
    )

    st.divider()

    col1, col2 = st.columns(2)

    # ------------------------------------------------------
    # COLUMNA 1
    # ------------------------------------------------------

    with col1:

        numero_expediente = st.text_input(
            "Número de expediente",
            value=folio
        )

        fecha = st.date_input(
            "Fecha del expediente",
            value=date.today()
        )

        nombre = st.text_input(
            "Nombre de la persona / empresa relacionada"
        )

        tipo = st.selectbox(
            "Tipo de asunto",
            [
                "Civil",
                "Laboral",
                "Administrativo",
                "Mercantil",
                "Penal",
                "Familiar",
                "Amparo",
                "Contrato",
                "Convenio",
                "Patrimonial",
                "Responsabilidad",
                "Otro"
            ]
        )

    # ------------------------------------------------------
    # COLUMNA 2
    # ------------------------------------------------------

    with col2:

        asunto = st.text_input(
            "Asunto"
        )

        responsable = st.text_input(
            "Responsable del expediente"
        )

        estado = st.selectbox(
            "Estado",
            [
                "En trámite",
                "Pendiente",
                "Concluido",
                "Archivado"
            ]
        )

    observaciones = st.text_area(
        "Observaciones",
        height=130
    )

    st.divider()

    guardar = st.button(
        "💾 GUARDAR EXPEDIENTE",
        type="primary",
        use_container_width=True
    )

    if guardar:

        if not numero_expediente.strip():

            st.error(
                "El número de expediente es obligatorio."
            )

        elif not asunto.strip():

            st.error(
                "El asunto es obligatorio."
            )

        else:

            try:

                guardar_expediente(
                    siguiente,
                    numero_expediente,
                    fecha,
                    nombre,
                    asunto,
                    tipo,
                    responsable,
                    estado,
                    observaciones
                )

                st.success(
                    f"✅ Expediente "
                    f"**{numero_expediente}** "
                    f"guardado correctamente."
                )

                st.info(
                    "📂 El expediente ya está disponible "
                    "en la base de datos."
                )

            except Exception as e:

                st.error(
                    "No fue posible guardar el expediente."
                )

                st.exception(e)


# ==========================================================
# EXPEDIENTES
# ==========================================================

elif opcion == "📋 Expedientes":

    st.header(
        "📋 Expedientes registrados"
    )

    try:

        expedientes = obtener_expedientes()

        if not expedientes:

            st.info(
                "No existen expedientes registrados."
            )

        else:

            st.write(
                f"Total de expedientes: **{len(expedientes)}**"
            )

            st.divider()

            for expediente in expedientes:

                numero = expediente.get(
                    "numero_expediente",
                    "Sin número"
                )

                nombre = expediente.get(
                    "nombre_relacionado",
                    "Sin nombre"
                )

                with st.expander(
                    f"📁 {numero} — {nombre}"
                ):

                    col1, col2 = st.columns(2)

                    with col1:

                        st.write(
                            f"**Número:** {numero}"
                        )

                        st.write(
                            f"**Fecha:** "
                            f"{expediente.get('fecha_expediente', '')}"
                        )

                        st.write(
                            f"**Relacionado:** "
                            f"{nombre}"
                        )

                        st.write(
                            f"**Asunto:** "
                            f"{expediente.get('asunto', '')}"
                        )

                    with col2:

                        st.write(
                            f"**Tipo:** "
                            f"{expediente.get('tipo_asunto', '')}"
                        )

                        st.write(
                            f"**Responsable:** "
                            f"{expediente.get('responsable', 'Sin asignar')}"
                        )

                        st.write(
                            f"**Estado:** "
                            f"{expediente.get('estado', '')}"
                        )

                        st.write(
                            f"**Documentos:** "
                            f"{expediente.get('documentos', 0)}"
                        )

                    st.write(
                        f"**Observaciones:** "
                        f"{expediente.get('observaciones', 'Sin observaciones')}"
                    )

                    st.divider()

                    st.subheader("📂 Documentación")
                    modulo_documentos(expediente["id"])

    except Exception as e:

        st.error(
            "No fue posible consultar los expedientes."
        )

        st.exception(e)


# ==========================================================
# BUSCAR
# ==========================================================

elif opcion == "🔎 Buscar":

    st.header(
        "🔎 Buscar expediente"
    )

    st.caption(
        "Puedes buscar por número, nombre, asunto, "
        "tipo, responsable, estado u observaciones."
    )

    texto = st.text_input(
        "¿Qué deseas buscar?",
        placeholder=(
            "Ejemplo: JUR-2026-0001, "
            "Juan Pérez, contrato..."
        )
    )

    if texto.strip():

        try:

            resultados = buscar_expedientes(
                texto
            )

            st.success(
                f"🔎 Se encontraron "
                f"**{len(resultados)}** resultados."
            )

            if resultados:

                for resultado in resultados:

                    numero = resultado.get(
                        "numero_expediente",
                        "Sin número"
                    )

                    nombre = resultado.get(
                        "nombre_relacionado",
                        "Sin nombre"
                    )

                    with st.expander(
                        f"📁 {numero} — {nombre}"
                    ):

                        col1, col2 = st.columns(2)

                        with col1:

                            st.write(
                                f"**Número:** {numero}"
                            )

                            st.write(
                                f"**Asunto:** "
                                f"{resultado.get('asunto', '')}"
                            )

                            st.write(
                                f"**Tipo:** "
                                f"{resultado.get('tipo_asunto', '')}"
                            )

                        with col2:

                            st.write(
                                f"**Responsable:** "
                                f"{resultado.get('responsable', 'Sin asignar')}"
                            )

                            st.write(
                                f"**Estado:** "
                                f"{resultado.get('estado', '')}"
                            )

                            st.write(
                                f"**Fecha:** "
                                f"{resultado.get('fecha_expediente', '')}"
                            )

                        st.write(
                            f"**Observaciones:** "
                            f"{resultado.get('observaciones', '')}"
                        )

                        st.divider()
                        st.subheader("📂 Documentación")
                        modulo_documentos(resultado["id"])

            else:

                st.warning(
                    "No se encontraron expedientes."
                )

        except Exception as e:

            st.error(
                "Error al realizar la búsqueda."
            )

            st.exception(e)