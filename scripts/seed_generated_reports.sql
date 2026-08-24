-- Seed script for local/staging validation of DB-first email queue behavior.
-- Inserts one generated weekly report, one generated monthly report, and one generated trimestral report.

INSERT INTO reports_sent (
    alert_type,
    report_title,
    report_url,
    report_date,
    status,
    metadata
) VALUES (
    'weekly_alerts',
    'Alertas GFW - Semana 2026-06-01 a 2026-06-07',
    'gs://reportes-simbyp/reportes_gfw/semana_2026-06-01_a_2026-06-07/reporte_final.html',
    DATE '2026-06-07',
    'generated',
    jsonb_build_object(
        'start_date', '2026-06-01',
        'end_date', '2026-06-07',
        'files', jsonb_build_array(
            jsonb_build_object('name', 'Reporte Final', 'url', 'gs://reportes-simbyp/reportes_gfw/semana_2026-06-01_a_2026-06-07/reporte_final.html'),
            jsonb_build_object('name', 'Datos JSON', 'path', 'data_final.json'),
            jsonb_build_object('name', 'GeoJSON', 'path', 'output.geojson')
        )
    )
), (
    'monthly_built_area',
    'Reporte Mensual de Área Construida - Mayo 2026',
    'gs://reportes-simbyp/urban_sprawl/urban_sprawl_reporte_2026_Mayo.html',
    DATE '2026-05-31',
    'generated',
    jsonb_build_object(
        'top_upls', jsonb_build_array(),
        'files', jsonb_build_array(
            jsonb_build_object('name', 'Reporte Mensual', 'url', 'gs://reportes-simbyp/urban_sprawl/urban_sprawl_reporte_2026_Mayo.html'),
            jsonb_build_object('name', 'Resumen UPL', 'path', 'urban_sprawl_reporte.json')
        )
    )
), (
    'trimestral_alerts',
    'Alertas GFW - Trimestre 2026-Q2',
    'gs://reportes-simbyp/reportes_gfw/trimestre_2026_q2/reporte_final.html',
    DATE '2026-06-30',
    'generated',
    jsonb_build_object(
        'start_date', '2026-04-01',
        'end_date', '2026-06-30',
        'map_url', 'gs://reportes-simbyp/reportes_gfw/trimestre_2026_q2/mapa_interactivo.html',
        'files', jsonb_build_array(
            jsonb_build_object('name', 'Reporte Trimestral', 'url', 'gs://reportes-simbyp/reportes_gfw/trimestre_2026_q2/reporte_final.html'),
            jsonb_build_object('name', 'Resumen CSV', 'path', 'resumen_q2.csv')
        )
    )
);
