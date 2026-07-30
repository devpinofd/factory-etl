# Reglas de Trabajo y Calidad de Datos - Factory ETL

## 🛑 Regla Fundamental: No Inventar ni Simular Datos (Strict Data Integrity)

1. **Prohibición de Datos Ficticios / Mocked**:
   - Queda estrictamente prohibido inventar o asumir datos ficticios (como RIFs genéricos `J-00000000-X`, razones sociales simuladas o valores inventados) cuando no hayan sido expresamente suministrados por el usuario o la base de datos.

2. **Protocolo Obligatorio de Verificación de Datos**:
   - **Paso 1 (Búsqueda en Repositorio y Base de Datos):** Antes de definir cualquier catálogo, tabla o parámetro de negocio, la primera acción debe ser buscar exhaustivamente la información real en el repositorio de código (`src/`, `dataform/`, `catalog.py`) o en el Data Lake de BigQuery.
   - **Paso 2 (Solicitud al Usuario):** Si la información requerida no existe en el repositorio ni en la base de datos, la conducta **ÚNICA Y OBLIGATORIA** es solicitarla explícitamente al usuario para que suministre los datos oficiales.

3. **Preservación de Calidad en BigQuery y Dataform**:
   - Las dimensiones y catálogos deben reflejar únicamente información verificada. Los campos cuyos datos no hayan sido suministrados deben permanecer como `NULL` o solicitarse al usuario antes de materializar.
