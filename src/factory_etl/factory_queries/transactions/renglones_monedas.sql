select rm.cod_mon, rm.renglon, rm.fecha, rm.tasa, rm.comentario, rm.registro from renglones_monedas rm where CAST(rm.registro AS DATE) BETWEEN {{ fec_des }} AND {{ fec_has }}
