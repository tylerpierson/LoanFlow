import re

DOCUMENT_TYPES = [
    "Processing Notes",
    "Property Tax / Appraisal District",
    "DU Findings",
    "ID",
    "Credit Explanation Letter",
    "Credit Report",
    "Income Worksheet",
    "Paystub",
    "W-2",
    "Bank Statement",
    "Cashier's Check / Earnest Money",
    "Purchase Contract",
    "Loan Application",
    "Insurance",
    "Title",
    "Appraisal",
    "Disclosure",
    "Unknown",
]

RULES = [
    (
        "Processing Notes",
        [
            r"notes for processing",
            r"processing notes",
            r"processor.?s notes",
            r"loan setup",
        ],
    ),
    (
        "Property Tax / Appraisal District",
        [
            r"dallas central appraisal district",
            r"central appraisal district",
            r"appraisal district",
            r"dcad",
            r"property tax estimator",
            r"taxing jurisdiction",
            r"taxing entity",
            r"taxable value",
            r"market value",
            r"improvement value",
            r"legal description",
            r"residential account",
            r"homestead exemption",
            r"apprais",
            r"taxable",
            r"district",
        ],
    ),
    (
        "DU Findings",
        [
            r"desktop underwriter",
            r"du findings",
            r"underwriting findings",
            r"summary of findings",
            r"approve.?eligible",
            r"fannie mae",
            r"recommendation",
            r"verification messages",
            r"approval conditions",
            r"risk.?eligibility",
            r"findings",
            r"loan casefile",
            r"casefile id",
        ],
    ),
    (
        "Credit Explanation Letter",
        [
            r"consumer explanation letter",
            r"credit accounts and inquiries",
            r"letter of explanation",
            r"explanation letter",
            r"previous address",
        ],
    ),
    (
        "Credit Report",
        [
            r"merged infile credit report",
            r"credit report",
            r"cic credit",
            r"experian",
            r"equifax",
            r"transunion",
            r"fico",
            r"tradeline",
            r"score models",
            r"account number",
            r"payment history",
            r"public records",
            r"inquiries",
            r"derogatory summary",
            r"credit score",
        ],
    ),
    (
        "Income Worksheet",
        [
            r"wage earner income calculation",
            r"income calculation",
            r"qualifying income",
            r"average income",
            r"ytd income",
            r"base income",
            r"variable total income",
            r"frequency of pay",
        ],
    ),
    (
        "Paystub",
        [
            r"earnings statement",
            r"pay date",
            r"period start",
            r"period end",
            r"gross pay",
            r"net pay",
            r"year to date",
            r"ytd",
            r"deductions",
            r"direct deposit",
        ],
    ),
    (
        "W-2",
        [
            r"form w-2",
            r"wage and tax statement",
            r"w-2 and earnings summary",
            r"employee.?s federal tax return",
            r"social security wages",
            r"medicare wages",
            r"federal income tax withheld",
        ],
    ),
    (
        "Bank Statement",
        [
            r"checking summary",
            r"transaction detail",
            r"beginning balance",
            r"ending balance",
            r"deposits and additions",
            r"electronic withdrawals",
            r"customer service information",
            r"jpmorgan chase",
            r"chase",
            r"bank of america",
            r"wells fargo",
            r"account number",
        ],
    ),
    (
        "Cashier's Check / Earnest Money",
        [
            r"cashier.?s check",
            r"earnest money",
            r"pay to the order of",
            r"non negotiable",
        ],
    ),
    (
        "Purchase Contract",
        [
            r"one to four family residential contract",
            r"residential contract",
            r"purchase contract",
            r"sales contract",
            r"third party financing addendum",
            r"buyer",
            r"seller",
            r"property address",
            r"option fee",
            r"sales price",
            r"closing",
        ],
    ),
    (
        "Loan Application",
        [
            r"uniform residential loan application",
            r"loan application",
            r"borrower information",
            r"mortgage loan application",
        ],
    ),
    (
        "ID",
        [
            r"driver license",
            r"drivers license",
            r"limited term",
            r"passport",
            r"identification card",
            r"class c",
            r"date of birth",
        ],
    ),
    (
        "Insurance",
        [
            r"homeowners insurance",
            r"hazard insurance",
            r"insurance premium",
            r"insurance binder",
        ],
    ),
    (
        "Title",
        [
            r"title commitment",
            r"title company",
            r"independence title",
            r"escrow officer",
        ],
    ),
    (
        "Appraisal",
        [
            r"uniform residential appraisal report",
            r"appraisal report",
            r"appraised value",
        ],
    ),
    (
        "Disclosure",
        [
            r"closing disclosure",
            r"loan estimate",
            r"settlement statement",
            r"disclosure",
        ],
    ),
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def classify_page(text: str) -> dict:
    clean = normalize_text(text)
    scores = {}

    for doc_type, patterns in RULES:
        score = 0

        for pattern in patterns:
            matches = re.findall(pattern, clean, re.I)
            score += len(matches)

        scores[doc_type] = score

    best_type = "Unknown"
    best_score = 0

    for doc_type, score in scores.items():
        if score > best_score:
            best_type = doc_type
            best_score = score

    if best_score == 0:
        return {"category": "Unknown", "confidence": 0.0, "score": 0}

    confidence = min(0.95, best_score / 5)

    return {"category": best_type, "confidence": confidence, "score": best_score}


def should_continue_previous(
    current: dict,
    previous: dict,
    current_section: dict | None = None,
) -> bool:
    current_type = current["category"]
    previous_type = previous["category"]
    text = normalize_text(current.get("text", ""))

    if current_type == previous_type:
        return True

    continuation_words = [
        "continued",
        "page 2 of",
        "page 3 of",
        "page 4 of",
        "page 5 of",
        "signature",
        "initial",
        "addendum",
        "transaction detail",
        "verification messages",
        "observations",
        "borrower signature",
        "seller signature",
        "end of report",
    ]

    if any(word in text for word in continuation_words):
        return True

    section_length = 0
    section_type = previous_type

    if current_section:
        section_length = current_section["endPage"] - current_section["startPage"] + 1
        section_type = current_section["category"]

    if current_type == "Unknown" and current_section:
        if section_type in [
            "DU Findings",
            "Credit Report",
            "Bank Statement",
            "Purchase Contract",
            "Property Tax / Appraisal District",
        ] and section_length >= 2:
            return True

    if current_type == "Unknown" and previous.get("confidence", 0) >= 0.75 and len(text) < 800:
        return True

    if previous_type == "Property Tax / Appraisal District":
        return any(
            word in text
            for word in [
                "tax",
                "taxable",
                "market value",
                "appraisal district",
                "dcad",
                "legal description",
                "homestead",
                "jurisdiction",
                "exemption",
                "apprais",
                "district",
            ]
        )

    if previous_type == "DU Findings":
        return any(
            word in text
            for word in [
                "desktop underwriter",
                "findings",
                "recommendation",
                "verification",
                "messages",
                "fannie mae",
                "income",
                "assets",
                "liabilities",
                "casefile",
                "borrower",
                "mortgage information",
            ]
        )

    if previous_type == "Credit Report":
        return any(
            word in text
            for word in [
                "tradeline",
                "account",
                "payment",
                "balance",
                "inquiry",
                "fico",
                "experian",
                "equifax",
                "transunion",
                "credit",
                "public records",
                "derogatory",
            ]
        )

    if previous_type == "Bank Statement":
        return any(
            word in text
            for word in [
                "deposit",
                "withdrawal",
                "balance",
                "checking",
                "savings",
                "transaction",
                "account number",
                "customer service",
                "jpmorgan",
                "chase",
            ]
        )

    if previous_type == "Purchase Contract":
        return any(
            word in text
            for word in [
                "buyer",
                "seller",
                "property",
                "contract",
                "closing",
                "option fee",
                "signature",
                "initial",
                "addendum",
                "sales price",
                "title company",
            ]
        )

    if previous_type == "W-2":
        return any(
            word in text
            for word in [
                "wage and tax",
                "w-2",
                "earnings summary",
                "social security",
                "medicare",
                "federal income tax",
            ]
        )

    return False


def build_sections(pages: list[dict]) -> list[dict]:
    sections = []

    for page in pages:
        if not sections:
            sections.append(
                {
                    "category": page["category"],
                    "startPage": page["page"],
                    "endPage": page["page"],
                    "pages": [page["page"]],
                    "confidence": page["confidence"],
                }
            )
            continue

        previous_page = pages[page["page"] - 2]
        current_section = sections[-1]

        if should_continue_previous(page, previous_page, current_section):
            current_section["endPage"] = page["page"]
            current_section["pages"].append(page["page"])

            if current_section["category"] == "Unknown" and page["category"] != "Unknown":
                current_section["category"] = page["category"]

            current_section["confidence"] = max(
                current_section.get("confidence", 0),
                page.get("confidence", 0),
            )
        else:
            sections.append(
                {
                    "category": page["category"],
                    "startPage": page["page"],
                    "endPage": page["page"],
                    "pages": [page["page"]],
                    "confidence": page["confidence"],
                }
            )

    return sections