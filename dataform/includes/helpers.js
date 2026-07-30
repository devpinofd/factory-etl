/**
 * Helpers JS reusables para Dataform en Factory ETL
 */

// Limpieza de espacios a izquierda y derecha
function trimStr(columnName) {
  return `RTRIM(LTRIM(CAST(${columnName} AS STRING)))`;
}

// Casteo seguro a TIMESTAMP (.NET eFactory de 7 decimales de subsegundo)
function toTimestamp(columnName) {
  return `COALESCE(PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S', ${columnName}), SAFE_CAST(${columnName} AS TIMESTAMP))`;
}

// Casteo seguro a DATE
function toDate(columnName) {
  return `SAFE_CAST(${columnName} AS DATE)`;
}

// Casteo seguro a NUMERIC (28,10)
function toNumeric(columnName) {
  return `SAFE_CAST(${columnName} AS NUMERIC)`;
}

module.exports = {
  trimStr,
  toTimestamp,
  toDate,
  toNumeric
};
