from enum import Enum

class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

CHECKLIST = [
    "placement_exists",
    "creative_exists",
    "placement_name",
    "creative_name",
    "dimensions",
    "landing_url",
    "dtree",
    "dset",
    "creative_mapping",
    "duplicates",
]

