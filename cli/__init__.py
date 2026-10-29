"""
Herramientas de linea de comandos para diagnosticar un archivo sin abrir la interfaz.

Cada modulo es un comando independiente (Typer + Rich):

  colors.py   calibrar como se leen los colores de relleno de una TS
  ts.py       ver lo que QA2 extrae de una Traffic Sheet
  preview.py  ver lo que QA2 extrae de un export de Innovid
  match.py    ver como se emparejan TS e Innovid, antes de las reglas
  tags.py     revisar la estructura de un archivo de tags

No forman parte del flujo del equipo: son para quien mantiene QA2.
"""
