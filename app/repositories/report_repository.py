from sqlalchemy import text
from typing import Optional, List, Tuple


def get_general_report(
    db,
    columns: List[Tuple[str, str]],
    estado: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
):
    """
    Reporte general consolidado por proyecto.

    Arquitectura real de la BD:
      - tipo 1: propuesta/idea inicial
      - tipo 2: proyecto formal — contiene TODOS los campos relevantes:
                director_id, evaluador_id, integrantes, modalidad, nivel,
                periodo, título, documentos, etc.
                El campo EAV 'idea_banco' guarda el id de la solicitud tipo 1.
      - actas.proyecto_id → solicitudes.id de tipo 2

    La query ancla en tipo 2 y desde ahí resuelve todo.
    """

    where_clauses = [
        "s.deleted_at IS NULL",
        "s.tipo_solicitud_id = 2",
    ]
    params = {}

    if estado:
        where_clauses.append("s.estado = :estado")
        params["estado"] = estado

    if fecha_inicio:
        where_clauses.append("s.created_at >= :fecha_inicio")
        params["fecha_inicio"] = fecha_inicio

    if fecha_fin:
        where_clauses.append("s.created_at <= :fecha_fin")
        params["fecha_fin"] = fecha_fin

    where_sql = " AND ".join(where_clauses)

    query = f"""
        SELECT
            -- ── Identificación ───────────────────────────────────────────
            s.id                                                            AS id,

            -- ── EAV tipo 2: campos simples ───────────────────────────────
            MAX(CASE WHEN c.name = 'periodo'             THEN vc.valor END) AS periodo,
            MAX(CASE WHEN c.name = 'codigo_modalidad'    THEN vc.valor END) AS consecutivo,
            MAX(CASE WHEN c.name = 'objetivo'            THEN vc.valor END) AS objetivo,
            MAX(CASE WHEN c.name = 'descripcion'         THEN vc.valor END) AS observaciones,
            -- Contar cuántos integrantes son beneficiarios TyT/PRO
            -- El valor es un JSON array de IDs: ["317"] → 1, ["1","2"] → 2
            COALESCE(
                JSON_LENGTH(
                    MAX(CASE WHEN c.name = 'beneficiarios_icfes' THEN vc.valor END)
                ),
                0
            )                                                               AS beneficiarios_icfes,

            -- Título: preferir tipo 2, fallback a tipo 1
            COALESCE(
                NULLIF(MAX(CASE WHEN c.name = 'titulo'   THEN vc.valor END), ''),
                s1.titulo_idea
            )                                                               AS titulo,

            -- ── Relaciones: nivel y modalidad ────────────────────────────
            niv.nombre                                                      AS nivel,
            tbl_mod.nombre                                                      AS modalidad,

            -- ── Relaciones: director, evaluador, codirector ───────────────
            tbl_dir.name                                                        AS director,
            tbl_eva.name                                                        AS evaluador,
            tbl_codir.name                                                      AS codirector,

            -- ── Integrante 1 ─────────────────────────────────────────────
            usr_int1.name                                                   AS nombre_est_1,
            usr_int1.nro_documento                                          AS documento_est_1,
            usr_int1.nro_celular                                            AS celular_est_1,
            usr_int1.email                                                  AS correo_est_1,

            -- ── Integrante 2 ─────────────────────────────────────────────
            usr_int2.name                                                   AS nombre_est_2,
            usr_int2.nro_documento                                          AS documento_est_2,
            usr_int2.nro_celular                                            AS celular_est_2,
            usr_int2.email                                                  AS correo_est_2,

            -- ── Participantes ─────────────────────────────────────────────
            CASE
                WHEN usr_int2.id IS NOT NULL THEN 2
                ELSE 1
            END                                                             AS participantes,

            -- ── Acta aprobación propuesta (fdc 124) ──────────────────────
            acta_aprobacion.numero                                          AS acta_aprobacion_propuesta,
            acta_aprobacion.fecha                                           AS fecha_aprobacion_acta,

            -- ── Acta aprobación informe final (fdc 125) ───────────────────
            acta_final.numero                                               AS acta_aprobacion_final,
            acta_final.fecha                                                AS fecha_aprobacion_final,

            -- ── Prórroga ─────────────────────────────────────────────────
            acta_prorroga.numero                                            AS acta_fecha_prorroga,
            acta_prorroga.fecha                                             AS fecha_prorroga,

            -- ── Fechas calculadas ─────────────────────────────────────────
            -- Mínimo tiempo: 90 días después de aprobación propuesta
            CASE
                WHEN acta_aprobacion.fecha IS NOT NULL
                THEN DATE_ADD(acta_aprobacion.fecha, INTERVAL 90 DAY)
            END                                                             AS fecha_minima,

            -- Vencimiento: 180 días desde aprobación propuesta
            -- Si tiene prórroga: 180 días adicionales desde el vencimiento inicial
            CASE
                WHEN acta_aprobacion.fecha IS NOT NULL AND acta_prorroga.fecha IS NOT NULL
                THEN DATE_ADD(DATE_ADD(acta_aprobacion.fecha, INTERVAL 180 DAY), INTERVAL 180 DAY)
                WHEN acta_aprobacion.fecha IS NOT NULL
                THEN DATE_ADD(acta_aprobacion.fecha, INTERVAL 180 DAY)
            END                                                             AS fecha_maxima,

            -- ── Pendientes ────────────────────────────────────────────────
            NULL                                                            AS link_repo,
            NULL                                                            AS link_repo_exento,
            NULL                                                            AS documento_est_1_alt,
            NULL                                                            AS documento_est_2_alt

        FROM solicitudes s

        -- ── EAV principal (todos los tipos de la solicitud) ─────────────
        -- Sin filtro de tipo_solicitud_id: una misma solicitud acumula
        -- campos de tipo 2,3,4,5,6,7 según avanza en fases
        LEFT JOIN valores_campos vc ON vc.solicitud_id = s.id
        LEFT JOIN campos c ON c.id = vc.campo_id

        -- ── Título desde tipo 1 via idea_banco ───────────────────────────
        LEFT JOIN (
            SELECT
                s1.id,
                MAX(CASE WHEN c1.name = 'titulo' THEN vc1.valor END) AS titulo_idea
            FROM solicitudes s1
            JOIN valores_campos vc1 ON vc1.solicitud_id = s1.id
            JOIN campos c1 ON c1.id = vc1.campo_id AND c1.tipo_solicitud_id = 1
            WHERE s1.tipo_solicitud_id = 1
              AND s1.deleted_at IS NULL
            GROUP BY s1.id
        ) s1 ON s1.id = (
            SELECT CAST(vc_idea.valor AS UNSIGNED)
            FROM valores_campos vc_idea
            JOIN campos c_idea ON c_idea.id = vc_idea.campo_id
            WHERE vc_idea.solicitud_id = s.id
              AND c_idea.name = 'idea_banco'
              AND c_idea.tipo_solicitud_id = 3
            LIMIT 1
        )

        -- ── Nivel ────────────────────────────────────────────────────────
        LEFT JOIN niveles niv ON niv.id = (
            SELECT CAST(vc_n.valor AS UNSIGNED)
            FROM valores_campos vc_n
            JOIN campos c_n ON c_n.id = vc_n.campo_id
            WHERE vc_n.solicitud_id = s.id
              AND c_n.name = 'nivel'
              AND c_n.tipo_solicitud_id = 2
            LIMIT 1
        )

        -- ── Modalidad ────────────────────────────────────────────────────
        LEFT JOIN modalidades tbl_mod ON tbl_mod.id = (
            SELECT CAST(vc_m.valor AS UNSIGNED)
            FROM valores_campos vc_m
            JOIN campos c_m ON c_m.id = vc_m.campo_id
            WHERE vc_m.solicitud_id = s.id
              AND c_m.name = 'modalidad'
              AND c_m.tipo_solicitud_id = 2
            LIMIT 1
        )

        -- ── Director ─────────────────────────────────────────────────────
        LEFT JOIN users tbl_dir ON tbl_dir.id = (
            SELECT CAST(vc_d.valor AS UNSIGNED)
            FROM valores_campos vc_d
            JOIN campos c_d ON c_d.id = vc_d.campo_id
            WHERE vc_d.solicitud_id = s.id
              AND c_d.name = 'director_id'
              AND c_d.tipo_solicitud_id = 3
            LIMIT 1
        )

        -- ── Evaluador ────────────────────────────────────────────────────
        LEFT JOIN users tbl_eva ON tbl_eva.id = (
            SELECT CAST(vc_e.valor AS UNSIGNED)
            FROM valores_campos vc_e
            JOIN campos c_e ON c_e.id = vc_e.campo_id
            WHERE vc_e.solicitud_id = s.id
              AND c_e.name = 'evaluador_id'
              AND c_e.tipo_solicitud_id = 3
            LIMIT 1
        )

        -- ── Codirector ───────────────────────────────────────────────────
        LEFT JOIN users tbl_codir ON tbl_codir.id = (
            SELECT CAST(vc_cd.valor AS UNSIGNED)
            FROM valores_campos vc_cd
            JOIN campos c_cd ON c_cd.id = vc_cd.campo_id
            WHERE vc_cd.solicitud_id = s.id
              AND c_cd.name = 'codirector_id'
              AND c_cd.tipo_solicitud_id = 3
            LIMIT 1
        )

        -- ── Integrante 1 ─────────────────────────────────────────────────
        LEFT JOIN users usr_int1 ON usr_int1.id = (
            SELECT CAST(vc_i1.valor AS UNSIGNED)
            FROM valores_campos vc_i1
            JOIN campos c_i1 ON c_i1.id = vc_i1.campo_id
            WHERE vc_i1.solicitud_id = s.id
              AND c_i1.name = 'id_integrante_1'
              AND c_i1.tipo_solicitud_id = 2
            LIMIT 1
        )

        -- ── Integrante 2 ─────────────────────────────────────────────────
        LEFT JOIN users usr_int2 ON usr_int2.id = (
            SELECT CAST(vc_i2.valor AS UNSIGNED)
            FROM valores_campos vc_i2
            JOIN campos c_i2 ON c_i2.id = vc_i2.campo_id
            WHERE vc_i2.solicitud_id = s.id
              AND c_i2.name = 'id_integrante_2'
              AND c_i2.tipo_solicitud_id = 2
            LIMIT 1
        )

        -- ── Acta aprobación propuesta (fdc 124) ──────────────────────────
        LEFT JOIN actas acta_aprobacion ON acta_aprobacion.id = (
            SELECT MIN(a.id)
            FROM actas a
            WHERE a.proyecto_id = s.id
              AND a.descripcion = 'Aprobación de la propuesta'
              AND a.deleted_at IS NULL
        )

        -- ── Acta aprobación informe final (fdc 125) ───────────────────────
        LEFT JOIN actas acta_final ON acta_final.id = (
            SELECT MIN(a.id)
            FROM actas a
            WHERE a.proyecto_id = s.id
              AND a.descripcion = 'Aprobación del informe final'
              AND a.deleted_at IS NULL
        )

        -- ── Prórroga (Aplazamiento de la propuesta) ──────────────────────────────────────────────────────
        LEFT JOIN actas acta_prorroga ON acta_prorroga.id = (
            SELECT MIN(a.id)
            FROM actas a
            WHERE a.proyecto_id = s.id
              AND a.descripcion = 'Aplazamiento de la propuesta'
              AND a.deleted_at IS NULL
        )

        WHERE {where_sql}

        GROUP BY
            s.id,
            s1.titulo_idea,
            niv.nombre,
            tbl_mod.nombre,
            tbl_dir.name,
            tbl_eva.name,
            tbl_codir.name,
            usr_int1.id, usr_int1.name, usr_int1.nro_documento, usr_int1.nro_celular, usr_int1.email,
            usr_int2.id, usr_int2.name, usr_int2.nro_documento, usr_int2.nro_celular, usr_int2.email,
            acta_aprobacion.numero, acta_aprobacion.fecha,
            acta_final.numero, acta_final.fecha,
            acta_prorroga.numero, acta_prorroga.fecha

        ORDER BY s.created_at DESC
    """

    result = db.execute(text(query), params)
    return [dict(row._mapping) for row in result]


def get_arl_report(
    db,
    columns: List[Tuple[str, str]],
    estado: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
):
    """
    Reporte ARL: estudiantes con propuesta aprobada (fase_3 = tipo_solicitud_id 5).
 
    Las solicitudes tipo 5 contienen directamente los campos EAV de tipo 2
    (id_integrante_1, id_integrante_2, nivel, modalidad, periodo).
    Cada integrante se devuelve como fila separada.
    """
 
    query = """
        SELECT
            usr_int.name            AS apellidos_nombres,
            usr_int.nro_documento   AS nro_documento,
            niv.nombre              AS programa_academico,
            'PRINCIPAL'             AS sede
 
        FROM (
 
            -- ── Integrante 1 ─────────────────────────────────────────────
            SELECT s.id AS solicitud_id, u.id, u.name, u.nro_documento
            FROM solicitudes s
            JOIN valores_campos vc ON vc.solicitud_id = s.id
            JOIN campos c ON c.id = vc.campo_id
                AND c.name = 'id_integrante_1'
                AND c.tipo_solicitud_id = 2
            JOIN users u ON u.id = CAST(vc.valor AS UNSIGNED)
            WHERE s.tipo_solicitud_id = 5
              AND s.deleted_at IS NULL
 
            UNION ALL
 
            -- ── Integrante 2 ─────────────────────────────────────────────
            SELECT s.id AS solicitud_id, u.id, u.name, u.nro_documento
            FROM solicitudes s
            JOIN valores_campos vc ON vc.solicitud_id = s.id
            JOIN campos c ON c.id = vc.campo_id
                AND c.name = 'id_integrante_2'
                AND c.tipo_solicitud_id = 2
            JOIN users u ON u.id = CAST(vc.valor AS UNSIGNED)
            WHERE s.tipo_solicitud_id = 5
              AND s.deleted_at IS NULL
 
        ) usr_int
 
        -- ── Nivel / Programa académico ───────────────────────────────────
        LEFT JOIN niveles niv ON niv.id = (
            SELECT CAST(vc_n.valor AS UNSIGNED)
            FROM valores_campos vc_n
            JOIN campos c_n ON c_n.id = vc_n.campo_id
            WHERE vc_n.solicitud_id = usr_int.solicitud_id
              AND c_n.name = 'nivel'
              AND c_n.tipo_solicitud_id = 2
            LIMIT 1
        )
 
        ORDER BY usr_int.name ASC
    """
 
    result = db.execute(text(query))
    return [dict(row._mapping) for row in result]


def get_beneficiarios_tyt_report(
    db,
    columns: List[Tuple[str, str]],
    estado: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
):
    """
    Reporte Beneficiarios TyT/PRO.
 
    Solo incluye los integrantes cuyos IDs están dentro del array JSON
    del campo EAV 'beneficiarios_icfes' (tipo_solicitud_id = 6).
 
    Cada integrante beneficiario genera su propia fila.
    Estado = nombre del tipo_solicitud de la solicitud fase_0 (tipo 2).
    """
 
    query = """
        SELECT
            niv.nombre                                                  AS programa,
 
            COALESCE(
                NULLIF(MAX(CASE WHEN c.name = 'titulo'  THEN vc.valor END), ''),
                s1.titulo_idea
            )                                                           AS titulo,
 
            CONCAT(
                tbl_mod.nombre,
                ' - ',
                MAX(CASE WHEN c.name = 'codigo_modalidad' THEN vc.valor END)
            )                                                           AS modalidad,
 
            usr_int.name                                                AS estudiante,
            usr_int.nro_documento                                       AS id_estudiante,
            tbl_dir.name                                                AS director,
            tbl_eva.name                                                AS evaluador,
            ts.nombre                                                   AS estado,
            NULL                                                        AS observaciones
 
        FROM solicitudes s
 
        -- ── Tipo solicitud para el estado ────────────────────────────────
        JOIN tipos_solicitudes ts ON ts.id = s.tipo_solicitud_id
 
        -- ── EAV principal ─────────────────────────────────────────────────
        LEFT JOIN valores_campos vc ON vc.solicitud_id = s.id
        LEFT JOIN campos c ON c.id = vc.campo_id
 
        -- ── Beneficiarios icfes: el campo JSON con los IDs ────────────────
        JOIN (
            SELECT vc_b.solicitud_id, vc_b.valor AS beneficiarios_json
            FROM valores_campos vc_b
            JOIN campos c_b ON c_b.id = vc_b.campo_id
                AND c_b.name = 'beneficiarios_icfes'
        ) bene ON bene.solicitud_id = s.id
 
        -- ── Integrantes que están en el JSON de beneficiarios ─────────────
        JOIN (
            SELECT s_u.id AS solicitud_id, u.id, u.name, u.nro_documento
            FROM solicitudes s_u
            JOIN valores_campos vc_u ON vc_u.solicitud_id = s_u.id
            JOIN campos c_u ON c_u.id = vc_u.campo_id
                AND c_u.name = 'id_integrante_1'
                AND c_u.tipo_solicitud_id = 2
            JOIN users u ON u.id = CAST(vc_u.valor AS UNSIGNED)
 
            UNION ALL
 
            SELECT s_u.id AS solicitud_id, u.id, u.name, u.nro_documento
            FROM solicitudes s_u
            JOIN valores_campos vc_u ON vc_u.solicitud_id = s_u.id
            JOIN campos c_u ON c_u.id = vc_u.campo_id
                AND c_u.name = 'id_integrante_2'
                AND c_u.tipo_solicitud_id = 2
            JOIN users u ON u.id = CAST(vc_u.valor AS UNSIGNED)
        ) usr_int
            ON usr_int.solicitud_id = s.id
            AND JSON_CONTAINS(bene.beneficiarios_json, CONCAT('"', usr_int.id, '"'))
 
        -- ── Nivel ────────────────────────────────────────────────────────
        LEFT JOIN niveles niv ON niv.id = (
            SELECT CAST(vc_n.valor AS UNSIGNED)
            FROM valores_campos vc_n
            JOIN campos c_n ON c_n.id = vc_n.campo_id
            WHERE vc_n.solicitud_id = s.id
              AND c_n.name = 'nivel'
              AND c_n.tipo_solicitud_id = 2
            LIMIT 1
        )
 
        -- ── Modalidad ────────────────────────────────────────────────────
        LEFT JOIN modalidades tbl_mod ON tbl_mod.id = (
            SELECT CAST(vc_m.valor AS UNSIGNED)
            FROM valores_campos vc_m
            JOIN campos c_m ON c_m.id = vc_m.campo_id
            WHERE vc_m.solicitud_id = s.id
              AND c_m.name = 'modalidad'
              AND c_m.tipo_solicitud_id = 2
            LIMIT 1
        )
 
        -- ── Director ─────────────────────────────────────────────────────
        LEFT JOIN users tbl_dir ON tbl_dir.id = (
            SELECT CAST(vc_d.valor AS UNSIGNED)
            FROM valores_campos vc_d
            JOIN campos c_d ON c_d.id = vc_d.campo_id
            WHERE vc_d.solicitud_id = s.id
              AND c_d.name = 'director_id'
              AND c_d.tipo_solicitud_id = 3
            LIMIT 1
        )
 
        -- ── Evaluador ────────────────────────────────────────────────────
        LEFT JOIN users tbl_eva ON tbl_eva.id = (
            SELECT CAST(vc_e.valor AS UNSIGNED)
            FROM valores_campos vc_e
            JOIN campos c_e ON c_e.id = vc_e.campo_id
            WHERE vc_e.solicitud_id = s.id
              AND c_e.name = 'evaluador_id'
              AND c_e.tipo_solicitud_id = 3
            LIMIT 1
        )
 
        -- ── Título desde tipo 1 via idea_banco ───────────────────────────
        LEFT JOIN (
            SELECT
                s1.id,
                MAX(CASE WHEN c1.name = 'titulo' THEN vc1.valor END) AS titulo_idea
            FROM solicitudes s1
            JOIN valores_campos vc1 ON vc1.solicitud_id = s1.id
            JOIN campos c1 ON c1.id = vc1.campo_id AND c1.tipo_solicitud_id = 1
            WHERE s1.tipo_solicitud_id = 1
              AND s1.deleted_at IS NULL
            GROUP BY s1.id
        ) s1 ON s1.id = (
            SELECT CAST(vc_idea.valor AS UNSIGNED)
            FROM valores_campos vc_idea
            JOIN campos c_idea ON c_idea.id = vc_idea.campo_id
            WHERE vc_idea.solicitud_id = s.id
              AND c_idea.name = 'idea_banco'
              AND c_idea.tipo_solicitud_id = 3
            LIMIT 1
        )
 
        WHERE s.deleted_at IS NULL
 
        GROUP BY
            usr_int.id,
            usr_int.name,
            usr_int.nro_documento,
            niv.nombre,
            tbl_mod.nombre,
            tbl_dir.name,
            tbl_eva.name,
            ts.nombre,
            s1.titulo_idea
 
        ORDER BY niv.nombre, usr_int.name ASC
    """
 
    result = db.execute(text(query))
    return [dict(row._mapping) for row in result]