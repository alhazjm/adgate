"""Angle cards built from the public-evidence sweep of 15 Jul 2026 (Singapore
market, Huggies product lines). Every receipt is verbatim from a cited public
source and carries its provenance grade honestly:

  fetched   - the page was loaded and the text read directly
  cached    - retrieved from a public archive (e.g. the pullpush Reddit archive)
  snippet   - seen only in search-result snippets (live page bot-walled);
              weakest grade, never load-bearing on its own
  brand     - the brand's own published copy (site/social) - context for voice
              and claims, never counted as independent customer evidence

Do NOT paraphrase receipts - they are the proof points the briefs cite.
"""

ANGLE_CARDS = [
    {
        "angle_tag": "newborn-default",
        "brand": "naturemade",
        "claim": "The newborn default in Singapore - the line most SG babies wear first, "
                 "gentle enough to keep from day one.",
        "verbatim_receipts": [
            {"quote": "If you've welcomed your newborn in a local maternity hospital, chances "
                      "are that your child's first diaper is from Huggies' Platinum Naturemade range",
             "provenance": "fetched", "source": "HoneyKids Asia SG diaper roundup, 16 Jun 2026"},
            {"quote": "we have been using huggies naturemade for years, highly recommend it",
             "provenance": "cached", "source": "Reddit r/askSingapore (pullpush archive), Dec 2023"},
        ],
        "audience": ["Expecting SG mums building the newborn kit", "New parents fresh from the maternity ward"],
        "evidence_grade": "STRONG - hospital-default status from a fetched 2026 SG editorial + "
                          "multi-year organic endorsements on SG Reddit",
        "notes": "TRAP: the hospital fact is a third-party observation, NOT ad substantiation - "
                 "'hospitals choose/trust Huggies' is gate-blocked (SCAP medical appendix; NAD "
                 "2018). Trust claims route through the brand's substantiated Euromonitor mums "
                 "line instead.",
    },
    {
        "angle_tag": "overnight-up-to-12h",
        "brand": "naturemade",
        "claim": "Overnight hold parents actually report - claimed only in the licensed "
                 "'up to 12 hours' form, never as an absolute.",
        "verbatim_receipts": [
            {"quote": "I'm using Huggies nature made and it lasts 12 hours for my little one!",
             "provenance": "cached", "source": "Reddit r/askSingapore (pullpush archive), Dec 2023"},
            {"quote": "We like Rascal and Friends and Mamypoko Air Fit. Huggies Naturemade is "
                      "alright too. All 3 brands last long and don't leak overnight.",
             "provenance": "cached", "source": "Reddit r/askSingapore (pullpush archive), Apr 2024"},
        ],
        "audience": ["Sleep-starved parents of heavy wetters", "Parents switching after 3am leaks"],
        "evidence_grade": "GOOD with a parity caveat - SG parents corroborate 12-hour hold, but "
                          "rank two rivals at the same level (never claim superiority)",
        "notes": "TRAPS: 'up to' is mandatory (the brand's own footnote is a urination-rate "
                 "model, not a wear test - duration-without-up-to rule); no competitor "
                 "superiority (competitor-superiority rule).",
    },
    {
        "angle_tag": "breathable-humid-sg",
        "brand": "airsoft",
        "claim": "Airflow for Singapore heat - breathability as the comfort story for "
                 "sweaty, active babies.",
        "verbatim_receipts": [
            {"quote": "Huggies Ultra works best with no leak, and baby buttocks won't feel "
                      "'wetness' therefore no rashes",
             "provenance": "snippet", "source": "SingaporeMotherhood forum overnight-leak thread "
             "(live page CAPTCHA-walled; search-snippet grade)"},
        ],
        "aggregate_evidence": [
            "Brand-side context: AirSoft advertises 'air-ventilation channels... 10X more "
            "airflow' with the only cited rash claim in the SG stack (Akin et al., Pediatric "
            "Dermatology, 2001) - huggies.com.sg/diapers/huggies-airsoft-pants, fetched 15 Jul 2026",
        ],
        "audience": ["Parents of crawlers who sweat through everything", "HDB no-aircon daytime households"],
        "evidence_grade": "MEDIUM - one SG forum voice (snippet grade) + the brand's own cited "
                          "clinical claim; breathability-comfort is the safe framing",
        "notes": "TRAPS: all rash claims are gate-blocked (rash-hypoallergenic-guarantee rule); "
                 "the licensed 'helps prevent diaper rash' form requires the Akin 2001 citation "
                 "and sits behind a claims-owner whitelist, so copy leads with airflow comfort, "
                 "not skin outcomes.",
    },
    {
        "angle_tag": "thin-not-flimsy",
        "brand": "naturemade",
        "claim": "Thin without the trade-off - 5mm-thin profile that still absorbs a "
                 "heavy wetter's day.",
        "verbatim_receipts": [
            {"quote": "one of the softest and thinnest diapers (only 5mm!)",
             "provenance": "fetched", "source": "HoneyKids Asia SG diaper roundup, 16 Jun 2026"},
            {"quote": "It's very thin and absorbent as my son urinates a lot so it managed to "
                      "capture all the urine most of the times",
             "provenance": "fetched", "source": "SG parent blogger (KKH newborn), "
             "hilzdoesreviews.wordpress.com, Mar 2021"},
        ],
        "audience": ["Parents who hate bulky waddle", "Diaper-bag minimalists"],
        "evidence_grade": "STRONG - two independent fetched SG sources on the same axis; note "
                          "the blogger's honest 'most of the times' hedge",
        "notes": "TRAPS: no 'thinnest diaper in SG' (competitor-superiority rule); mirror the "
                 "customer's own hedged register - the receipt says 'most of the times', so "
                 "the copy never says 'always'.",
    },
    {
        "angle_tag": "carton-economics",
        "brand": "naturemade",
        "claim": "Mega-day carton maths - SG parents buy Huggies by the carton on promo "
                 "cycles, and the copy can own that behaviour.",
        "verbatim_receipts": [
            {"quote": "I got Huggies L pants at 28 cents each during 3.3 because I bought 2 cartons!",
             "provenance": "cached", "source": "Reddit r/askSingapore (pullpush archive), Apr 2024"},
            {"quote": "Diapers, I buy Huggies. If I remember correctly, $50ish per carton",
             "provenance": "cached", "source": "Reddit r/askSingapore (pullpush archive), Jul 2023"},
            {"quote": "Previously Huggies had some really good deal with promo codes but seems "
                      "like theyve do away with them",
             "provenance": "cached", "source": "Reddit r/askSingapore (pullpush archive), Apr 2024"},
        ],
        "audience": ["Carton-planning value hunters", "9.9/11.11 mega-day shoppers"],
        "evidence_grade": "STRONG behavioural pattern - per-piece benchmarking (~28-30 cents) "
                          "and carton buying are the SG purchase reality; promo goodwill is "
                          "promo-dependent",
        "notes": "TRAPS: never 'best value in SG' or 'cheapest' (SG parents name Drypers/Merries "
                 "as the value picks - competitor-superiority rule); price framing must survive "
                 "the 28-cents-per-piece promo benchmark parents already know.",
    },
    {
        "angle_tag": "black-label-softness-craft",
        "brand": "black-label",
        "claim": "Premium softness as a craft story - the top-tier line's hug-soft "
                 "positioning for parents who want the best-feeling option.",
        "verbatim_receipts": [
            {"quote": "Our premium diapers are as soft as a mother's hug. Snug, soft, and "
                      "secure - because your baby deserves the royal treatment!",
             "provenance": "brand", "source": "Huggies.SG Facebook caption (Black Label video), "
             "fetched 15 Jul 2026"},
        ],
        "aggregate_evidence": [
            "Brand-side: Black Label launched exclusively on Lazada Super Brand Day (29 May "
            "2023, fetched caption); product page credits 'Japan-imported high-quality cotton' "
            "whose '72 hours' figure is footnoted as preparation time, not a performance claim",
        ],
        "audience": ["Premium-tier parents", "Gift-set buyers (baby showers, full-month)"],
        "evidence_grade": "BRAND-SIDE ONLY - no independent SG VoC found for this line; the "
                          "angle is voice-led, and every performance number stays footnote-scoped",
        "notes": "TRAPS: '30x absorbent' describes the polymer, not the diaper, and '99.9%' "
                 "exceeds the 99% internal-testing footnote (stat-inflation rule); 'softest "
                 "ever' is contested in public reviews and gate-blocked (competitor-superiority).",
    },
    {
        "angle_tag": "little-swimmers-pool-day",
        "brand": "little-swimmers",
        "claim": "Condo-pool and swim-class confidence - containment built for water play, "
                 "sold on fun and easy on-off, never on absorbency.",
        "verbatim_receipts": [
            {"quote": "As a product designed for water wear, Huggies Little Swimmers 5-6 have "
                      "almost no absorbency by design.",
             "provenance": "fetched", "source": "Independent diaper test blog (diapermetrics), "
             "20 Feb 2026 - the boundary the copy must respect"},
        ],
        "aggregate_evidence": [
            "Availability: 'HUGGIES Little Swimmers Disposable Swimpants S (7-12kg) 12s' listed "
            "at Watsons SG (snippet grade; product page bot-walled)",
        ],
        "audience": ["Condo-pool weekend families", "Baby swim-class parents"],
        "evidence_grade": "CATEGORY-DEFINING - the strongest receipt here defines what NOT to "
                          "claim; the angle sells the actual job (water play, containment, fun)",
        "notes": "HARD LINE RULE: any absorbency/dryness/leak-proof framing for this line is "
                 "gate-blocked (little-swimmers-absorbency) - it misrepresents the product "
                 "category itself.",
    },
    {
        "angle_tag": "poonami-containment",
        "brand": "naturemade",
        "claim": "Blowout containment for explosive days - hedged, lived-experience "
                 "framing of the mess every parent knows.",
        "verbatim_receipts": [
            {"quote": "no rashes, no leaks. Best Value for money",
             "provenance": "snippet", "source": "Amazon.sg review, Platinum Naturemade listing "
             "(page bot-walled; snippet grade). NOTE: quoting this verbatim in ad copy still "
             "trips the absolute-leak rule - conservative by design"},
            {"quote": "Huggies were fantastic for the last 3 years, almost never had a leak or blowout.",
             "provenance": "cached", "source": "Reddit r/NewParents (pullpush archive), May 2025 - "
             "note the customer's own 'almost'"},
        ],
        "audience": ["Parents of newborn poonami survivors", "Car-seat and stroller commuters"],
        "evidence_grade": "MIXED/POLARISED - the same month produced 'guaranteed leak or blowout' "
                          "complaints elsewhere; only hedged containment claims are defensible",
        "notes": "TRAPS: absolutes are gate-blocked even inside quoted reviews (absolute-leak-"
                 "blowout rule); the honest register is the customer's own 'almost never'.",
    },
]


def load_cards():
    return list(ANGLE_CARDS)
