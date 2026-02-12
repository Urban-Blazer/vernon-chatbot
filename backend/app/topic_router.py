"""Keyword-based topic classification and department-specific prompt additions."""

import re
import logging

logger = logging.getLogger(__name__)

DEPARTMENTS = {
    "water_utilities": {
        "keywords": [
            r"\bwater\b", r"\butilit", r"\bsewer\b", r"\bmeter\b", r"\bhydrant\b",
            r"\bdrain", r"\bflood", r"\birrigation\b", r"\bwater\s+bill",
            r"\bwater\s+service", r"\bwater\s+quality",
        ],
        "prompt_addition": (
            "This question is about water and utility services. "
            "Focus on water billing, meter reading, service connections, sewer services, "
            "irrigation, and stormwater management when answering."
        ),
        "label": {"en": "Water & Utilities", "fr": "Eau et services publics"},
    },
    "building_permits": {
        "keywords": [
            r"\bpermit\b", r"\bbuilding\b", r"\bzoning\b", r"\brenovation",
            r"\bconstruction\b", r"\bbylaw\b", r"\bland\s+use", r"\bsubdivision",
            r"\bdevelopment\b", r"\binspection\b",
        ],
        "prompt_addition": (
            "This question is about building permits and development. "
            "Focus on permit applications, zoning bylaws, building inspections, "
            "land use planning, and development processes when answering."
        ),
        "label": {"en": "Building & Permits", "fr": "Construction et permis"},
    },
    "recreation": {
        "keywords": [
            r"\brecreation\b", r"\bpark\b", r"\bpool\b", r"\barena\b", r"\bsport",
            r"\bprogram\b", r"\bregistration\b", r"\bswim", r"\bskat",
            r"\btrail\b", r"\bcamping\b", r"\bfitness\b", r"\bgym\b",
        ],
        "prompt_addition": (
            "This question is about recreation and parks. "
            "Focus on recreation programs, facility schedules, park amenities, "
            "program registration, and outdoor activities when answering."
        ),
        "label": {"en": "Recreation & Parks", "fr": "Loisirs et parcs"},
    },
    "taxes_finance": {
        "keywords": [
            r"\btax", r"\bproperty\s+tax", r"\bassessment\b", r"\bbill\b",
            r"\bpayment\b", r"\binvoice\b", r"\bfinance\b", r"\bbudget\b",
            r"\bfee\b", r"\brate\b",
        ],
        "prompt_addition": (
            "This question is about taxes and finance. "
            "Focus on property taxes, tax payment methods, assessment notices, "
            "utility billing, and fee schedules when answering."
        ),
        "label": {"en": "Taxes & Finance", "fr": "Taxes et finances"},
    },
    "roads_transportation": {
        "keywords": [
            r"\broad\b", r"\bstreet\b", r"\bsidewalk\b", r"\btraffic\b",
            r"\bparking\b", r"\bsnow\b", r"\bplow\b", r"\btransit\b",
            r"\bbus\b", r"\bbike\b", r"\bcycl", r"\btransportation\b",
        ],
        "prompt_addition": (
            "This question is about roads and transportation. "
            "Focus on road maintenance, parking regulations, snow removal, "
            "transit services, cycling infrastructure, and traffic management when answering."
        ),
        "label": {"en": "Roads & Transportation", "fr": "Routes et transport"},
    },
    "waste_collection": {
        "keywords": [
            r"\bwaste\b", r"\bgarbage\b", r"\brecycl", r"\bcompost",
            r"\bcollection\b", r"\bdump\b", r"\blandfill\b", r"\bpickup\b",
            r"\bbin\b", r"\byard\s+waste",
        ],
        "prompt_addition": (
            "This question is about waste collection and recycling. "
            "Focus on collection schedules, recycling guidelines, composting, "
            "yard waste disposal, and landfill information when answering."
        ),
        "label": {"en": "Waste & Recycling", "fr": "Dechets et recyclage"},
    },
    "council_meetings": {
        "keywords": [
            r"\bcouncil\b", r"\bmeeting\b", r"\bminutes\b", r"\bagenda\b",
            r"\bmotion\b", r"\bpublic\s+hearing", r"\bcommittee\s+of\s+the\s+whole",
            r"\bcow\b", r"\bresolution\b", r"\bcouncillor\b", r"\bmayor\b",
            r"\belected\b", r"\bvot\w+", r"\bdeliberat",
        ],
        "prompt_addition": (
            "This question may relate to council meetings, agendas, or decisions. "
            "If council meeting transcriptions are available in the context, cite specific "
            "meeting dates and decisions. Focus on motions, resolutions, and directives."
        ),
        "label": {"en": "Council & Governance", "fr": "Conseil et gouvernance"},
    },
    "general": {
        "keywords": [],
        "prompt_addition": "",
        "label": {"en": "General", "fr": "General"},
    },
}


def classify_topic(question: str) -> str:
    """Classify a question into a department topic using keyword matching.

    Returns the topic key (e.g., 'water_utilities') or 'general' if no match.
    """
    question_lower = question.lower()

    best_topic = "general"
    best_score = 0

    for topic, config in DEPARTMENTS.items():
        if topic == "general":
            continue
        score = 0
        for pattern in config["keywords"]:
            if re.search(pattern, question_lower):
                score += 1
        if score > best_score:
            best_score = score
            best_topic = topic

    return best_topic


def get_prompt_addition(topic: str) -> str:
    """Get the prompt addition for a given topic."""
    dept = DEPARTMENTS.get(topic, DEPARTMENTS["general"])
    return dept.get("prompt_addition", "")


def get_topic_label(topic: str, language: str = "en") -> str:
    """Get the display label for a topic in the given language."""
    dept = DEPARTMENTS.get(topic, DEPARTMENTS["general"])
    labels = dept.get("label", {})
    return labels.get(language, labels.get("en", topic))


def get_all_topic_labels(language: str = "en") -> dict[str, str]:
    """Get all topic labels for the given language."""
    return {
        topic: get_topic_label(topic, language)
        for topic in DEPARTMENTS
    }
