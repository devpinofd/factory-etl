select cli.cod_cli,
 cli.nom_cli, cli.rif, 
 cli.dir_fis, cli.dir_exa, 
 cli.cod_pai, cli.cod_est,
  cli.cod_ciu, cli.dir_otr as nom_mun, 
  cli.caracter1 as nom_par, cli.web as gps, cli.cod_ven, cli.cod_cla as segmentacion1, cli.atributo_a as segmentacion2, cli.mon_sal, cli.cod_suc, cli.tip_con, cli.crm_pos, cli.tip_cli, cli.abc, cli.status from clientes cli
