"""
Que revisa cada regla, en una frase.

Lo usan la interfaz (el "porque" de cada hallazgo) y los callouts de
los reportes. Una regla nueva se agrega aqui.
"""

#: Que revisa cada regla, en una frase. Es lo primero del "porque".
RULE_TITLES = {
    "EXT-000": "The Traffic Sheet could be read",
    "EXT-001": "A required column is not empty",
    "PLC-001": "The placement in the Traffic Sheet exists in Innovid",
    "PLC-002": "A full disassignment left the placement stopped",
    "PLC-003": "The placement the Traffic Sheet wants running is on",
    "PLC-005": "The placement size matches the Traffic Sheet",
    "PLC-004": "The placement flight dates match the Traffic Sheet",
    "PLC-006": "The placement name matches",
    "PLC-007": "The rotation the placement declares has creatives of its size",
    "CRE-001": "The creative is assigned as the Traffic Sheet asks",
    "CRE-002": "The 1x1 pixel is assigned on a site-served placement",
    "CRE-008": "Creative rotation",
    "ROT-001": "The requested rotation change was applied",
    "URL-001": "The landing page matches the click tag in Innovid",
    "URL-002": "The new landing page is live in Innovid",
    "URL-003": "Landing pages of directly assigned placements",
    "ATR-001": "Attribution (CGEN) on each creative",
    "ATR-002": "Attribution (CGEN) on the placement",
    "TRK-001": "The decision tree is the right one",
    "TRK-002": "The decision set is the right one",
    "INV-001": "Creative flight dates inside the decision set",
    "INV-002": "Creative rotation weight inside the decision set",
    "INV-003": "Verification partner on the placement",
    "INV-004": "The creative name in the decision set",
    "INV-005": "The placement the Traffic Sheet wants running is on in Innovid",
    "TAG-001": "The tag file declares the right Campaign ID",
    "TAG-002": "The tag's placement exists in Innovid",
    "TAG-003": "The tag's placement is part of this request",
    "TAG-004": "The tag's placement name matches",
    "TAG-008": "The Campaign ID inside the tag",
    "TAG-009": "The dimensions inside the tag",
    "TAG-010": "The tag is not empty",
    "TAG-011": "The placement appears once in the tag file",
    "TAG-012": "Adobe tag columns (Ftrack, Clicktag, Protected)",
    "TAG-013": "Every 1x1 with a vendor has a row in the tag file",
    "TAG-014": "The landing page inside the 1x1 click tag",
    "TAG-015": "Every column of the tag file is filled after wrapping",
    "DV-001": "DV Pinnacle tag delivered for the placement",
    "DV-002": "DV Pinnacle tags outside this request",
    "DV-003": "DoubleVerify column in the Innovid tag file",
    "PIX-002": "Vendor pixels on the placement",
    "PIX-A01": "Adobe vendor pixels (DISQO, iSpot)",
    "DEF-001": "The default ad is consistent",
    "VID-001": "Remove VPAID on the site of video placements",
}
