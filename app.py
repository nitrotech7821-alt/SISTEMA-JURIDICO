import streamlit as st
import pyodbc
from datetime import date

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
# DISEÑO
# ==========================================================

st.markdown("""
<style>

.stApp {
    background-color: #eef1f5;
}

/* SIDEBAR */
[data-testid="stSidebar"] {
    background-color: #0b1f3a;
}

[data-testid="stSidebar"] * {
    color: white !important;
}

/* TITULOS */
h1 {
    color: #0b1f3a;
}

h2, h3 {
    color: #163a63;
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

/* CAMPOS */
.stTextInput input,
.stTextArea textarea {
    border-radius: 7px;
}

/* EXPANDERS */
[data-testid="stExpander"] {
    background-color: white;
    border-radius: 10px;
}

/* ALERTAS */
.stAlert {
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)


# ==========================================================
# CONEXIÓN SQL SERVER
# ==========================================================

def conectar():

    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost\\SQLEXPRESS;"
        "DATABASE=ExpedientesJuridicos;"
        "Trusted_Connection=yes;"
    )


# ==========================================================
# OBTENER EXPEDIENTES
# ==========================================================

def obtener_expedientes():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            Id,
            NumeroExpediente,
            FechaExpediente,
            NombreRelacionado,
            Asunto,
            TipoAsunto,
            Responsable,
            Estado,
            Observaciones
        FROM Expedientes
        ORDER BY Id DESC
    """)

    datos = cursor.fetchall()

    cursor.close()
    conn.close()

    return datos


# ==========================================================
# FOLIO AUTOMÁTICO
# ==========================================================

def obtener_siguiente_folio():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ISNULL(MAX(Id), 0) + 1
        FROM Expedientes
    """)

    numero = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return f"JUR-{date.today().year}-{numero:04d}"


# ==========================================================
# GUARDAR EXPEDIENTE
# ==========================================================

def guardar_expediente(
    numero,
    fecha,
    nombre,
    asunto,
    tipo,
    responsable,
    estado,
    observaciones
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO Expedientes
        (
            NumeroExpediente,
            FechaExpediente,
            NombreRelacionado,
            Asunto,
            TipoAsunto,
            Responsable,
            Estado,
            Observaciones
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    numero,
    fecha,
    nombre,
    asunto,
    tipo,
    responsable,
    estado,
    observaciones)

    conn.commit()

    cursor.close()
    conn.close()


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
        "🔎 Buscar"
    ]
)

st.sidebar.divider()

st.sidebar.caption(
    "Sistema de Digitalización y Consulta"
)


# ==========================================================
# ENCABEZADO
# ==========================================================

st.title("⚖️ Plataforma de Expedientes Jurídicos")

st.caption(
    "Sistema de Digitalización, Administración y Consulta "
    "de Expedientes Jurídicos"
)

st.divider()


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
            if x[7] == "En trámite"
        )

        concluidos = sum(
            1 for x in expedientes
            if x[7] == "Concluido"
        )

        pendientes = sum(
            1 for x in expedientes
            if x[7] == "Pendiente"
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("📁 Expedientes", total)

        with col2:
            st.metric("🟡 En trámite", tramite)

        with col3:
            st.metric("🟢 Concluidos", concluidos)

        with col4:
            st.metric("🟠 Pendientes", pendientes)

        st.divider()

        st.subheader("📂 Expedientes recientes")

        if expedientes:

            for expediente in expedientes[:10]:

                with st.expander(
                    f"📁 {expediente[1]} — "
                    f"{expediente[3] or 'Sin nombre'}"
                ):

                    col1, col2 = st.columns(2)

                    with col1:

                        st.write(
                            f"**Fecha:** {expediente[2]}"
                        )

                        st.write(
                            f"**Tipo:** {expediente[5]}"
                        )

                    with col2:

                        st.write(
                            f"**Estado:** {expediente[7]}"
                        )

                        st.write(
                            f"**Responsable:** "
                            f"{expediente[6] or 'Sin asignar'}"
                        )

                    st.write(
                        f"**Asunto:** "
                        f"{expediente[4] or 'Sin asunto'}"
                    )

        else:

            st.info(
                "Todavía no existen expedientes registrados."
            )

    except Exception as e:

        st.error(
            "No se pudo conectar con SQL Server."
        )

        st.code(str(e))


# ==========================================================
# NUEVO EXPEDIENTE
# ==========================================================

elif opcion == "➕ Nuevo expediente":

    st.header("➕ Nuevo expediente")

    try:
        folio = obtener_siguiente_folio()

    except Exception:
        folio = f"JUR-{date.today().year}-0001"

    st.info(
        f"📌 Folio sugerido: **{folio}**"
    )

    col1, col2 = st.columns(2)

    with col1:

        numero = st.text_input(
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

    if st.button(
        "💾 GUARDAR EXPEDIENTE",
        type="primary",
        use_container_width=True
    ):

        if not numero.strip():

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
                    numero,
                    fecha,
                    nombre,
                    asunto,
                    tipo,
                    responsable,
                    estado,
                    observaciones
                )

                st.success(
                    f"✅ Expediente {numero} guardado correctamente."
                )

            except Exception as e:

                st.error(
                    "No fue posible guardar el expediente."
                )

                st.code(str(e))


# ==========================================================
# EXPEDIENTES
# ==========================================================

elif opcion == "📋 Expedientes":

    st.header("📋 Expedientes registrados")

    try:

        expedientes = obtener_expedientes()

        if not expedientes:

            st.info(
                "No existen expedientes registrados."
            )

        else:

            for expediente in expedientes:

                with st.expander(
                    f"📁 {expediente[1]} — "
                    f"{expediente[3] or 'Sin nombre'}"
                ):

                    st.write(
                        f"**Fecha:** {expediente[2]}"
                    )

                    st.write(
                        f"**Asunto:** "
                        f"{expediente[4] or 'Sin asunto'}"
                    )

                    st.write(
                        f"**Tipo:** {expediente[5]}"
                    )

                    st.write(
                        f"**Responsable:** "
                        f"{expediente[6] or 'Sin asignar'}"
                    )

                    st.write(
                        f"**Estado:** {expediente[7]}"
                    )

                    st.write(
                        f"**Observaciones:** "
                        f"{expediente[8] or 'Sin observaciones'}"
                    )

    except Exception as e:

        st.error(
            "No se pudo consultar SQL Server."
        )

        st.code(str(e))


# ==========================================================
# BUSCAR
# ==========================================================

elif opcion == "🔎 Buscar":

    st.header("🔎 Buscar expediente")

    st.caption(
        "Busca por número, nombre, asunto, tipo o responsable."
    )

    texto = st.text_input(
        "¿Qué deseas buscar?",
        placeholder="Ejemplo: JUR-2026-0001, Juan Pérez, contrato..."
    )

    if texto:

        try:

            conn = conectar()
            cursor = conn.cursor()

            busqueda = f"%{texto}%"

            cursor.execute("""
                SELECT
                    Id,
                    NumeroExpediente,
                    FechaExpediente,
                    NombreRelacionado,
                    Asunto,
                    TipoAsunto,
                    Responsable,
                    Estado
                FROM Expedientes
                WHERE
                    NumeroExpediente LIKE ?
                    OR NombreRelacionado LIKE ?
                    OR Asunto LIKE ?
                    OR TipoAsunto LIKE ?
                    OR Responsable LIKE ?
                ORDER BY Id DESC
            """,
            busqueda,
            busqueda,
            busqueda,
            busqueda,
            busqueda)

            resultados = cursor.fetchall()

            cursor.close()
            conn.close()

            st.success(
                f"🔎 Se encontraron {len(resultados)} resultados."
            )

            for resultado in resultados:

                with st.expander(
                    f"📁 {resultado[1]} — "
                    f"{resultado[3] or 'Sin nombre'}"
                ):

                    st.write(
                        f"**Asunto:** {resultado[4] or 'Sin asunto'}"
                    )

                    st.write(
                        f"**Tipo:** {resultado[5]}"
                    )

                    st.write(
                        f"**Responsable:** "
                        f"{resultado[6] or 'Sin asignar'}"
                    )

                    st.write(
                        f"**Estado:** {resultado[7]}"
                    )

        except Exception as e:

            st.error(
                "Error al realizar la búsqueda."
            )

            st.code(str(e))