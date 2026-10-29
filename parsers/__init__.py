"""
Lectura de los archivos que sube el analista.

  ts_parser.py       Traffic Sheet: placements, creativos y la intencion
                     de cada celda segun su color de relleno
  innovid_export.py  exports Placement-Creative View y Placement View
  innovid_tags.py    archivos de tags que se entregan al publisher
  dv_tags.py         exports de tags de DoubleVerify Pinnacle

Los parsers solo leen y normalizan: no deciden si algo esta bien o mal.
Eso es trabajo de core/ y rules/. Nada de lo que leen se guarda en disco
ni sale de la maquina.
"""
