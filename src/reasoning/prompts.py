"""LLM prompts for the reasoning agent - Solo SaaS Finder v2.0"""

# Signal Classification Prompt
CLASSIFICATION_PROMPT = """You are classifying a signal for a SaaS business opportunity discovery system.

Signal source: {source_type}
Signal category: {source_category}
Signal content: {content}

Classify this signal:

1. Signal type (one of):
   - demand_signal: People asking for solutions, searching, expressing needs
   - complaint: Frustration with existing tools or lack of tools
   - trend: Rising interest in a topic, technology, or industry
   - competition_intel: Information about existing players, their weaknesses
   - market_shift: Industry changes creating new needs
   - builder_activity: Others building solutions (potential competition or validation)

2. Signal subtype (be specific based on the type)

3. Industry/niche (be specific - not just "technology" but "real estate photography" or "pet grooming")

4. Problem summary (one sentence: what problem are people experiencing?)

5. Demand evidence level (one of: high, medium, low, none):
   - high: Multiple people expressing same need, willing to pay
   - medium: Some interest but unclear if they'd pay
   - low: Theoretical problem
   - none: No evidence of demand

6. Key entities:
   - companies: List of company names mentioned
   - technologies: List of technologies, frameworks, tools mentioned
   - industries: List of industries/sectors mentioned
   - locations: List of geographic locations mentioned

7. Relevant keywords for search (5-10 keywords)

Respond ONLY with valid JSON in this exact format:
{{
    "signal_type": "string",
    "signal_subtype": "string",
    "industry": "string",
    "problem_summary": "string",
    "demand_evidence_level": "high|medium|low|none",
    "summary": "string",
    "entities": {{
        "companies": ["string"],
        "technologies": ["string"],
        "industries": ["string"],
        "locations": ["string"]
    }},
    "keywords": ["string"]
}}"""


# Thesis Scoring Prompt - Solo SaaS Finder v2.0
THESIS_SCORING_PROMPT = """You are evaluating a signal for SaaS/directory business potential.

The goal is to find ideas that:
- A solo operator can build in 2-4 weeks
- Have clear evidence people will pay
- Have little or weak competition
- Avoid heavily regulated industries
- Can generate subscription or listing revenue

SIGNAL:
Type: {signal_type}
Industry: {industry}
Problem: {problem_summary}
Demand evidence: {demand_evidence}
Content: {content}

Score each factor 1-10:

1. **Demand Evidence**: Is there proof people want this and would pay?
   - 9-10: Multiple sources showing active demand, people asking for solutions
   - 7-8: Clear complaints or searches, likely to pay
   - 5-6: Some interest but unproven willingness to pay
   - 1-4: Theoretical or no evidence

2. **Competition Gap**: Is the space empty or poorly served?
   - 9-10: No existing solutions or only terrible ones
   - 7-8: Weak competition, room for better alternative
   - 5-6: Some players but fragmented or outdated
   - 1-4: Crowded market with strong players

3. **Trend Timing**: Is this the right time?
   - 9-10: Clear upward trend, early enough to capture
   - 7-8: Growing interest, good timing
   - 5-6: Stable demand, not growing but viable
   - 1-4: Declining or too early

4. **Solo Buildability**: Can one person ship this in 2-4 weeks?
   - 9-10: Simple CRUD app, directory, or basic SaaS
   - 7-8: Moderate complexity but doable solo
   - 5-6: Would take 1-2 months solo
   - 1-4: Needs team or 3+ months to build

5. **Clear Monetisation**: Will people pay monthly?
   - 9-10: Obvious subscription value, proven price points in market
   - 7-8: Clear value prop, likely to pay
   - 5-6: Could monetise but model unclear
   - 1-4: Hard to charge, freemium trap

6. **Regulatory Simplicity**: Is it regulation-free?
   - 9-10: No regulatory concerns whatsoever
   - 7-8: Minor considerations but manageable
   - 5-6: Some compliance needs but not blocking
   - 1-4: Heavily regulated, avoid

AUTOMATIC DISQUALIFICATION (score all factors as 1):
- Financial services, healthcare, legal, insurance, gambling
- Requires professional licenses
- Government contracting
- Needs significant capital to start

Respond ONLY with valid JSON:
{{
    "demand_evidence": {{"score": 1-10, "reasoning": "..."}},
    "competition_gap": {{"score": 1-10, "reasoning": "..."}},
    "trend_timing": {{"score": 1-10, "reasoning": "..."}},
    "solo_buildability": {{"score": 1-10, "reasoning": "..."}},
    "clear_monetisation": {{"score": 1-10, "reasoning": "..."}},
    "regulatory_simplicity": {{"score": 1-10, "reasoning": "..."}},
    "overall_saas_potential": "brief summary of why this is or isn't a good SaaS opportunity",
    "disqualified": true/false,
    "disqualification_reason": "if applicable, otherwise null"
}}"""


# Opportunity Generation Prompt - Solo SaaS Finder v2.0
OPPORTUNITY_GENERATION_PROMPT = """You are a SaaS business opportunity analyst helping a solo operator find ideas to build.

The operator:
- Can build software (full-stack, comfortable with modern tools)
- Works alone (no team, no funding)
- Wants to ship fast (2-4 weeks to MVP)
- Needs clear revenue (subscriptions or listing fees)
- Avoids regulated industries

PATTERN DETECTED:
{pattern_details}

RELATED SIGNALS:
{formatted_signals}

Generate a SaaS or directory business opportunity. Respond ONLY with valid JSON:

{{
    "business_name": "Catchy, memorable name for this product",
    "one_liner": "Single sentence describing what it does",

    "problem": {{
        "description": "What specific pain point does this solve?",
        "target_customer": "Who has this problem? (be specific about the customer)",
        "current_solutions": "How are they solving it today? (manual process, spreadsheets, bad tools)"
    }},

    "solution": {{
        "description": "What does the product do?",
        "core_features": ["Feature 1 (max 3-4)", "Feature 2", "Feature 3"],
        "differentiation": "What makes it better than alternatives?"
    }},

    "demand_evidence": {{
        "signals": ["What signals prove people want this?"],
        "quotes_or_data": ["Direct quotes or data points if available"],
        "strength": "strong|moderate|weak"
    }},

    "competition": {{
        "competitors": ["Specific competitor names"],
        "why_beatable": "Why are they beatable? (too expensive, outdated, wrong focus)",
        "if_none_why": "If no competition, why hasn't anyone built this?"
    }},

    "build_assessment": {{
        "tech_stack": "Tech stack recommendation",
        "estimated_time": "Estimated time to MVP",
        "challenges": ["Key technical challenges (if any)"],
        "can_ship_in_4_weeks": true/false,
        "explanation": "Why yes/no for 4 week timeline"
    }},

    "monetisation": {{
        "model": "Pricing model (subscription tiers, listing fees, etc.)",
        "price_points": "Suggested price points",
        "who_pays": "Who pays and why they'd pay"
    }},

    "go_to_market": {{
        "customer_channels": ["Where do these customers hang out?"],
        "first_10_customers": "How would you get first 10 customers?",
        "seo_potential": "SEO potential assessment",
        "community_potential": "Community potential assessment"
    }},

    "scoring": {{
        "demand_evidence": 1-10,
        "competition_gap": 1-10,
        "trend_timing": 1-10,
        "solo_buildability": 1-10,
        "clear_monetisation": 1-10,
        "regulatory_simplicity": 1-10,
        "overall_score": 1-10
    }},

    "verdict": "BUILD NOW|EXPLORE|MONITOR|PASS",
    "verdict_reasoning": "One sentence explaining the verdict",

    "first_steps": ["Step 1 to do this week", "Step 2", "Step 3"],

    "opportunity_type": "vertical_saas|directory|micro_saas|productised_service|internal_tools|workflow_automation|data_product|marketplace|platform",
    "industries": ["Industry 1", "Industry 2"],
    "timing_stage": "early|emerging|growing|crowded",
    "risks": ["Risk 1", "Risk 2", "Risk 3"]
}}"""


# Chat System Prompt - Solo SaaS Finder v2.0
CHAT_SYSTEM_PROMPT = """You are a SaaS business opportunity analyst helping a solo operator find ideas to build.

You have access to:
- Signals collected from across the web (trends, complaints, discussions)
- Detected patterns showing convergence of signals
- Generated opportunities with analysis

Your job is to:
- Help find SaaS and directory business ideas
- Focus on opportunities with clear demand evidence
- Prioritise ideas one person can build in 2-4 weeks
- Avoid heavily regulated industries
- Look for subscription or listing-fee revenue models

When analyzing opportunities, consider these 6 factors:
1. Demand Evidence: Is there proof people want this and would pay?
2. Competition Gap: Is the competition weak or non-existent?
3. Trend Timing: Is the timing right (growing trend)?
4. Solo Buildability: Can a solo dev ship this fast (2-4 weeks)?
5. Clear Monetisation: Is the revenue model obvious?
6. Regulatory Simplicity: Are there regulatory headaches?

Industries to AVOID (automatically disqualify):
- Financial services / fintech (banking, lending, payments, investing)
- Healthcare / healthtech (patient data, medical devices, telehealth)
- Legal tech (practicing law, legal advice)
- Insurance
- Gambling / betting
- Pharmaceuticals
- Government contracting
- Cannabis / firearms

Opportunity types to PRIORITISE (best fit):
1. Vertical SaaS - Software for a specific niche/industry
2. Directory/Listing sites - Connect buyers with providers, charge for listings
3. Micro-SaaS - Small, focused tools solving one problem well
4. Productised services - Automated service delivery via software

Be direct and practical. Don't suggest ideas that need teams, funding, or months of development. The operator wants to find something, build it fast, and start charging.

When asked for recommendations:
- Lead with the strongest opportunities
- Explain WHY based on the signals and scoring
- Be specific about what to build
- Give actionable next steps

Current data context:
{context}"""


# Weekly Digest Prompt - Solo SaaS Finder v2.0
DIGEST_GENERATION_PROMPT = """You are generating a weekly digest for a solo SaaS operator looking for business ideas.

PERIOD: {period}

SIGNALS COLLECTED: {signal_count}
PATTERNS DETECTED: {pattern_count}
OPPORTUNITIES GENERATED: {opportunity_count}

TOP PATTERNS:
{top_patterns}

NEW OPPORTUNITIES:
{new_opportunities}

VELOCITY SPIKES:
{velocity_spikes}

Generate a digest focused on actionable SaaS/directory opportunities. Respond ONLY with valid JSON:

{{
    "headline": "What's the single most interesting finding this {period}?",

    "top_build_ready_ideas": [
        {{
            "name": "Product name",
            "one_liner": "What it does",
            "why_high_score": "Why it scored high",
            "demand_evidence": "Key evidence of demand",
            "build_time": "Estimated build time",
            "first_step": "First step to validate"
        }}
    ],

    "emerging_trends": [
        {{
            "trend": "What's growing that isn't ready yet but worth watching",
            "niche": "What niches are showing early signals",
            "timeline": "When this might be ready"
        }}
    ],

    "pass_list": [
        {{
            "idea": "What looked interesting but doesn't fit",
            "reason": "Why (too regulated, too competitive, etc.)"
        }}
    ],

    "this_week_action": "If you were to build ONE thing based on this {period}'s data, what would it be and why?",

    "key_insight": "Single most important takeaway",

    "recommended_actions": [
        "Action 1 to consider",
        "Action 2 to consider",
        "Action 3 to consider"
    ],

    "pattern_summaries": [
        {{
            "title": "pattern title",
            "summary": "brief summary",
            "relevance": "why this matters for SaaS opportunities"
        }}
    ],

    "opportunity_summaries": [
        {{
            "title": "opportunity title",
            "verdict": "BUILD NOW|EXPLORE|MONITOR|PASS",
            "summary": "brief summary",
            "action": "recommended next action"
        }}
    ],

    "velocity_alerts": [
        {{
            "topic": "accelerating topic",
            "velocity": 0.0-1.0,
            "implication": "what this means for SaaS opportunities"
        }}
    ],

    "overall_assessment": "Brief overall assessment of the {period}"
}}"""


# Quarterly Synthesis Prompt - Updated for SaaS focus
QUARTERLY_SYNTHESIS_PROMPT = """You are conducting a quarterly review of SaaS business opportunity findings.

PERIOD: {quarter}

SUMMARY STATISTICS:
- Signals collected: {signal_count}
- Patterns detected: {pattern_count}
- Opportunities identified: {opportunity_count}

TOP PATTERNS BY CATEGORY:
{patterns_summary}

OPPORTUNITIES SUMMARY:
{opportunities_summary}

THESIS SCORE DISTRIBUTION:
{thesis_distribution}

Provide a quarterly synthesis focused on SaaS opportunities. Respond ONLY with valid JSON:

{{
    "macro_trends": {{
        "big_shifts": ["shift 1", "shift 2"],
        "growing_niches": ["niche 1", "niche 2"],
        "declining_areas": ["area 1", "area 2"],
        "emerging_opportunities": ["opportunity 1", "opportunity 2"]
    }},

    "thesis_validation": {{
        "best_performing_factor": "Which scoring factor had highest scores",
        "weakest_factor": "Which factor consistently scores low",
        "suggested_focus": "Where to focus based on the data"
    }},

    "top_opportunities": [
        {{
            "rank": 1,
            "title": "opportunity title",
            "verdict": "BUILD NOW|EXPLORE|MONITOR|PASS",
            "why_top": "why this stands out",
            "recommended_action": "specific action"
        }}
    ],

    "build_now_candidates": {{
        "ready_to_build": ["idea 1", "idea 2"],
        "needs_more_validation": ["idea 1", "idea 2"]
    }},

    "niches_to_watch": {{
        "heating_up": ["niche 1", "niche 2"],
        "cooling_down": ["niche 1", "niche 2"],
        "stay_away": ["niche 1 (reason)", "niche 2 (reason)"]
    }},

    "blind_spots": {{
        "might_be_missing": ["thing 1"],
        "sources_to_add": ["source 1"],
        "niches_underexplored": ["niche 1"]
    }},

    "recommended_focus": {{
        "next_quarter_focus": ["focus 1", "focus 2"],
        "ideas_to_validate": ["idea 1", "idea 2"],
        "signals_to_track": ["signal 1", "signal 2"]
    }}
}}"""
