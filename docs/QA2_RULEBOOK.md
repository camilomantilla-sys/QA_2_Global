# QA2 RULEBOOK
Version: 1.0

# Objetivo

QA2 valida que la implementación configurada en Innovid coincida con los requisitos definidos en la Traffic Sheet (TS) para todos los placements trabajados por Ad Ops.

La Traffic Sheet es la fuente de verdad.

Los exports de Innovid son la evidencia de implementación.

El objetivo es detectar discrepancias antes del lanzamiento.

---

# Estados posibles

## PASS

La validación coincide con lo solicitado en la TS.

## FAIL

Existe una discrepancia verificable entre TS y Export.

## REVIEW

La situación requiere validación humana o contexto adicional.

## NOT_VERIFIABLE

No existe evidencia suficiente para validar el requisito.

---

# Severidades

## CRITICAL

Puede generar problemas de serving, tracking, atribución, medición o lanzamiento incorrecto.

Ejemplos:

- Placement faltante
- Creative faltante
- Landing URL incorrecta
- Decision Tree incorrecto
- Attribution incorrecta
- Mapping incorrecto Placement ↔ Creative

## HIGH

Incumple un requisito importante de implementación.

Ejemplos:

- Direct Assignment incorrecto
- Implementation Type incorrecto
- Duplicados

## MEDIUM

Inconsistencia relevante sin impacto inmediato en serving.

Ejemplos:

- Naming incorrecto
- Creative naming incorrecto

## LOW

Diferencias de formato o limpieza sin impacto funcional.

---

# Alcance QA2

QA2 solamente revisa placements trabajados por Ad Ops.

Un placement entra en scope cuando:

- Tiene color propio de trabajo.
- Hereda trabajo desde Creative Rotations.
- Hereda trabajo desde Landing Pages.
- Tiene evidencia de modificación solicitada.

Placements sin evidencia de trabajo quedan fuera de alcance.

---

# Sistemas soportados

## Traffic Sheets

- Adobe Variante A
- Adobe Variante B
- WPP Standard

## Exports Innovid

- Placement Creative Export
- Placement Export

---

# RULE-001 Campaign Match

Categoria:
Scope

Severidad:
BLOCKER

Validación:

Campaign ID de la TS debe coincidir con Campaign ID del export.

PASS:
Coincide.

FAIL:
No coincide.

Acción:
Abortar QA2.

---

# RULE-002 Placement Exists

Categoria:
Inventory

Severidad:
CRITICAL

Validación:

Todo placement trabajado en TS debe existir en el export.

PASS:
Placement encontrado.

FAIL:
Placement faltante.

---

# RULE-003 Creative Exists

Categoria:
Inventory

Severidad:
CRITICAL

Validación:

Todo creative esperado debe existir en el export.

PASS:
Creative encontrado.

FAIL:
Creative faltante.

---

# RULE-004 Placement Duplicate

Categoria:
Inventory

Severidad:
HIGH

Validación:

El mismo Placement ID no debe aparecer múltiples veces de forma inconsistente.

PASS:
Sin duplicados.

FAIL:
Placement ID duplicado.

---

# RULE-005 Creative Duplicate

Categoria:
Inventory

Severidad:
HIGH

Validación:

El mismo Creative ID no debe aparecer múltiples veces de forma inconsistente.

PASS:
Sin duplicados.

FAIL:
Creative ID duplicado.

---

# RULE-006 Placement Name Match

Categoria:
Naming

Severidad:
MEDIUM

Validación:

TS Placement Name = Innovid Placement Name.

PASS:
Coincide.

FAIL:
No coincide.

---

# RULE-007 Creative Name Match

Categoria:
Naming

Severidad:
MEDIUM

Validación:

TS Creative Name = Innovid Creative Name.

PASS:
Coincide.

FAIL:
No coincide.

---

# RULE-008 Dimensions Match

Categoria:
Naming

Severidad:
MEDIUM

Validación:

TS Dimensions = Innovid Dimensions.

PASS:
Coincide.

FAIL:
No coincide.

---

# RULE-009 Dates Match

Categoria:
Setup

Severidad:
HIGH

Validación:

Start Date y End Date configuradas coinciden con la TS.

PASS:
Coinciden.

FAIL:
No coinciden.

---

# RULE-010 Group Exists

Categoria:
Group

Severidad:
HIGH

Aplicación:

Adobe Variante A
WPP

Validación:

Creative Rotation / Decision Tree existe.

PASS:
Existe.

FAIL:
No existe.

---

# RULE-011 Group Match

Categoria:
Group

Severidad:
HIGH

Validación:

TS Group Name = Innovid Decision Tree Name.

PASS:
Coincide.

FAIL:
No coincide.

---

# RULE-012 Group Membership

Categoria:
Group

Severidad:
HIGH

Validación:

Placement 