import re

# ==========================================================
# SECTION AND HEADING PATTERNS
# ==========================================================


SECTION_REGEX = re.compile(r"^((?:\d+(?:\.\d+)*|[A-C]\d+(?:\.\d+)*))\s+(.+)$")

# VALID_VPLAN_SECTION_REGEX = re.compile(
#     r'^(?:[A-C]\d+(?:\.\d+)*)$'
# )

VALID_VPLAN_SECTION_REGEX = re.compile(r"^(?:\d+(?:\.\d+)*|[A-Z]\d+(?:\.\d+)*)$")

# ==========================================================
# TABLE PATTERNS
# ==========================================================

TABLE_REGEX = re.compile(r"(Table)\s+([A-Za-z]?\d+(?:[-.]\d+)*)", re.IGNORECASE)

TABLE_REF_REGEX = re.compile(r"Table\s+[A-Za-z]?\d+(?:[-.]\d+)*", re.IGNORECASE)

# ==========================================================
# REQUIREMENT PATTERNS
# ==========================================================

REQ_ID_REGEX = re.compile(r"([A-Z_]*REQ[-_]?\d+)", re.IGNORECASE)

FEATURE_REGEX = re.compile(
    r"\b(" r"to transfer|" r"permits|" r"supports|"
    # r'provides|'
    # r'contains|'
    # r'uses|'
    # r'controls|'
    r"control|" r"can either|" r"can pass|" r"requires that|"
    # r'perform'
    r")\b",
    re.IGNORECASE,
)


REQUIREMENT_REGEX = re.compile(
    r"\b("
    # Strong obligations and prohibitions
    r"shall not|shall|"
    r"must not|must|"
    r"should not|should|"
    r"cannot|can not|"
    r"may not|"
    r"must have|must not have|"
    r"must be|must not be|"
    r"must issue|must not issue|"
    r"must complete|must not complete|"
    r"must be consistent|"
    r"must not cross|"
    r"must be able to|"
    r"must be given|"
    # Explicit requirements
    r"is required to|are required to|required to|" r"requires that|"
    # Permission and prohibition
    r"is prohibited|are prohibited|prohibited to|"
    r"is not allowed to|are not allowed to|not allowed to|"
    r"is allowed to|are allowed to|allowed to|"
    r"is not permitted to|are not permitted to|not permitted to|"
    r"is permitted to|are permitted to|permitted to|"
    # Timing and signal stability
    r"must remain|shall remain|"
    r"must be held|"
    r"must be stable|shall be stable|remain stable|"
    r"shall be asserted|must be asserted|"
    r"shall be deasserted|must be deasserted|"
    # Validity constraints
    r"is valid only when|are valid only when|"
    r"is only valid|are only valid|"
    r"occurs only when|"
    r"is not valid|are not valid|"
    r"can only be|may only be|"
    # Optional and supported behaviour
    r"is not supported|are not supported|"
    r"is optional|are optional|"
    r"it is recommended to|"
    # Legal values and bounds
    r"length can be|"
    r"can discard|can omit|"
    r"can be lower than|can be higher than|"
    r"can be up to|may be up to|"
    r"can range from|may range from|"
    r"can be asserted|can be deasserted|"
    r"may be asserted|may be deasserted|"
    r"can be sent"
    r")\b",
    re.IGNORECASE,
)


# REQUIREMENT_REGEX = re.compile(
#     r'\b('
#     #strong obligations / prohibitions
#     r'shall|shall not|'
#     r'require|required|'
#     # r'permitted|'
#     r'able to|'
#     r'specified|not specified|'
#     r'must|must not|'
#     r'length can be|'
#     r'can discard|'
#     r'must be consistent|'
#     r'should|should not|'
#     r'cannot|can not|'
#     r'can omit|'
#     r'is required to|are required to|required to|'
#     r'is prohibited|are prohibited|prohibited to|'
#     r'is not allowed to|are not allowed to|not allowed to|'
#     r'is permitted to|are permitted to|permitted to|'
#     r'is not permitted to|are not permitted to|not permitted to|'
#     r'are non-modifiable| is non-modifiable|'
#     r'are nonmodifiable| is nonmodifiable|'
#     r'is not present|are not present|'
#     r'must be able to|must be given|'
#     r'is indicated|are indicated|'
#     r'is issued|are issued|'
#     r'is sent|are sent|'
#     r'is determined|are determined|'
#     r'is returned|are returned|'
#     r'is terminated|are terminated|'
#     r'returns|'

#     #Timing / protocol behaviour
#     r'must remain|shall remain|remain asserted|remains asserted|'
#     r'must be held|must be stable|'
#     r'must be stable|shall be stable|remain stable|'
#     r'shall be deasserted|must be deasserted|'

#     #Validity / legality constraints
#     r'is valid only when|are valid only when|'
#     r'is not valid|are not valid|'
#     r'is only valid|are only valid|'
#     r'can only be|may only be|'
#     r'is not satisfied|are not satisfied|'
#     r'is satisfied|are satisfied|'

#     #Optional / supported behaviour
#     r'is not supported|are not supported|'
#     r'is supported|are supported|'
#     r'is optional|are optional|'

#     #Legal values / bounds
#     r'can be lower than|can be higher than|'
#     r'can be up to|may be up to|'
#     r'can range from|may range from|'
#     r'can be obtained|'

#     #Spec-specific but common protocol phrasing
#     r'early termination of .* not supported|' # .* means anything in between.
#     r'is half that specified by|'
#     r'is determined from|'

#     #extra keywords
#     r'permitted to|is permitted to|are permitted to|'
#     r'is permitted|are permitted|'
#     r'allowed to|is allowed to|are allowed to|'
#     r'may|may not|'
#     r'are present|are not present|is present|is not present|'
#     r'must be asserted|'
#     r'shall be asserted|'
#     r'can be asserted|'
#     r'may be asserted|'
#     r'can be sent|'
#     r'indicates that|'

#     r')\b',
#     re.IGNORECASE
# )


CONDITIONAL_BEHAVIOUR_REGEX = re.compile(
    r"\b(?:when|if)\b.+\b(?:"
    r"asserts?|deasserts?|"
    r"uses?|transfers?|"
    r"accepts?|rejects?|"
    r"generates?|returns?|"
    r"occurs?|completes?|"
    r"indicates?|encodes?|"
    r"enables?|disables?|"
    r"gives?|receives?"
    r")\b",
    re.IGNORECASE,
)


# ==========================================================
# DECLARATIVE BEHAVIOUR PATTERNS
# ==========================================================

DECLARATIVE_BEHAVIOUR_REGEX = re.compile(
    r"\b(?:"
    # Behavioural consequences
    r"causes?\s+(?:an?\s+|the\s+)?" r"[A-Za-z0-9_-]+\s+to|"
    # State or behaviour changes
    r"(?:is|are)\s+"
    r"(?:set|cleared|asserted|deasserted|"
    r"updated|written|read|returned|"
    r"terminated|handled|ignored|reserved|"
    r"preserved|discarded|completed|"
    r"accepted|rejected|generated)|"
    # Table descriptions often omit the subject and auxiliary verb.
    r"(?:set|cleared|asserted|deasserted|"
    r"updated|written|read|returned|"
    r"terminated|handled|ignored|reserved|"
    r"preserved|discarded|completed|"
    r"accepted|rejected|generated)\b|"
    # Active architectural behaviour
    r"(?:resumes?|terminates?|"
    r"asserts?|deasserts?|"
    r"updates?|returns?|"
    r"generates?|produces?|"
    r"accepts?|rejects?|"
    r"completes?|discards?)\s+|"
    r"can\s+be\s+either\s+"
    r"[A-Za-z0-9_-]+\s+or\s+[A-Za-z0-9_-]+|"
    r")",
    re.IGNORECASE,
)

# ==========================================================
# NOTE AND ACRONYM PATTERNS
# ==========================================================

NOTE_REGEX = re.compile(
    r"^(NOTE|WARNING|CAUTION|IMPORTANT|ASSUMPTION)\b", re.IGNORECASE
)

ACRONYM_REGEX = re.compile(r"\b([A-Z]{2,10})\b")

# ==========================================================
# CROSS-REFERENCE PATTERNS
# ==========================================================

SECTION_REF_REGEX = re.compile(r"Section\s+\d+(?:\.\d+)*", re.IGNORECASE)


# ==========================================================
# ENCODING TABLE PATTERN
# ==========================================================


ENCODING_TABLE_REGEX = re.compile(
    r"(0b[01]+)\s+"
    r"([A-Za-z][A-Za-z0-9_-]*)\s+"
    r"(.*?)"
    r"(?="
    r"\s+0b[01]+\s+[A-Za-z][A-Za-z0-9_-]*\s+"
    r"|"
    r"\s+(?:\d+(?:\.\d+)*|[A-C]\d+(?:\.\d+)*)\s+"
    r"|"
    r"\s+Table\s+[A-Za-z]?\d+"
    r"|$"
    r")",
    re.DOTALL,
)

"""Excluding the following patterns from the regex to avoid false positives:"""
DESCRIPTIVE_SENTENCE_REGEX = re.compile(
    r"\b(?:"
    r"this section describes|"
    r"this chapter describes|"
    r"this document describes|"
    r"provides information|"
    r"is shown in|"
    r"is illustrated in|"
    r"for example|"
    r"the following example|"
    r"the purpose of"
    r")\b",
    re.IGNORECASE,
)
