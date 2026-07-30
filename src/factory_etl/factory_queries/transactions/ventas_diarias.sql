(SELECT  'Factura'                                                                    AS Tipo_Documento,
          Facturas.Cod_Suc                                                            AS Cod_Suc,
          Facturas.Documento                                                          AS Documento,
          Renglones_Facturas.Renglon                                                  AS Renglon,
          Facturas.Fec_Reg                                                            AS Registro,
          Facturas.Cod_Ven                                                            AS Cod_Ven,
          Vendedores.Nom_Ven                                                          AS Nom_Ven,
          Facturas.Cod_Cli                                                            AS Cod_Cli,
          Clientes.Nom_Cli                                                            AS Nom_Cli,
          Clases_Clientes.Nom_Cla                                                     AS Nom_Cla,
          Estados.Nom_Est                                                             AS Nom_Est,
          Ciudades.Nom_Ciu                                                            AS Nom_Ciu,
          Renglones_Facturas.Cod_Art                                                  AS Cod_Art,
          Marcas.Cod_Mar                                                              AS Cod_Mar,
          Marcas.Nom_Mar                                                              AS Nom_Mar,
          Departamentos.Nom_Dep                                                       AS Nom_Dep,
          Articulos.Cod_Sec                                                           AS Cod_Sec,
          Articulos.Modelo                                                            AS Modelo,
          Articulos.Cod_Pro                                                           AS Cod_Pro,
          Proveedores.Nom_Pro                                                         AS Nom_Pro,
          Articulos.Nom_Art                                                           AS Nom_Art,
          Articulos.Cod_Uni1                                                          AS Cod_Uni1,
          Renglones_Facturas.Can_Art1                                                 AS Can_Ven,
          Renglones_Facturas.Mon_Bru                                                  AS Monto_Bruto,
          Facturas.cod_mon                                                            AS Cod_Mon,
          Clientes.rif                                                                AS Rif,
          Renglones_Facturas.cod_imp                                                  AS Cod_Imp,
         CAST((Renglones_Facturas.mon_net + Renglones_Facturas.mon_imp1) * Facturas.tasa  AS DECIMAL (8,2) ) AS Neto,
          CAST(Facturas.por_des1  AS DECIMAL (8,2))                                                         AS Dcto,
          CAST(1 / Facturas.tasa AS DECIMAL(8,2))                                    AS Tasa,
          CAST(((Renglones_Facturas.mon_net + Renglones_Facturas.mon_imp1) * Facturas.tasa) * (1 - Facturas.por_des1 / 100) AS DECIMAL (8,2)) AS Neto_Dcto
  FROM    Renglones_Facturas
      JOIN Facturas ON Facturas.Documento = Renglones_Facturas.Documento
      JOIN Articulos ON Articulos.Cod_Art = Renglones_Facturas.Cod_Art
      JOIN Marcas ON Marcas.Cod_Mar = Articulos.Cod_Mar
      JOIN Clientes ON Clientes.Cod_Cli = Facturas.Cod_Cli
      JOIN Vendedores ON Vendedores.Cod_Ven = Facturas.Cod_Ven
      JOIN Estados ON Estados.Cod_Est = Clientes.Cod_Est
      JOIN Ciudades ON Ciudades.Cod_Ciu = Clientes.Cod_Ciu
      JOIN Departamentos ON Departamentos.Cod_Dep = Articulos.Cod_Dep
      JOIN Secciones ON Secciones.Cod_Sec = Articulos.Cod_Sec AND Secciones.Cod_Dep = Articulos.Cod_Dep
      JOIN Clases_Clientes ON Clases_Clientes.Cod_Cla = Clientes.Cod_Cla
      JOIN Proveedores ON Proveedores.Cod_Pro = Articulos.Cod_Pro
  WHERE   Facturas.Status IN ('Confirmado', 'Afectado', 'Procesado')
      AND CAST(Facturas.Fec_Reg AS DATE) BETWEEN {{ fec_des }} AND {{ fec_has }})

 UNION ALL

 ( SELECT 'Devolucion'                                                                                    AS Tipo_Documento, 
          Devoluciones_Clientes.Cod_Suc                                                                   AS Cod_Suc,
          Devoluciones_Clientes.Documento                                                                 AS Documento,
          Renglones_DClientes.Renglon                                                                     AS Renglon,
          Devoluciones_Clientes.Fec_Reg                                                                   AS Registro,
          Devoluciones_Clientes.Cod_Ven                                                                   AS Cod_Ven,
          Vendedores.Nom_Ven                                                                              AS Nom_Ven,
          Devoluciones_Clientes.Cod_Cli                                                                   AS Cod_Cli,
          Clientes.Nom_Cli                                                                                AS Nom_Cli,
          Clases_Clientes.Nom_Cla                                                                         AS Nom_Cla,
          Estados.Nom_Est                                                                                 AS Nom_Est,
          Ciudades.Nom_Ciu                                                                                AS Nom_Ciu,
          Renglones_DClientes.Cod_Art                                                                     AS Cod_Art,
          Marcas.Cod_Mar                                                                                  AS Cod_Mar,
          Marcas.Nom_Mar                                                                                  AS Nom_Mar,
          Departamentos.Nom_Dep                                                                           AS Nom_Dep,
          Articulos.Cod_Sec                                                                               AS Cod_Sec,
          Articulos.Modelo                                                                                AS Modelo,
          Articulos.Cod_Pro                                                                               AS Cod_Pro,
          Proveedores.Nom_Pro                                                                             AS Nom_Pro,
          Articulos.Nom_Art                                                                               AS Nom_Art,
          Articulos.Cod_Uni1                                                                              AS Cod_Uni1,
          Renglones_DClientes.Can_Art1 * (-1)                                                             AS Can_Ven,
          Renglones_DClientes.Mon_Bru * (-1)                                                              AS Monto_Bruto,
          Devoluciones_Clientes.cod_mon                                                                   AS Cod_Mon,
          Clientes.rif                                                                                    AS Rif,
          Renglones_DClientes.cod_imp                                                                     AS Cod_Imp,
          CAST((Renglones_DClientes.mon_net + Renglones_DClientes.mon_imp1) * Devoluciones_Clientes.tasa * (-1) AS DECIMAL (8,2)) AS Neto,
          CAST (Devoluciones_Clientes.por_des1  AS DECIMAL (8,2))                                        AS Dcto,
          CAST(1 / Devoluciones_Clientes.tasa AS DECIMAL(8,2))                                            AS Tasa,
          CAST( ((Renglones_DClientes.mon_net + Renglones_DClientes.mon_imp1) * Devoluciones_Clientes.tasa) * (1 - Devoluciones_Clientes.por_des1 / 100) * (-1) AS DECIMAL (8,2)) AS Neto_Dcto
  FROM    Renglones_DClientes
      JOIN Devoluciones_Clientes ON Devoluciones_Clientes.Documento = Renglones_DClientes.Documento
      JOIN Articulos On Articulos.Cod_Art = Renglones_DClientes.Cod_Art
      JOIN Marcas On Marcas.Cod_Mar = Articulos.Cod_Mar
      JOIN Clientes On Clientes.Cod_Cli = Devoluciones_Clientes.Cod_Cli
      JOIN Vendedores On Vendedores.Cod_Ven = Devoluciones_Clientes.Cod_Ven
      JOIN Estados On Estados.Cod_Est = Clientes.Cod_Est
      JOIN Ciudades On Ciudades.Cod_Ciu = Clientes.Cod_Ciu
      JOIN Departamentos On Departamentos.Cod_Dep = Articulos.Cod_Dep
      JOIN Secciones On Secciones.Cod_Sec = Articulos.Cod_Sec And Secciones.Cod_Dep = Articulos.Cod_Dep
      JOIN Clases_Clientes On Clases_Clientes.Cod_Cla = Clientes.Cod_Cla
      JOIN Proveedores On Proveedores.Cod_Pro = Articulos.Cod_Pro
  WHERE   Devoluciones_Clientes.Status In ('Confirmado', 'Afectado', 'Procesado')
      AND CAST(Devoluciones_Clientes.Fec_Reg AS DATE) BETWEEN {{ fec_des }} AND {{ fec_has }}
     )
 ORDER BY 5
