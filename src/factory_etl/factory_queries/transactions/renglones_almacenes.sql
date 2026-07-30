select ra.cod_alm, ra.cod_art, ra.exi_act1, ra.registro from renglones_almacenes ra where CAST(ra.registro AS DATE) BETWEEN {{ fec_des }} AND {{ fec_has }}
