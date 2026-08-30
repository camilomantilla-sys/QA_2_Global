from pathlib import Path

path = Path("ui/app_v2.py")
text = path.read_text(encoding="utf-8")

# ============================================================
# 1. Insertar normalización flexible de sites
# ============================================================

anchor = """
def clean_value(value) -> str:
"""

site_helpers = r'''
_SITE_ID_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")
_SITE_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)

_GENERIC_SITE_WORDS = {
    "site",
    "media",
    "network",
    "networks",
    "group",
    "digital",
    "online",
    "inc",
    "llc",
    "ltd",
    "com",
}


def normalize_site(value) -> str:
    """
    Normaliza sites sin alterar el valor original mostrado.

    Ejemplos:
        Brainly (21817) -> brainly
        Disney XD      -> disney xd
    """
    text_value = str(value or "").strip().casefold()
    text_value = _SITE_ID_SUFFIX.sub("", text_value)

    tokens = [
        token
        for token in _SITE_TOKEN.findall(text_value)
        if token not in _GENERIC_SITE_WORDS
    ]

    return " ".join(tokens)


def sites_match(expected, actual) -> bool:
    """
    Match operativo de sites.

    Se considera match cuando:
      - Los nombres normalizados son iguales.
      - Un nombre contiene al otro.
      - Comparten al menos una palabra significativa.

    Ejemplos válidos:
      Brainly (21817) vs Brainly
      Disney XD vs Disney
    """
    expected_norm = normalize_site(expected)
    actual_norm = normalize_site(actual)

    if not expected_norm or not actual_norm:
        return False

    if expected_norm == actual_norm:
        return True

    if (
        expected_norm in actual_norm
        or actual_norm in expected_norm
    ):
        return True

    expected_tokens = set(expected_norm.split())
    actual_tokens = set(actual_norm.split())

    return bool(expected_tokens & actual_tokens)


def compare_site_value(expected, actual) -> str:
    expected_text = str(expected or "").strip()
    actual_text = str(actual or "").strip()

    if not expected_text or not actual_text:
        return "NOT_VERIFIED"

    return "PASS" if sites_match(expected_text, actual_text) else "FAIL"


'''

if "def normalize_site(value)" not in text:
    if anchor not in text:
        raise SystemExit(
            "ERROR: no se encontró def clean_value en ui/app_v2.py"
        )

    text = text.replace(
        anchor,
        site_helpers + anchor,
        1,
    )

# Asegurar import re.
if "\nimport re\n" not in text:
    import_anchor = "import sys\n"
    if import_anchor not in text:
        raise SystemExit("ERROR: no se encontró import sys")

    text = text.replace(
        import_anchor,
        "import re\nimport sys\n",
        1,
    )

# ============================================================
# 2. Permitir comparación personalizada en comparison_row
# ============================================================

old_function = '''def comparison_row(
    field_name: str,
    expected,
    actual,
    *,
    normalizer=None,
    optional: bool = False,
) -> dict:
    return {
        "Campo validado": field_name,
        "Esperado en Traffic Sheet": clean_value(expected),
        "Encontrado en Innovid": clean_value(actual),
        "Resultado visual": compare_value(
            expected,
            actual,
            normalizer=normalizer,
            optional=optional,
        ),
    }
'''

new_function = '''def comparison_row(
    field_name: str,
    expected,
    actual,
    *,
    normalizer=None,
    optional: bool = False,
    comparator=None,
) -> dict:
    if comparator is not None:
        visual_result = comparator(expected, actual)
    else:
        visual_result = compare_value(
            expected,
            actual,
            normalizer=normalizer,
            optional=optional,
        )

    return {
        "Validated field": field_name,
        "Expected from Traffic Sheet": clean_value(expected),
        "Found in Innovid": clean_value(actual),
        "Result": visual_result,
    }
'''

if old_function in text:
    text = text.replace(old_function, new_function, 1)
elif "comparator=None" not in text:
    raise SystemExit(
        "ERROR: comparison_row no coincide con la versión esperada."
    )

# ============================================================
# 3. Aplicar el comparador flexible exclusivamente al Site
# ============================================================

old_site = '''                        comparison_row(
                            "Site",
                            expected.site,
                            actual.site if actual else "",
                        ),
'''

new_site = '''                        comparison_row(
                            "Site",
                            expected.site,
                            actual.site if actual else "",
                            comparator=compare_site_value,
                        ),
'''

if old_site in text:
    text = text.replace(old_site, new_site, 1)
elif "comparator=compare_site_value" not in text:
    raise SystemExit(
        "ERROR: no se encontró el comparison_row de Site."
    )

# ============================================================
# 4. URL/Attribution no aplicables deben mostrar N/A
# ============================================================

text = text.replace(
    '''                                    "URL": (
                                        creative_link.url.result
                                        if creative_link.url
                                        else "NOT_VERIFIED"
                                    ),''',
    '''                                    "URL": (
                                        creative_link.url.result
                                        if creative_link.url is not None
                                        else "N/A"
                                    ),''',
)

text = text.replace(
    '''                                    "Attribution": (
                                        creative_link.triangle.result
                                        if creative_link.triangle
                                        else "NOT_VERIFIED"
                                    ),''',
    '''                                    "Attribution": (
                                        creative_link.triangle.result
                                        if creative_link.triangle is not None
                                        else "N/A"
                                    ),''',
)

# Variantes que pudieron quedar con diferente indentación.
text = text.replace(
    'else "NOT_VERIFIED"\n                                    ),\n                                }\n                            )',
    'else "N/A"\n                                    ),\n                                }\n                            )',
)

path.write_text(text, encoding="utf-8")

print("OK: flexible Site matching added.")
print("OK: UI comparison columns translated.")
print("OK: non-applicable URL/Attribution now display N/A.")
