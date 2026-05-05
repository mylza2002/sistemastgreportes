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

            -- ── Actas ────────────────────────────────────────────────────
            acta_prop.numero                                                AS acta_aprobacion_propuesta,
            acta_prop.fecha                                                 AS fecha_aprobacion_acta,
            acta_final.numero                                               AS acta_aprobacion_final,
            acta_final.fecha                                                AS fecha_aprobacion_final,

            -- ── Campos pendientes de implementar ─────────────────────────
            NULL                                                            AS fecha_maxima,
            NULL                                                            AS fecha_minima,
            NULL                                                            AS acta_fecha_prorroga,
            NULL                                                            AS fecha_prorroga,
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

        -- ── Acta de propuesta (primera acta del proyecto) ─────────────────
        LEFT JOIN actas acta_prop ON acta_prop.id = (
            SELECT MIN(a.id)
            FROM actas a
            WHERE a.proyecto_id = s.id
              AND a.deleted_at IS NULL
        )

        -- ── Acta final (última acta del proyecto) ─────────────────────────
        LEFT JOIN actas acta_final ON acta_final.id = (
            SELECT MAX(a.id)
            FROM actas a
            WHERE a.proyecto_id = s.id
              AND a.deleted_at IS NULL
              AND a.id != acta_prop.id
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
            acta_prop.numero, acta_prop.fecha,
            acta_final.numero, acta_final.fecha

        ORDER BY s.created_at DESC
    """

    result = db.execute(text(query), params)
    return [dict(row._mapping) for row in result]