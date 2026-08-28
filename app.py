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
    initial_sidebar_state="expanded",
)

COLECCION_EXPEDIENTES = "expedientes_juridicos"
COLECCION_CONFIG = "configuracion"
DOCUMENTOS_SUBCOLECCION = "documentos"
EXTENSIONES_PERMITIDAS = ["pdf", "jpg", "jpeg", "png", "tif", "tiff"]

# ==========================================================
# ESTILOS
# ==========================================================
st.markdown(
    """
<style>
.stApp {
    background-color: #eef1f5;
}
[data-testid="stSidebar"] {
    background-color: #0b1f3a;
}
[data-testid="stSidebar"] * {
    color: white !important;
}
h1 {
    color: #0b1f3a !important;
    font-weight: 700 !important;
}
h2, h3 {
    color: #163a63 !important;
}
[data-testid="stMetric"] {
    background-color: white;
    padding: 18px;
    border-radius: 12px;
    border-top: 4px solid #c9a227;
    box-shadow: 0px 3px 10px rgba(0,0,0,0.08);
}
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
.stTextInput input,
.stTextArea textarea {
    border-radius: 7px;
}
[data-testid="stExpander"] {
    background-color: white;
    border-radius: 10px;
}
hr {
    border-color: #d5dbe3;
}
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# FIREBASE
# ==========================================================
@st.cache_resource

def inicializar_firebase():
    """Inicializa Firebase una sola vez y devuelve Firestore + Storage."""
    if firebase_admin._apps:
        app = firebase_admin.get_app()
    else:
        if "firebase" not in st.secrets:
            raise RuntimeError(
                "No existe la sección [firebase] en Streamlit Secrets."
            )

        firebase_config = dict(st.secrets["firebase"])

        # Evita que una clave de ejemplo provoque errores difíciles de detectar.
        obligatorios = [
            "type",
            "project_id",
            "private_key",
            "client_email",
            "client_id",
            "auth_uri",
            "token_uri",
            "auth_provider_x509_cert_url",
            "client_x509_cert_url",
            "storage_bucket",
        ]
        faltantes = [x for x in obligatorios if not firebase_config.get(x)]
        if faltantes:
            raise RuntimeError(
                "Faltan estos campos en [firebase]: " + ", ".join(faltantes)
            )

        private_key = firebase_config["private_key"]
        # Streamlit Secrets puede recibir la clave con \n literales.
        private_key = private_key.replace("\\n", "\n")
        firebase_config["private_key"] = private_key

        cred = credentials.Certificate(firebase_config)
        app = firebase_admin.initialize_app(
            cred,
            {
                "storageBucket": firebase_config["storage_bucket"],
            },
        )

    db = firestore.client(app=app)
    bucket = storage.bucket(app=app)
    return db, bucket


try:
    db, bucket = inicializar_firebase()
    FIREBASE_OK = True
    FIREBASE_ERROR = None
except Exception as e:
    db = None
    bucket = None
    FIREBASE_OK = False
    FIREBASE_ERROR = str(e)

# ==========================================================
# SIDEBAR
# ==========================================================
st.sidebar.title("⚖️ JURÍDICO")
st.sidebar.caption("Expedientes Digitales")
st.sidebar.divider()

opcion = st.sidebar.radio(
    "MENÚ PRINCIPAL",
    [
        "🏠 Inicio",
        "➕ Nuevo expediente",
        "📋 Expedientes",
        "🔎 Buscar",
    ],
)

st.sidebar.divider()
if FIREBASE_OK:
    st.sidebar.success("🟢 Firebase conectado")
    st.sidebar.caption("Base de datos: Firebase + Storage")
else:
    st.sidebar.error("🔴 Firebase sin conexión")
    st.sidebar.caption("Revisa Streamlit Secrets")

# ==========================================================
# SI FIREBASE NO CONECTA, NO EJECUTAR EL RESTO
# ==========================================================
if not FIREBASE_OK:
    st.title("⚖️ Plataforma de Expedientes Jurídicos")
    st.caption("Sistema de Digitalización, Administración y Consulta de Expedientes Jurídicos")
    st.divider()
    st.error("❌ No fue posible conectar con Firebase.")
    st.warning(
        "La aplicación sí está funcionando, pero necesita las credenciales correctas "
        "en Streamlit → App settings → Secrets."
    )
    st.subheader("Diagnóstico")
    st.code(FIREBASE_ERROR or "Error desconocido")
    st.info(
        "Verifica especialmente: project_id, client_email, private_key y storage_bucket."
    )
    st.stop()

# ==========================================================
# FUNCIONES FIRESTORE / STORAGE
# ==========================================================
def obtener_documentos(expediente_id):
    docs = (
        db.collection(COLECCION_EXPEDIENTES)
        .document(expediente_id)
        .collection(DOCUMENTOS_SUBCOLECCION)
        .order_by("fecha_registro", direction=firestore.Query.DESCENDING)
        .stream()
    )
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

    contenido = archivo.getvalue()
    if not contenido:
        raise ValueError("El archivo está vacío.")

    nombre_storage = f"{uuid.uuid4().hex}_{nombre_original}"
    ruta = f"expedientes_juridicos/{expediente_id}/{nombre_storage}"
    content_type = (
        archivo.type
        or mimetypes.guess_type(nombre_original)[0]
        or "application/octet-stream"
    )

    blob = bucket.blob(ruta)
    blob.upload_from_string(contenido, content_type=content_type)

    try:
        ref = (
            db.collection(COLECCION_EXPEDIENTES)
            .document(expediente_id)
            .collection(DOCUMENTOS_SUBCOLECCION)
            .document()
        )
        ref.set(
            {
                "nombre": nombre_original,
                "categoria": categoria,
                "tipo": content_type,
                "tamano": len(contenido),
                "storage_path": ruta,
                "fecha_registro": datetime.now(),
            }
        )

        total = len(obtener_documentos(expediente_id))
        db.collection(COLECCION_EXPEDIENTES).document(expediente_id).update(
            {
                "documentos": total,
                "ultima_actualizacion": datetime.now(),
            }
        )
    except Exception:
        # Si Firestore falla después de subir el archivo, intenta no dejar basura en Storage.
        try:
            blob.delete()
        except Exception:
            pass
        raise


def url_documento(storage_path):
    blob = bucket.blob(storage_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=24),
        method="GET",
    )


def eliminar_documento(expediente_id, documento_id, storage_path):
    blob = bucket.blob(storage_path)
    try:
        if blob.exists():
            blob.delete()
    finally:
        (
            db.collection(COLECCION_EXPEDIENTES)
            .document(expediente_id)
            .collection(DOCUMENTOS_SUBCOLECCION)
            .document(documento_id)
            .delete()
        )

    total = len(obtener_documentos(expediente_id))
    db.collection(COLECCION_EXPEDIENTES).document(expediente_id).update(
        {
            "documentos": total,
            "ultima_actualizacion": datetime.now(),
        }
    )


def modulo_documentos(expediente_id):
    st.subheader("📂 Digitalización del expediente")
    st.caption(
        "Escanea el documento y guárdalo como PDF/JPG/PNG/TIFF; después súbelo aquí. "
        "Quedará asociado automáticamente al expediente."
    )

    categoria = st.selectbox(
        "Tipo de documento",
        [
            "Demanda / escrito",
            "Oficio",
            "Contrato",
            "Convenio",
            "Resolución",
            "Notificación",
            "Identificación",
            "Comprobante",
            "Evidencia",
            "Acuerdo",
            "Dictamen",
            "Anexo",
            "Otro",
        ],
        key=f"cat_{expediente_id}",
    )

    archivo = st.file_uploader(
        "📤 Seleccionar documento escaneado",
        type=EXTENSIONES_PERMITIDAS,
        key=f"upload_{expediente_id}",
    )

    if archivo:
        st.info(f"📄 {archivo.name} — {archivo.size / 1024 / 1024:.2f} MB")
        if st.button(
            "☁️ GUARDAR EN EL EXPEDIENTE",
            type="primary",
            key=f"save_doc_{expediente_id}",
        ):
            try:
                with st.spinner("Subiendo documento a Firebase Storage..."):
                    guardar_documento(expediente_id, archivo, categoria)
                st.success("✅ Documento guardado correctamente.")
                st.rerun()
            except Exception as e:
                st.error("No fue posible guardar el documento.")
                st.code(str(e))

    st.divider()
    try:
        documentos = obtener_documentos(expediente_id)
    except Exception as e:
        st.error("No fue posible consultar los documentos.")
        st.code(str(e))
        return

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
                tamano = doc.get("tamano", 0) or 0
                st.caption(f"Tamaño: {tamano / 1024 / 1024:.2f} MB")
            with c2:
                try:
                    st.link_button(
                        "👁️ Abrir documento",
                        url_documento(doc["storage_path"]),
                    )
                except Exception as e:
                    st.warning("No se pudo generar el enlace.")
                    st.caption(str(e))
            with c3:
                if st.button("🗑️", key=f"del_{expediente_id}_{doc['id']}"):
                    try:
                        eliminar_documento(
                            expediente_id,
                            doc["id"],
                            doc["storage_path"],
                        )
                        st.success("Documento eliminado.")
                        st.rerun()
                    except Exception as e:
                        st.error("No fue posible eliminar el documento.")
                        st.code(str(e))


def obtener_expedientes():
    documentos = (
        db.collection(COLECCION_EXPEDIENTES)
        .order_by("fecha_registro", direction=firestore.Query.DESCENDING)
        .stream()
    )

    expedientes = []
    for documento in documentos:
        datos = documento.to_dict()
        datos["id"] = documento.id
        expedientes.append(datos)
    return expedientes


def obtener_siguiente_numero():
    """Solo consulta el próximo folio; NO incrementa el contador."""
    referencia = db.collection(COLECCION_CONFIG).document("folios")
    documento = referencia.get()
    ultimo = documento.to_dict().get("ultimo", 0) if documento.exists else 0
    return int(ultimo) + 1


def reservar_siguiente_numero():
    """Incrementa el folio de forma atómica para evitar duplicados."""
    referencia = db.collection(COLECCION_CONFIG).document("folios")
    transaccion = db.transaction()

    @firestore.transactional
    def actualizar(transaction):
        documento = referencia.get(transaction=transaction)
        ultimo = documento.to_dict().get("ultimo", 0) if documento.exists else 0
        siguiente = int(ultimo) + 1
        transaction.set(
            referencia,
            {
                "ultimo": siguiente,
                "actualizado": datetime.now(),
            },
            merge=True,
        )
        return siguiente

    return actualizar(transaccion)


def crear_folio(numero):
    return f"JUR-{date.today().year}-{numero:04d}"


def guardar_expediente(
    numero_control,
    numero_expediente,
    fecha,
    nombre,
    asunto,
    tipo,
    responsable,
    estado,
    observaciones,
):
    referencia = db.collection(COLECCION_EXPEDIENTES).document()
    ahora = datetime.now()

    datos = {
        "numero_control": numero_control,
        "numero_expediente": numero_expediente.strip(),
        "fecha_expediente": fecha.strftime("%Y-%m-%d"),
        "nombre_relacionado": nombre.strip(),
        "asunto": asunto.strip(),
        "tipo_asunto": tipo,
        "responsable": responsable.strip(),
        "estado": estado,
        "observaciones": observaciones.strip(),
        "documentos": 0,
        "fecha_registro": ahora,
        "ultima_actualizacion": ahora,
    }

    referencia.set(datos)
    return referencia.id


def buscar_expedientes(texto):
    documentos = db.collection(COLECCION_EXPEDIENTES).stream()
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
            datos.get("observaciones", ""),
        ]

        if any(texto in str(campo).lower() for campo in campos):
            datos["id"] = documento.id
            resultados.append(datos)

    return resultados


def eliminar_expediente(documento_id):
    """Elimina expediente, subdocumentos y archivos de Storage asociados."""
    docs_ref = (
        db.collection(COLECCION_EXPEDIENTES)
        .document(documento_id)
        .collection(DOCUMENTOS_SUBCOLECCION)
    )

    documentos = list(docs_ref.stream())
    for documento in documentos:
        datos = documento.to_dict()
        storage_path = datos.get("storage_path")
        if storage_path:
            try:
                blob = bucket.blob(storage_path)
                if blob.exists():
                    blob.delete()
            except Exception:
                pass
        documento.reference.delete()

    db.collection(COLECCION_EXPEDIENTES).document(documento_id).delete()

# ==========================================================
# ENCABEZADO
# ==========================================================
st.title("⚖️ Plataforma de Expedientes Jurídicos")
st.caption("Sistema de Digitalización, Administración y Consulta de Expedientes Jurídicos")
st.divider()

# ==========================================================
# INICIO
# ==========================================================
if opcion == "🏠 Inicio":
    st.header("Panel principal")

    try:
        expedientes = obtener_expedientes()
        total = len(expedientes)
        tramite = sum(1 for x in expedientes if x.get("estado") == "En trámite")
        concluidos = sum(1 for x in expedientes if x.get("estado") == "Concluido")
        pendientes = sum(1 for x in expedientes if x.get("estado") == "Pendiente")
        documentos_total = sum(int(x.get("documentos", 0) or 0) for x in expedientes)

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📁 Expedientes", total)
        with col2:
            st.metric("🟡 En trámite", tramite)
        with col3:
            st.metric("🟢 Concluidos", concluidos)
        with col4:
            st.metric("🟠 Pendientes", pendientes)
        with col5:
            st.metric("📄 Documentos", documentos_total)

        st.divider()
        st.subheader("📂 Expedientes recientes")

        if expedientes:
            for expediente in expedientes[:10]:
                numero = expediente.get("numero_expediente", "Sin número")
                nombre = expediente.get("nombre_relacionado", "Sin nombre")
                estado = expediente.get("estado", "Sin estado")
                asunto = expediente.get("asunto", "Sin asunto")

                with st.expander(f"📁 {numero} — {nombre}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Asunto:** {asunto}")
                        st.write(f"**Tipo:** {expediente.get('tipo_asunto', '')}")
                        st.write(f"**Fecha:** {expediente.get('fecha_expediente', '')}")
                    with col2:
                        st.write(f"**Estado:** {estado}")
                        st.write(
                            f"**Responsable:** {expediente.get('responsable', 'Sin asignar')}"
                        )
                        st.write(f"**Documentos:** {expediente.get('documentos', 0)}")
        else:
            st.info("Todavía no existen expedientes registrados.")

    except Exception as e:
        st.error("No fue posible consultar Firebase.")
        st.code(str(e))

# ==========================================================
# NUEVO EXPEDIENTE
# ==========================================================
elif opcion == "➕ Nuevo expediente":
    st.header("➕ Nuevo expediente")

    try:
        siguiente = obtener_siguiente_numero()
        folio = crear_folio(siguiente)
    except Exception as e:
        st.error("No fue posible consultar el siguiente folio.")
        st.code(str(e))
        st.stop()

    st.info(f"📌 Folio sugerido por el sistema: **{folio}**")
    st.caption("El folio solo se asignará al guardar el expediente.")
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        numero_expediente = st.text_input("Número de expediente", value=folio)
        fecha = st.date_input("Fecha del expediente", value=date.today())
        nombre = st.text_input("Nombre de la persona / empresa relacionada")
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
                "Otro",
            ],
        )

    with col2:
        asunto = st.text_input("Asunto")
        responsable = st.text_input("Responsable del expediente")
        estado = st.selectbox(
            "Estado",
            ["En trámite", "Pendiente", "Concluido", "Archivado"],
        )

    observaciones = st.text_area("Observaciones", height=130)
    st.divider()

    guardar = st.button(
        "💾 GUARDAR EXPEDIENTE",
        type="primary",
        use_container_width=True,
    )

    if guardar:
        if not numero_expediente.strip():
            st.error("El número de expediente es obligatorio.")
        elif not asunto.strip():
            st.error("El asunto es obligatorio.")
        else:
            try:
                # El contador se incrementa SOLO al guardar.
                numero_control = reservar_siguiente_numero()
                folio_real = crear_folio(numero_control)

                # Si el usuario dejó el folio sugerido, se mantiene sincronizado.
                if numero_expediente.strip() == folio:
                    numero_expediente = folio_real

                guardar_expediente(
                    numero_control,
                    numero_expediente,
                    fecha,
                    nombre,
                    asunto,
                    tipo,
                    responsable,
                    estado,
                    observaciones,
                )

                st.success(
                    f"✅ Expediente **{numero_expediente}** guardado correctamente."
                )
                st.info("📂 Ya puedes entrar a 'Expedientes' para digitalizar documentos.")

            except Exception as e:
                st.error("No fue posible guardar el expediente.")
                st.code(str(e))

# ==========================================================
# EXPEDIENTES
# ==========================================================
elif opcion == "📋 Expedientes":
    st.header("📋 Expedientes registrados")

    try:
        expedientes = obtener_expedientes()

        if not expedientes:
            st.info("No existen expedientes registrados.")
        else:
            st.write(f"Total de expedientes: **{len(expedientes)}**")
            st.divider()

            for expediente in expedientes:
                numero = expediente.get("numero_expediente", "Sin número")
                nombre = expediente.get("nombre_relacionado", "Sin nombre")

                with st.expander(f"📁 {numero} — {nombre}"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Número:** {numero}")
                        st.write(f"**Fecha:** {expediente.get('fecha_expediente', '')}")
                        st.write(f"**Relacionado:** {nombre}")
                        st.write(f"**Asunto:** {expediente.get('asunto', '')}")

                    with col2:
                        st.write(f"**Tipo:** {expediente.get('tipo_asunto', '')}")
                        st.write(
                            f"**Responsable:** {expediente.get('responsable', 'Sin asignar')}"
                        )
                        st.write(f"**Estado:** {expediente.get('estado', '')}")
                        st.write(f"**Documentos:** {expediente.get('documentos', 0)}")

                    st.write(
                        f"**Observaciones:** "
                        f"{expediente.get('observaciones', 'Sin observaciones')}"
                    )

                    st.divider()
                    modulo_documentos(expediente["id"])

                    st.divider()
                    if st.button(
                        "🗑️ ELIMINAR EXPEDIENTE COMPLETO",
                        key=f"delete_exp_{expediente['id']}",
                    ):
                        st.warning(
                            "Esta acción eliminará el expediente y sus documentos digitalizados."
                        )
                        confirmar = st.checkbox(
                            "Confirmo que deseo eliminarlo",
                            key=f"confirm_delete_{expediente['id']}",
                        )
                        if confirmar:
                            try:
                                eliminar_expediente(expediente["id"])
                                st.success("Expediente eliminado correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error("No fue posible eliminar el expediente.")
                                st.code(str(e))

    except Exception as e:
        st.error("No fue posible consultar los expedientes.")
        st.code(str(e))

# ==========================================================
# BUSCAR
# ==========================================================
elif opcion == "🔎 Buscar":
    st.header("🔎 Buscar expediente")
    st.caption(
        "Puedes buscar por número, nombre, asunto, tipo, responsable, estado u observaciones."
    )

    texto = st.text_input(
        "¿Qué deseas buscar?",
        placeholder="Ejemplo: JUR-2026-0001, Juan Pérez, contrato...",
    )

    if texto.strip():
        try:
            resultados = buscar_expedientes(texto)
            st.success(f"🔎 Se encontraron **{len(resultados)}** resultados.")

            if resultados:
                for resultado in resultados:
                    numero = resultado.get("numero_expediente", "Sin número")
                    nombre = resultado.get("nombre_relacionado", "Sin nombre")

                    with st.expander(f"📁 {numero} — {nombre}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Número:** {numero}")
                            st.write(f"**Asunto:** {resultado.get('asunto', '')}")
                            st.write(f"**Tipo:** {resultado.get('tipo_asunto', '')}")
                        with col2:
                            st.write(
                                f"**Responsable:** {resultado.get('responsable', 'Sin asignar')}"
                            )
                            st.write(f"**Estado:** {resultado.get('estado', '')}")
                            st.write(f"**Fecha:** {resultado.get('fecha_expediente', '')}")

                        st.write(f"**Observaciones:** {resultado.get('observaciones', '')}")
                        st.divider()
                        modulo_documentos(resultado["id"])
            else:
                st.warning("No se encontraron expedientes.")

        except Exception as e:
            st.error("Error al realizar la búsqueda.")
            st.code(str(e))
