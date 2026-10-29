"""
Las reglas de QA2, una familia por archivo.

Cada modulo expone evaluate(...), que recibe datos ya emparejados o
conciliados y escribe hallazgos en un FindingsBuffer (core/findings.py).
Las reglas no leen archivos ni llaman a la red: son funciones
deterministas, el mismo insumo da siempre el mismo resultado.

Quien las llama y en que orden: core/engine.py, run_rules().
Catalogo completo de IDs (PLC-, CRE-, URL-, TAG-, PIX-, DV-, ...):
docs/GUIA_TECNICA.md, seccion 4.
"""
