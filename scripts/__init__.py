"""
Scripts de soporte: arranque, empaquetado y diagnosticos.

Los que importan para operar QA2:

  start_qa2.py       arranca la app (lo llaman los .bat)
  build_bundle.py    arma el paquete completo para el equipo
  package_release.py arma el parche de actualizacion

El resto (diagnose_*, run_*, reconcile_*, regression_*) son herramientas
de desarrollo que se corren a mano contra casos locales; necesitan
archivos de cliente que no viven en el repositorio.
"""
