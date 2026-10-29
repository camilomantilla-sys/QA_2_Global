"""
Motor de QA2: todo lo que no es interfaz ni lectura de archivos.

Recorrido de una corrida, y el modulo que se encarga de cada paso:

  1. Leer         parsers/            (TS, exports de Innovid, tags, DV)
  2. Emparejar    matching.py         TS contra Innovid, placement por placement
  3. Conciliar    *_reconciliation.py cruces especificos (pixeles, DV, Adobe, Innovid API)
  4. Evaluar      engine.run_rules()  llama a cada regla de rules/
  5. Hallazgos    findings.py         FindingsBuffer: PASS / FAIL / REVIEW / NOT_VERIFIED
  6. Veredicto    verdict.py          Implementation vs Tags & pixels; manda el peor
  7. Entregar     excel_report.py, pdf_report.py, qa_export.py

Seguridad: en tiempo de ejecucion, innovid_api.py e innovid_login.py son los unicos modulos que
salen de la maquina, y solo hacia Innovid/Flashtalking. paths.py fija
que las credenciales nunca se puedan mover a una carpeta compartida.
"""
