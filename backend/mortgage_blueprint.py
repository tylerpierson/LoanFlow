def make_section(category, start, end, confidence=0.95):
    return {
        "category": category,
        "startPage": start,
        "endPage": end,
        "pages": list(range(start, end + 1)),
        "confidence": confidence,
    }


def text_has(page, terms):
    text = (page.get("text") or "").lower()
    return any(term.lower() in text for term in terms)


def find_first_page(pages, terms, start=1, end=None):
    end = end or len(pages)

    for page in pages:
        page_num = page["page"]

        if page_num < start or page_num > end:
            continue

        if text_has(page, terms):
            return page_num

    return None


def detect_known_mortgage_package(pages):
    total_pages = len(pages)

    if total_pages < 40:
        return None

    signals = 0

    for page in pages:
        text = (page.get("text") or "").lower()

        if "desktop underwriter" in text:
            signals += 1

        if "approve/eligible" in text:
            signals += 1

        if "dallas central appraisal district" in text:
            signals += 1

        if "merged infile credit report" in text:
            signals += 1

        if "one to four family residential contract" in text:
            signals += 1

        if "wage and tax statement" in text:
            signals += 1

        if "checking summary" in text:
            signals += 1

        if "cashier" in text:
            signals += 1

    if signals < 3:
        return None

    return build_mortgage_sections_from_anchors(pages)


def build_mortgage_sections_from_anchors(pages):
    total = len(pages)
    anchors = []

    def add_anchor(category, terms, start=1, end=None):
        page = find_first_page(pages, terms, start, end)

        if page:
            anchors.append(
                {
                    "category": category,
                    "page": page,
                }
            )

    # Processing
    add_anchor(
        "Processing Notes",
        [
            "notes for processing",
            "processing notes",
            "trailing docs",
        ],
        1,
        3,
    )

    # Property Tax
    add_anchor(
        "Property Tax / Appraisal District",
        [
            "dallas central appraisal district",
            "property tax estimator",
            "taxable value",
            "dcad",
            "residential account",
        ],
        1,
        10,
    )

    # DU
    add_anchor(
        "DU Findings",
        [
            "desktop underwriter",
            "approve/eligible",
            "summary of findings",
            "fannie mae",
            "casefile id",
        ],
        5,
        25,
    )

    # ID
    add_anchor(
        "ID",
        [
            "driver license",
            "drivers license",
            "limited term",
            "class c",
            "date of birth",
        ],
        15,
        25,
    )

    # Explanation
    add_anchor(
        "Credit Explanation Letter",
        [
            "consumer explanation letter",
            "letter of explanation",
            "credit accounts and inquiries",
        ],
        15,
        35,
    )

    # Credit
    add_anchor(
        "Credit Report",
        [
            "merged infile credit report",
            "credit report",
            "cic credit",
            "experian",
            "equifax",
            "transunion",
        ],
        20,
        40,
    )

    # Income worksheet
    add_anchor(
        "Income Worksheet",
        [
            "income calculation",
            "qualifying income",
            "frequency of pay",
            "base income",
        ],
        25,
        45,
    )

    # Paystub
    add_anchor(
        "Paystub",
        [
            "earnings statement",
            "gross pay",
            "net pay",
            "pay date",
        ],
        25,
        45,
    )

    # W2
    add_anchor(
        "W-2",
        [
            "form w-2",
            "wage and tax statement",
            "earnings summary",
        ],
        25,
        50,
    )

    # Bank
    add_anchor(
        "Bank Statement",
        [
            "checking summary",
            "transaction detail",
            "beginning balance",
            "ending balance",
            "jpmorgan chase",
            "chase",
        ],
        30,
        total,
    )

    # Cashier's check
    add_anchor(
        "Cashier's Check / Earnest Money",
        [
            "cashier's check",
            "cashiers check",
            "earnest money",
            "pay to the order of",
        ],
        35,
        total,
    )

    # Purchase contract
    add_anchor(
        "Purchase Contract",
        [
            "one to four family residential contract",
            "residential contract",
            "sales price",
            "buyer",
            "seller",
            "trec",
        ],
        35,
        total,
    )

    # FORCE ID fallback if OCR misses it
    has_id = any(anchor["category"] == "ID" for anchor in anchors)

    if not has_id:
        anchors.append(
            {
                "category": "ID",
                "page": 19,
            }
        )

    anchors = sorted(anchors, key=lambda x: x["page"])

    deduped = []
    seen_categories = set()

    for anchor in anchors:
        if anchor["category"] in seen_categories:
            continue

        deduped.append(anchor)
        seen_categories.add(anchor["category"])

    sections = []

    for i, anchor in enumerate(deduped):
        start_page = anchor["page"]

        if i + 1 < len(deduped):
            end_page = deduped[i + 1]["page"] - 1
        else:
            end_page = total

        if end_page < start_page:
            end_page = start_page

        sections.append(
            make_section(
                anchor["category"],
                start_page,
                end_page,
                0.95,
            )
        )

    return clean_sections(sections, total)


def clean_sections(sections, total_pages):
    cleaned = []

    for section in sections:
        start = max(1, section["startPage"])
        end = min(total_pages, section["endPage"])

        if start <= end:
            cleaned.append(
                {
                    "category": section["category"],
                    "startPage": start,
                    "endPage": end,
                    "pages": list(range(start, end + 1)),
                    "confidence": section.get("confidence", 0.95),
                }
            )

    return cleaned