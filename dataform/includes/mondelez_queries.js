function grupos() {
  return `SELECT 'tinito' AS source_empresa, '02' AS cod_suc,
  '100123571' AS codigo_grupo, 'CCIAL TINITO EL TIGRE, VLPC' AS nombre_grupo,
  'CENTRO' AS region
UNION ALL
SELECT 'ctb', '01', '100216067', 'COMERCIAL TINITO BARCELONA MESONES', 'ORIENTE'
UNION ALL
SELECT 'ctb', '02', '100216067', 'COMERCIAL TINITO BARCELONA MESONES', 'ORIENTE'
UNION ALL
SELECT 'tinito', '01', '100596186', 'CCIAL TINITO EL TIGRE, APURE', 'CENTRO'
UNION ALL
SELECT 'tinito', '04', '100676254', 'CCIAL TINITO EL TIGRE, BOLIVAR', 'ORIENTE'
UNION ALL
SELECT 'tinito', '06', '101068889', 'COMERCIAL TINITO ARAGUA', 'CENTRO'
UNION ALL
SELECT 'ctm', '01', '156143416', 'COMERCIAL TINITO C.A', 'ORIENTE'
UNION ALL
SELECT 'ctm', '02', '156143416', 'COMERCIAL TINITO C.A', 'ORIENTE'
UNION ALL
SELECT 'tinito', '03', '156180907', 'COMERCIAL TINITO EL TIGRE C.A', 'ORIENTE'
UNION ALL
SELECT 'ctb', '06', '300004760', 'COMERCIAL TINITO CARACAS', 'CENTRO'`;
}

function clientes(ref, gruposSource = ref("vw_mondelez_grupos")) {
  return `SELECT
  c.source_empresa,
  c.cod_cli AS _cod_cli,
  TRIM(LEFT(g.codigo_grupo, 20), ' ') AS CODIGO_GRUPO,
  TRIM(LEFT(REPLACE(REPLACE(COALESCE(c.rif, ''), '.', ''), '-', ''), 10), ' ') AS RIF,
  TRIM(LEFT(c.nom_cli, 40), ' ') AS SOCIO_NEGOCIO,
  TRIM(LEFT(COALESCE(p.nom_pai, ''), 20), ' ') AS PAIS,
  TRIM(LEFT(COALESCE(e.nom_est, ''), 20), ' ') AS ESTADO,
  TRIM(LEFT(COALESCE(c.nom_mun, ''), 20), ' ') AS MUNICIPIO,
  TRIM(LEFT(COALESCE(ci.nom_ciu, ''), 20), ' ') AS CIUDAD,
  TRIM(LEFT(COALESCE(c.dir_fis, ''), 50), ' ') AS DIRECCION,
  TRIM(LEFT(COALESCE(c.gps, ''), 40), ' ') AS GPS,
  'SI' AS DIRECCION_FISCAL,
  TRIM(LEFT(COALESCE(c.segmentacion2, ''), 20), ' ') AS CANAL_VENTAS,
  TRIM(LEFT(COALESCE(UPPER(c.cod_ven), ''), 20), ' ') AS RUTA,
  TRIM(LEFT(COALESCE(c.segmentacion2, ''), 20), ' ') AS CLASIFICACION_NEGOCIO,
  CASE UPPER(c.status)
    WHEN 'A' THEN '1'
    WHEN 'I' THEN '0'
    WHEN 'S' THEN '0'
    ELSE ERROR(CONCAT('Estatus de cliente no soportado: ', COALESCE(c.status, 'NULL')))
  END AS ESTATUS,
  TRIM(LEFT(COALESCE(UPPER(c.cod_ven), ''), 10), ' ') AS CODIGO_VENDEDOR,
  TRIM(LEFT(COALESCE(ven.nom_ven, ''), 20), ' ') AS NOMBRE_VENDEDOR,
  TRIM(LEFT(COALESCE(c.nom_par, ''), 20), ' ') AS PARROQUA
FROM ${ref("dim_cliente")} c
INNER JOIN ${gruposSource} g
  ON c.source_empresa = g.source_empresa AND c.cod_suc = g.cod_suc
LEFT JOIN ${ref("dim_pais")} p
  ON c.source_empresa = p.source_empresa AND c.cod_pai = p.cod_pai
LEFT JOIN ${ref("dim_estado")} e
  ON c.source_empresa = e.source_empresa AND c.cod_est = e.cod_est
LEFT JOIN ${ref("dim_ciudad")} ci
  ON c.source_empresa = ci.source_empresa AND c.cod_ciu = ci.cod_ciu
LEFT JOIN (
  SELECT
    source_empresa,
    UPPER(cod_ven) AS cod_ven,
    IF(COUNT(*) = 1, ANY_VALUE(nom_ven),
      ERROR(CONCAT('Codigo de vendedor ambiguo al normalizar: ', source_empresa))) AS nom_ven
  FROM ${ref("dim_vendedor")}
  GROUP BY 1, 2
) ven
  ON c.source_empresa = ven.source_empresa AND UPPER(c.cod_ven) = ven.cod_ven`;
}

function ventas(ref, gruposSource = ref("vw_mondelez_grupos")) {
  return `WITH ventas AS (
  SELECT
    v.*,
    ROUND(
      ABS(SAFE_DIVIDE(CAST(v.monto_bruto AS NUMERIC), CAST(v.unidades_vendidas AS NUMERIC)))
        * (1 - CAST(v.dcto AS NUMERIC) / 100),
      2
    ) AS precio_unitario
  FROM ${ref("fct_ventas_gold")} v
  WHERE v.source_empresa IN ('ctb', 'tinito', 'ctm')
    AND v.cod_pro = '0301'
    AND DATE(v.registro) >= DATE '2025-01-01'
)
SELECT
  v.source_empresa,
  TO_HEX(SHA256(TO_JSON_STRING(STRUCT(
    v.source_empresa, v.tipo_documento, v.cod_suc, v.documento, v.renglon
  )))) AS ID_LINEA,
  DATE(v.registro) AS _fecha,
  v.renglon AS _renglon,
  v.cod_cli AS _cod_cli,
  g.codigo_grupo AS CODIGO_GRUPO,
  g.nombre_grupo AS NOMBRE_GRUPO,
  TRIM(LEFT(COALESCE(UPPER(v.cod_ven), ''), 20), ' ') AS RUTA,
  TRIM(LEFT(REPLACE(REPLACE(COALESCE(c.rif, ''), '.', ''), '-', ''), 10), ' ') AS RIF,
  TRIM(LEFT(c.nom_cli, 40), ' ') AS SOCIO_NEGOCIO,
  TRIM(LEFT(COALESCE(p.nom_pai, ''), 20), ' ') AS PAIS,
  TRIM(LEFT(COALESCE(e.nom_est, ''), 20), ' ') AS ESTADO,
  TRIM(LEFT(COALESCE(c.nom_mun, ''), 20), ' ') AS MUNICIPIO,
  TRIM(LEFT(COALESCE(ci.nom_ciu, ''), 20), ' ') AS CIUDAD,
  TRIM(LEFT(COALESCE(c.dir_fis, ''), 50), ' ') AS DIRECCION,
  TRIM(LEFT(v.cod_art, 20), ' ') AS CODIGO_SKU,
  TRIM(LEFT(COALESCE(a.modelo, ''), 13), ' ') AS CODIGO_BARRA,
  TRIM(LEFT(COALESCE(a.cod_uni1, ''), 20), ' ') AS UNIDAD_MEDIDA,
  FORMAT_DATE('%Y%m%d', DATE(v.registro)) AS FECHA,
  TRIM(LEFT(v.documento, 10), ' ') AS NUMERO_DOCUMENTO,
  CASE UPPER(v.tipo_documento)
    WHEN 'FACTURA' THEN 'FACTURA'
    WHEN 'DEVOLUCION' THEN 'N/CR'
    ELSE ERROR(CONCAT('Tipo documental no soportado: ', COALESCE(v.tipo_documento, 'NULL')))
  END AS TIPO_DOCUMENTO,
  TRIM(LEFT(COALESCE(a.nom_art, ''), 40), ' ') AS NOMBRE_SKU,
  TRIM(LEFT(COALESCE(pro.nom_pro, ''), 20), ' ') AS PROVEEDOR,
  TRIM(LEFT(COALESCE(c.segmentacion2, ''), 30), ' ') AS CANAL_VENTA,
  IF(v.unidades_vendidas IS NULL,
    ERROR('Cantidad nula en ventas Mondelez'),
    FORMAT('%.2f', ABS(CAST(v.unidades_vendidas AS NUMERIC)))) AS CANTIDAD,
  IF(v.precio_unitario IS NULL,
    ERROR('Cantidad cero o importe/descuento nulo en ventas Mondelez'),
    FORMAT('%.2f', v.precio_unitario)) AS PRECIO,
  v.cod_mon AS MONEDA,
  FORMAT('%.2f', ROUND(v.precio_unitario * ABS(CAST(v.unidades_vendidas AS NUMERIC)), 2)) AS NETO_MONEDA,
  FORMAT_TIMESTAMP('%Y%m%d%H%M%S', v.registro, 'America/Caracas') AS FECHA_ACTUALIZACION
FROM ventas v
INNER JOIN ${gruposSource} g
  ON v.source_empresa = g.source_empresa AND v.cod_suc = g.cod_suc
INNER JOIN ${ref("dim_cliente")} c
  ON c.source_empresa = v.source_empresa AND c.cod_cli = v.cod_cli
LEFT JOIN ${ref("dim_pais")} p
  ON c.source_empresa = p.source_empresa AND c.cod_pai = p.cod_pai
LEFT JOIN ${ref("dim_estado")} e
  ON c.source_empresa = e.source_empresa AND c.cod_est = e.cod_est
LEFT JOIN ${ref("dim_ciudad")} ci
  ON c.source_empresa = ci.source_empresa AND c.cod_ciu = ci.cod_ciu
LEFT JOIN ${ref("dim_articulo")} a
  ON v.source_empresa = a.source_empresa AND v.cod_art = a.cod_art
LEFT JOIN ${ref("dim_proveedor")} pro
  ON v.source_empresa = pro.source_empresa AND v.cod_pro = pro.cod_pro`;
}

function existenciasCandidata(ref, gruposSource = ref("vw_mondelez_grupos")) {
  return `WITH inventario AS (
  SELECT source_empresa, snapshot_date AS dia_venezuela, run_id,
    _ingested_at AS captura, cod_alm, cod_art, unidades_disponibles
  FROM ${ref("fct_inventario_snapshot")}
  WHERE source_empresa IN ('ctb', 'ctm', 'tinito')
),
articulos AS (
  SELECT source_empresa, cod_art,
    IF(COUNT(*) = 1, ANY_VALUE(cod_pro),
      ERROR(CONCAT('Maestro de articulo ambiguo: ', source_empresa, '/', cod_art))) AS cod_pro,
    ANY_VALUE(nom_art) AS nom_art, ANY_VALUE(modelo) AS modelo,
    ANY_VALUE(fraccion) AS fraccion
  FROM ${ref("dim_articulo")}
  GROUP BY 1, 2
),
almacenes AS (
  SELECT source_empresa, cod_alm,
    IF(COUNT(*) = 1, ANY_VALUE(cod_suc),
      ERROR(CONCAT('Maestro de almacen ambiguo: ', source_empresa, '/', cod_alm))) AS cod_suc
  FROM ${ref("dim_almacen")}
  GROUP BY 1, 2
)
SELECT
  i.source_empresa,
  i.dia_venezuela AS FECHA_SNAPSHOT,
  i.run_id AS _capture_id,
  i.captura AS _captured_at,
  g.codigo_grupo AS CODIGO_GRUPO,
  g.nombre_grupo AS NOMBRE_GRUPO,
  i.cod_art AS _cod_art,
  TRIM(LEFT(i.cod_art, 20), ' ') AS CODIGO_SKU,
  IF(a.nom_art IS NOT NULL, TRIM(LEFT(a.nom_art, 40), ' '),
    ERROR(CONCAT('Descripcion de articulo nula: ', i.source_empresa, '/', i.cod_art))) AS DESCRIPCION_SKU,
  TRIM(LEFT(COALESCE(a.modelo, ''), 13), ' ') AS CODIGO_BARRA,
  SUM(i.unidades_disponibles) AS DISPONIBLE,
  'UNI' AS TIPO_UNIDADES,
  IF(a.fraccion >= 0, a.fraccion,
    ERROR(CONCAT('Fraccion nula o negativa: ', i.source_empresa, '/', i.cod_art))) AS UNIDAD_SIMPLE_X_EMPAQUE,
  FORMAT_TIMESTAMP('%Y%m%d%H%M%S', i.captura, 'America/Caracas') AS FECHA_DATA
FROM inventario i
LEFT JOIN articulos a
  ON i.source_empresa = a.source_empresa AND i.cod_art = a.cod_art
LEFT JOIN almacenes alm
  ON i.source_empresa = alm.source_empresa AND i.cod_alm = alm.cod_alm
LEFT JOIN ${gruposSource} g
  ON alm.source_empresa = g.source_empresa AND alm.cod_suc = g.cod_suc
WHERE CASE
  WHEN UPPER(TRIM(i.cod_alm)) = 'TRANSITO' THEN FALSE
  WHEN a.cod_art IS NULL THEN
    ERROR(CONCAT('Maestro de articulo faltante: ', i.source_empresa, '/', i.cod_art))
  WHEN a.cod_pro IS DISTINCT FROM '0301' THEN FALSE
  WHEN alm.cod_alm IS NULL THEN
    ERROR(CONCAT('Maestro de almacen faltante: ', i.source_empresa, '/', i.cod_alm))
  ELSE g.codigo_grupo IS NOT NULL
END
GROUP BY i.source_empresa, i.dia_venezuela, i.run_id, i.captura,
  g.codigo_grupo, g.nombre_grupo, i.cod_art, a.nom_art, a.modelo, a.fraccion`;
}

function existencias(ref, candidataSource = ref("vw_mondelez_existencias_candidata")) {
  return `WITH candidata AS (
  SELECT *,
    COUNT(*) OVER (
      PARTITION BY source_empresa, FECHA_SNAPSHOT, CODIGO_GRUPO, CODIGO_SKU
    ) AS claves_publicas
  FROM ${candidataSource}
)
SELECT
  * EXCEPT (FECHA_DATA, claves_publicas, _cod_art)
  REPLACE (
    IF(claves_publicas = 1 AND CODIGO_SKU IS NOT NULL
      AND DISPONIBLE IS NOT NULL AND ABS(DISPONIBLE) < 10000000000
      AND DISPONIBLE * 100 = TRUNC(DISPONIBLE * 100),
      DISPONIBLE, ERROR('Contrato inventario invalido: cantidad o clave publica')) AS DISPONIBLE,
    IF(UNIDAD_SIMPLE_X_EMPAQUE IS NOT NULL AND UNIDAD_SIMPLE_X_EMPAQUE >= 0
      AND UNIDAD_SIMPLE_X_EMPAQUE < 10000000000
      AND UNIDAD_SIMPLE_X_EMPAQUE * 100 = TRUNC(UNIDAD_SIMPLE_X_EMPAQUE * 100),
      UNIDAD_SIMPLE_X_EMPAQUE, ERROR('Contrato inventario invalido: empaque')) AS UNIDAD_SIMPLE_X_EMPAQUE
  ),
  FORMAT_TIMESTAMP('%Y%m%d%H%M%S', _captured_at, 'America/Caracas') AS FECHA_DATA
FROM candidata`;
}

function articulosEnriquecidos(ref) {
  return `SELECT
  a.*,
  c.modelo AS modelo_canonico,
  c.descripcion AS descripcion_canonica,
  c.clase_producto AS clase_producto_canonica,
  c.marca AS marca_canonica,
  c.peso_caja_kg AS peso_caja_kg_canonico,
  c.peso_unidad_kg AS peso_unidad_kg_canonico,
  c.unidades_por_empaque AS unidades_por_empaque_canonicas,
  c._source_sha256 AS _canonico_source_sha256,
  IF(c.modelo IS NULL, 'SIN_CORRESPONDENCIA', 'COINCIDENCIA_EXACTA') AS estado_correspondencia
FROM ${ref("dim_articulo")} AS a
LEFT JOIN ${ref("dim_mondelez_producto_canonico")} AS c
  ON TRIM(a.modelo) = c.modelo
WHERE a.source_empresa IN ('ctb', 'ctm', 'tinito')
  AND a.cod_pro = '0301'`;
}

module.exports = {
  grupos,
  clientes,
  ventas,
  existenciasCandidata,
  existencias,
  articulosEnriquecidos
};
