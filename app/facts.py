"""Authoritative project facts and hallucination guard patterns."""

AUTHORIZED_FACTS = {
    "company": "Northstar Homes",
    "project": "Northstar One",
    "location": "Sector 79, Gurugram",
    "configurations": ("2 BHK", "3 BHK"),
    "starting_prices": {
        "2 BHK": "₹1.35 crore onwards",
        "3 BHK": "₹1.75 crore onwards",
    },
}

ALLOWED_PRICE_VALUES = frozenset({"1.35", "1.75", "135", "175"})

# User asks about details we were never given.
UNKNOWN_DETAIL_PATTERN = (
    r"(?:possession|handover|delivery|ready to move|move[- ]?in|"
    r"availability|available units|inventory|units left|"
    r"discount|offer|deal|cashback|early bird|limited time|"
    r"payment plan|emi|installment|down payment|loan|financing|"
    r"carpet area|built[- ]?up area|super area|sq\.?\s*ft|square feet|sqft|"
    r"rera|registration number|"
    r"amenit|swimming pool|\bgym\b|clubhouse|club house|jogging|tennis|spa|"
    r"concierge|security guard|\blift\b|\belevator\b|parking slot|play area|"
    r"floor plan|layout|\btower\b|\bblock\b|floor count|\bfloors\b|"
    r"commute|distance from|near metro|nearby school|"
    r"developer track record|builder reputation)"
)

# Model output must not claim these unless booking is confirmed.
FORBIDDEN_OUTPUT_PATTERNS = (
    (r"\b\d+(?:\.\d+)?\s*(?:sq\.?\s*ft|square feet|sqft)\b", "invented_area"),
    (r"\b(?:possession|handover|delivery|ready to move)\b", "invented_possession"),
    (r"\b(?:discount|offers?|cashback|early bird|limited time)\b", "invented_offer"),
    (r"\b(?:payment plan|emi plan|installment plan)\b", "invented_payment"),
    (r"\b(?:rera\s*(?:no\.?|number|#)|registration\s*(?:no\.?|number))\s*[\w/-]+", "invented_rera"),
    (r"\b(?:swimming pool|clubhouse|gymnasium|tennis court|jogging track)\b", "invented_amenity"),
    (r"\b(?:carpet|built[- ]?up|super)\s*area\b", "invented_area"),
    (r"\b(?:tower\s+[a-z]|block\s+[a-z]|floor\s+\d+)\b", "invented_inventory"),
)

PRICE_QUESTION_PATTERN = r"\b(price|cost|rate|kitna|daam|pricing|how much|kya\s+hai)\b|कीमत|दाम"
PROJECT_INFO_PATTERN = (
    r"\b(tell me about|about the project|project details|what is northstar|"
    r"kya hai northstar|project ke baare|overview|describe the project)\b"
)
FLEXIBLE_BUDGET_PATTERN = (
    r"\b(not fixed|not decided|undecided|flexible|open budget|open|depends|"
    r"decide later|no budget|budget nahi|tay nahi|fix nahi|fixed nahi|"
    r"pata nahi|still thinking|haven't decided|have not decided)\b"
)
