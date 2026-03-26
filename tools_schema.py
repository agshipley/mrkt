"""
Mrkt — Tool schemas for deal term extraction.
Each tool defines a JSON schema that forces Claude to return structured data.
"""

# ── Tool 1: Termination Fee Provisions ──────────────────────────
TERMINATION_FEE_TOOL = {
    "name": "extract_termination_provisions",
    "description": (
        "Extracts termination fee structure from a merger agreement. "
        "Call this tool with all termination-related provisions found. "
        "If a provision is not present, set its value to null. "
        "Do NOT fabricate or infer values — only extract what is explicitly stated."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "target_termination_fee": {
                "type": ["object", "null"],
                "description": "Fee payable by the target company upon termination",
                "properties": {
                    "amount_dollars": {
                        "type": ["number", "null"],
                        "description": "Dollar amount of the termination fee"
                    },
                    "as_percentage_of_deal_value": {
                        "type": ["number", "null"],
                        "description": "Fee as percentage of deal value, if calculable"
                    },
                    "triggers": {
                        "type": ["array", "null"],
                        "items": {
                            "type": "string",
                            "enum": [
                                "superior_proposal",
                                "board_recommendation_change",
                                "shareholder_vote_failure_after_competing_bid",
                                "regulatory_failure",
                                "financing_failure",
                                "general_breach",
                                "other"
                            ]
                        }
                    },
                    "trigger_details": {
                        "type": ["string", "null"],
                        "description": "Additional detail on triggers"
                    }
                }
            },
            "reverse_termination_fee": {
                "type": ["object", "null"],
                "description": "Fee payable by the acquirer/parent upon termination",
                "properties": {
                    "amount_dollars": {
                        "type": ["number", "null"]
                    },
                    "triggers": {
                        "type": ["array", "null"],
                        "items": {
                            "type": "string",
                            "enum": [
                                "regulatory_failure",
                                "financing_failure",
                                "general_breach",
                                "other"
                            ]
                        }
                    },
                    "trigger_details": {
                        "type": ["string", "null"]
                    }
                }
            },
            "go_shop": {
                "type": ["object", "null"],
                "properties": {
                    "present": {"type": "boolean"},
                    "duration_days": {"type": ["integer", "null"]},
                    "reduced_fee_during_shop": {"type": ["number", "null"]}
                }
            },
            "source_sections": {"type": ["string", "null"]},
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"]
            }
        },
        "required": ["target_termination_fee", "reverse_termination_fee",
                     "go_shop", "source_sections", "confidence"]
    }
}

# ── Tool 2: Antitrust Efforts Standard ──────────────────────────
EFFORTS_STANDARD_TOOL = {
    "name": "extract_efforts_standard",
    "description": (
        "Extracts the regulatory/antitrust efforts standard from a merger agreement. "
        "Extract TWO things: (1) the STATED efforts standard — the literal language used "
        "(e.g., 'reasonable best efforts', 'best efforts'), and (2) the FUNCTIONAL efforts "
        "classification — whether the agreement effectively imposes a 'hell or high water' "
        "obligation by requiring unlimited divestitures or other actions to obtain regulatory "
        "approval, regardless of the stated standard. "
        "Look in the covenants section, typically in provisions about regulatory filings, "
        "antitrust approvals, or HSR Act compliance."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "stated_efforts_standard": {
                "type": ["string", "null"],
                "enum": [
                    "best_efforts",
                    "reasonable_best_efforts",
                    "commercially_reasonable_efforts",
                    "reasonable_efforts",
                    "other",
                    None
                ],
                "description": "The literal efforts standard language in the agreement"
            },
            "stated_standard_detail": {
                "type": ["string", "null"],
                "description": "Exact language used if 'other', or direct quote of the standard"
            },
            "functional_efforts_classification": {
                "type": ["string", "null"],
                "enum": [
                    "hell_or_high_water",
                    "limited_divestiture_obligation",
                    "no_divestiture_obligation",
                    "other",
                    None
                ],
                "description": (
                    "The functional classification based on the FULL provision. "
                    "'hell_or_high_water' = acquirer must take any and all actions including "
                    "unlimited divestitures to obtain approval. "
                    "'limited_divestiture_obligation' = acquirer must divest but with caps or "
                    "materiality thresholds. "
                    "'no_divestiture_obligation' = no affirmative divestiture commitment."
                )
            },
            "unlimited_divestiture_obligation": {
                "type": ["boolean", "null"],
                "description": (
                    "Whether the acquirer is required to divest assets, terminate contracts, "
                    "or restructure businesses WITHOUT a cap or materiality limitation "
                    "to obtain regulatory approval"
                )
            },
            "divestiture_limitations_detail": {
                "type": ["string", "null"],
                "description": "If divestitures are limited, describe the cap or threshold"
            },
            "litigation_obligation": {
                "type": ["boolean", "null"],
                "description": "Whether the acquirer is required to litigate or contest regulatory challenges"
            },
            "source_sections": {"type": ["string", "null"]},
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"]
            }
        },
        "required": ["stated_efforts_standard", "functional_efforts_classification",
                     "unlimited_divestiture_obligation", "source_sections", "confidence"]
    }
}

# ── Tool 3: MAC Definition Structure ────────────────────────────
MAC_DEFINITION_TOOL = {
    "name": "extract_mac_definition",
    "description": (
        "Extracts the Material Adverse Effect (MAE/MAC) definition structure. "
        "Focus on: (1) what the MAE applies to, (2) the list of carve-outs/exclusions, "
        "(3) whether each carve-out has a 'disproportionate impact' qualifier, "
        "and (4) whether the definition references 'prospects' or includes a forward-looking standard. "
        "The MAE definition is typically in the Definitions article (Article I). "
        "IMPORTANT: For the pandemic carve-out, treat references to 'epidemics,' "
        "'quarantine restrictions,' 'public health emergencies,' or similar language "
        "as a pandemic carve-out even if the word 'pandemic' is not used. "
        "For COVID-specific references, look for 'COVID-19,' 'coronavirus,' 'SARS-CoV-2,' "
        "OR language like 'epidemics' and 'quarantine restrictions' that clearly contemplates "
        "the COVID-19 pandemic in context (e.g., agreements signed in 2020-2021). "
        "For disproportionate impact qualifiers, check whether there is a trailing provision "
        "that applies the qualifier to a RANGE of carve-outs (e.g., 'clauses (A) through (F) "
        "shall not apply to the extent such changes disproportionately affect...'). "
        "Apply the qualifier to each individual carve-out it covers."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "mae_applies_to": {
                "type": ["string", "null"],
                "enum": [
                    "target_and_subsidiaries_as_a_whole",
                    "target_only",
                    "target_and_subsidiaries_individually",
                    "other",
                    None
                ]
            },
            "includes_prospects": {
                "type": ["boolean", "null"],
                "description": "Whether MAE definition references target 'prospects'"
            },
            "forward_looking_standard": {
                "type": ["boolean", "null"],
                "description": "Whether MAE includes 'would reasonably be expected to' or similar forward-looking language"
            },
            "includes_ability_to_consummate": {
                "type": ["boolean", "null"],
                "description": "Whether MAE includes adverse impact on target's ability to consummate the transaction"
            },
            "carveouts": {
                "type": ["object", "null"],
                "description": "Each carve-out and whether it has a disproportionate impact qualifier",
                "properties": {
                    "general_economic_conditions": {
                        "type": ["object", "null"],
                        "properties": {
                            "present": {"type": "boolean"},
                            "disproportionate_impact_qualifier": {"type": "boolean"}
                        }
                    },
                    "political_social_conditions": {
                        "type": ["object", "null"],
                        "properties": {
                            "present": {"type": "boolean"},
                            "disproportionate_impact_qualifier": {"type": "boolean"}
                        }
                    },
                    "industry_changes": {
                        "type": ["object", "null"],
                        "properties": {
                            "present": {"type": "boolean"},
                            "disproportionate_impact_qualifier": {"type": "boolean"}
                        }
                    },
                    "change_in_law": {
                        "type": ["object", "null"],
                        "properties": {
                            "present": {"type": "boolean"},
                            "disproportionate_impact_qualifier": {"type": "boolean"}
                        }
                    },
                    "gaap_changes": {
                        "type": ["object", "null"],
                        "properties": {
                            "present": {"type": "boolean"},
                            "disproportionate_impact_qualifier": {"type": "boolean"}
                        }
                    },
                    "war_terrorism_disasters": {
                        "type": ["object", "null"],
                        "properties": {
                            "present": {"type": "boolean"},
                            "disproportionate_impact_qualifier": {"type": "boolean"}
                        }
                    },
                    "pandemic": {
                        "type": ["object", "null"],
                        "properties": {
                            "present": {
                                "type": "boolean",
                                "description": (
                                    "True if the definition carves out pandemics, epidemics, "
                                    "quarantine restrictions, public health emergencies, or "
                                    "similar language — even if the word 'pandemic' is not used"
                                )
                            },
                            "specific_covid_reference": {
                                "type": "boolean",
                                "description": (
                                    "True if the provision specifically names COVID-19, "
                                    "coronavirus, or SARS-CoV-2, OR if it uses epidemic/"
                                    "quarantine language in an agreement signed during 2020-2021 "
                                    "where the drafters clearly contemplated COVID"
                                )
                            },
                            "disproportionate_impact_qualifier": {"type": "boolean"}
                        }
                    },
                    "announcement_of_deal": {
                        "type": ["object", "null"],
                        "properties": {
                            "present": {"type": "boolean"},
                            "disproportionate_impact_qualifier": {"type": "boolean"}
                        }
                    },
                    "failure_to_meet_projections": {
                        "type": ["object", "null"],
                        "properties": {
                            "present": {"type": "boolean"},
                            "disproportionate_impact_qualifier": {"type": "boolean"}
                        }
                    },
                    "stock_price_changes": {
                        "type": ["object", "null"],
                        "properties": {
                            "present": {"type": "boolean"},
                            "disproportionate_impact_qualifier": {"type": "boolean"}
                        }
                    }
                }
            },
            "total_carveout_count": {
                "type": ["integer", "null"],
                "description": "Total number of MAE carve-outs/exclusions"
            },
            "source_sections": {"type": ["string", "null"]},
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"]
            }
        },
        "required": ["mae_applies_to", "includes_prospects", "carveouts",
                     "total_carveout_count", "source_sections", "confidence"]
    }
}

# ── Tool 4: Specific Performance ────────────────────────────────
SPECIFIC_PERFORMANCE_TOOL = {
    "name": "extract_specific_performance",
    "description": (
        "Extracts the specific performance provision from a merger agreement. "
        "This determines whether the parties can seek court-ordered enforcement "
        "rather than just monetary damages. Look in the general/miscellaneous "
        "provisions, typically one of the last articles."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "specific_performance_available": {
                "type": ["string", "null"],
                "enum": [
                    "entitled_to",
                    "may_seek",
                    "mutual_entitled_to",
                    "limited_to_one_party",
                    "not_available",
                    "other",
                    None
                ],
                "description": "Whether and how specific performance is available"
            },
            "available_to": {
                "type": ["string", "null"],
                "enum": ["both_parties", "target_only", "acquirer_only", "other", None]
            },
            "conditions_or_limitations": {
                "type": ["string", "null"],
                "description": "Any conditions or limitations on specific performance rights"
            },
            "source_sections": {"type": ["string", "null"]},
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"]
            }
        },
        "required": ["specific_performance_available", "available_to",
                     "source_sections", "confidence"]
    }
}

# All tools for multi-extraction pass
ALL_TOOLS = [
    TERMINATION_FEE_TOOL,
    EFFORTS_STANDARD_TOOL,
    MAC_DEFINITION_TOOL,
    SPECIFIC_PERFORMANCE_TOOL,
]