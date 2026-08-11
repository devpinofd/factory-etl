(SELECT
  'Factura' AS Tipo_Documento,
  Facturas.Cod_Suc AS Cod_Suc,
  Facturas.Documento AS Documento,
  Renglones_Facturas.Renglon AS Renglon,
  Facturas.Fec_Reg AS Registro,
  Facturas.Cod_Ven AS Cod_Ven,
  Facturas.Cod_Cli AS Cod_Cli,
  Renglones_Facturas.Cod_Art AS Cod_Art,
  Renglones_Facturas.Cod_Alm AS Cod_Alm,
  Renglones_Facturas.Can_Art1 AS Can_Ven,
  Renglones_Facturas.Mon_Bru AS Monto_Bruto,
  Facturas.cod_mon AS Cod_Mon,
  Renglones_Facturas.cod_imp AS Cod_Imp,
  Renglones_Facturas.por_imp1 AS Por_Imp1,
  CAST((Renglones_Facturas.mon_net + Renglones_Facturas.mon_imp1) * Facturas.tasa AS DECIMAL (8,2)) AS Neto,
  CAST(Facturas.por_des1 AS DECIMAL (8,2)) AS Dcto,
  CAST(1 / Facturas.tasa AS DECIMAL(8,2)) AS Tasa,
  CAST(((Renglones_Facturas.mon_net + Renglones_Facturas.mon_imp1) * Facturas.tasa) * (1 - Facturas.por_des1 / 100) AS DECIMAL (8,2)) AS Neto_Dcto
FROM Renglones_Facturas
JOIN Facturas ON Facturas.Documento = Renglones_Facturas.Documento
WHERE Facturas.Status IN ('Confirmado', 'Afectado', 'Procesado')
  AND CAST(Facturas.Fec_Reg AS DATE) BETWEEN {{ fec_des }} AND {{ fec_has }})

UNION ALL

(SELECT
  'Devolucion' AS Tipo_Documento,
  Devoluciones_Clientes.Cod_Suc AS Cod_Suc,
  Devoluciones_Clientes.Documento AS Documento,
  Renglones_DClientes.Renglon AS Renglon,
  Devoluciones_Clientes.Fec_Reg AS Registro,
  Devoluciones_Clientes.Cod_Ven AS Cod_Ven,
  Devoluciones_Clientes.Cod_Cli AS Cod_Cli,
  Renglones_DClientes.Cod_Art AS Cod_Art,
  Renglones_DClientes.Cod_Alm AS Cod_Alm,
  Renglones_DClientes.Can_Art1 * (-1) AS Can_Ven,
  Renglones_DClientes.Mon_Bru * (-1) AS Monto_Bruto,
  Devoluciones_Clientes.cod_mon AS Cod_Mon,
  Renglones_DClientes.cod_imp AS Cod_Imp,
  Renglones_DClientes.por_imp1 AS Por_Imp1,
  CAST((Renglones_DClientes.mon_net + Renglones_DClientes.mon_imp1) * Devoluciones_Clientes.tasa * (-1) AS DECIMAL (8,2)) AS Neto,
  CAST(Devoluciones_Clientes.por_des1 AS DECIMAL (8,2)) AS Dcto,
  CAST(1 / Devoluciones_Clientes.tasa AS DECIMAL(8,2)) AS Tasa,
  CAST(((Renglones_DClientes.mon_net + Renglones_DClientes.mon_imp1) * Devoluciones_Clientes.tasa) * (1 - Devoluciones_Clientes.por_des1 / 100) * (-1) AS DECIMAL (8,2)) AS Neto_Dcto
FROM Renglones_DClientes
JOIN Devoluciones_Clientes ON Devoluciones_Clientes.Documento = Renglones_DClientes.Documento
WHERE Devoluciones_Clientes.Status IN ('Confirmado', 'Afectado', 'Procesado')
  AND CAST(Devoluciones_Clientes.Fec_Reg AS DATE) BETWEEN {{ fec_des }} AND {{ fec_has }})
