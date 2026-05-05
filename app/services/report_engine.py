from app.repositories import report_repository
from app.exports.excel_exporter import export_excel


REPORTS = {

    "general_report": {
        "query": report_repository.get_general_report,
        "params": ["estado", "fecha_inicio", "fecha_fin"],

        "columns": [
            ("Periodo Académico Tramitado", "periodo"),
            ("Programa académico",          "nivel"),
            ("Consecutivo de proyecto",     "consecutivo"),
            ("Nombre de la propuesta",      "titulo"),        # ✅ igual
            ("Modalidad",                   "modalidad"),
            ("Observaciones",               "observaciones"), # ✅ igual
            ("Nombre del director",         "director"),      # 🔧 era director_id
            ("Docente evaluador",           "evaluador"),     # 🔧 era evaluador_id
            ("Beneficiaros TyT / PRO",      "beneficiarios_icfes"),

            ("Nombre y Apellidos",          "nombre_est_1"),
            ("Documento de identidad",      "documento_est_1"),
            ("No. de Celular",              "celular_est_1"),
            ("Correo Electrónico",          "correo_est_1"),

            ("Nombres y Apellidos Autor 2", "nombre_est_2"),
            ("Documento de Identidad 2",    "documento_est_2"),
            ("Celular del autor 2",         "celular_est_2"),
            ("Correo del autor 2",          "correo_est_2"),

            ("Participantes",               "participantes"), # 🔧 era cantidad_est

            ("APROBACIÓN PROPUESTA F-DC-124 - F-DC-127",        "acta_aprobacion_propuesta"),
            ("(Fecha de aprobación por parte de evaluador, número de Acta y fecha de acta)",       "fecha_aprobacion_acta"),
            ("FECHA VENCIMIENTO",           "fecha_maxima"),
            ("APROBACIÓN PROPUESTA F-DC-125 - F-DC-128",            "acta_aprobacion_final"),
            ("(Fecha de aprobación por parte de evaluador, número de Acta y fecha de acta)",      "fecha_aprobacion_final"),

            ("Prórroga",                    "acta_fecha_prorroga"),
            ("Fecha Prórroga",              "fecha_prorroga"),
            ("Enlace Repositorio",          "link_repo"),
            ("Mínimo tiempo",               "fecha_minima"),
            ("primera cc",           "documento_est_1_alt"),
            ("segunda cc",           "documento_est_2_alt"),
            ("Enlace repositorio exentos",  "link_repo_exento"),
        ],
        
        "title": "Reporte General TG Sistemas"
    },

    # "modalidad":{
    #     "query": "",
    #     "columns": :[]
    # }
}

# =========================
def generate_report(report_name, db, params):

    if report_name not in REPORTS:
        raise Exception(f"Reporte '{report_name}' no existe")

    report = REPORTS[report_name]

    query_function = report["query"]
    columns = report["columns"]
    expected_params = report.get("params", [])

    # =========================
    clean_params = []

    for param in expected_params:
        value = params.get(param, None)
        clean_params.append(value)

    # =========================
    data = query_function(
        db,
        columns,
        *clean_params
    )
    # DEBUG TEMPORAL — quitar después
    if data:
        print("🔍 Keys que retorna la query:", list(data[0].keys()))
        print("🔍 Primera fila:", data[0])

    # =========================
    if not data:
        print("⚠️ Reporte sin datos")

    # =========================
    file_path = export_excel(
        data,
        columns,
        report["title"]
    )

    return file_path