select  
    rap.documento,
    rap.renglon,
    rap.cod_art,
    rap.pre_ant,
    rap.pre_nue,
    rap.cos_ult1,
    rap.tip_pre,
    rap.notas,
    ajp.registro
from renglones_aprecios rap
join ajustes_precios ajp on ajp.documento = rap.documento
where ajp.status = 'Confirmado' and CAST(ajp.registro AS DATE) BETWEEN {{ fec_des }} AND {{ fec_has }}
