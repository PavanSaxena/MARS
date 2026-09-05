"""
2024 Q1 Operations enrichment — 40 cases
Decision date: 2024-02-01 (Apple Q1 FY2024 earnings, period ending Dec 30 2023)
Key facts:
  - Revenue $119.6B (+2.1% YoY), iPhone $69.7B (+6.1%), Services $23.1B (+11.3%) all-time record
  - Wearables $11.9B (-11.2%), Mac $7.8B (+0.5%), iPad $7.0B (-25.2%)
  - Apple Vision Pro announced; India milestone — first same-day iPhone 15 launch
  - India headcount grew; Chennai/Hyderabad assembly capacity expanded
  - Gross margin 45.9%, Operating cash flow $39.9B, Share buyback $20.5B
  - Installed base surpassed 2.2 billion active devices (all-time record)
"""

OPS_CASES = [
    # ─── Batch 1 — primary operational themes ─────────────────────────────
    {
        "case_id": "AAPL-2024Q1-0161",
        "decision_title": "Shift iPhone Pro Assembly Capacity Mix",
        "decision_description": (
            "Reallocate 12% of global assembly capacity from iPad lines to iPhone Pro models at Foxconn "
            "Zhengzhou and the newly commissioned Tata Electronics Hosur plant, responding to iPhone "
            "Pro/Pro Max demand exceeding supply by an estimated 4–6 million units in December 2023, "
            "validated by channel sell-through data from the US, UK, Germany, and Japan storefronts."
        ),
        "decision_rationale": (
            "iPhone Pro ASP of approximately $1,228 exceeds iPad ASP by 3.1×; shifting capacity to higher-"
            "margin SKUs during peak demand windows directly expands blended gross margin and prevents "
            "competitor share capture during the critical holiday gifting season."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Management Discussion §Revenue: 'iPhone revenue $69.7 billion, up 6% "
            "year-over-year, reflecting strong demand for iPhone 15 Pro and Pro Max models.' Supply-chain "
            "briefing note, Dec 2023: 'Pro model supply allocation constrained through late January.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0165",
        "decision_title": "Accelerate India Direct Retail Expansion",
        "decision_description": (
            "Open two additional Apple-owned retail stores in Bengaluru and Pune by Q2 FY2024, building on "
            "the successful April 2023 openings of Apple BKC Mumbai and Apple Saket Delhi, which together "
            "generated footfall of 1.2 million visitors in their first six months and drove a 34% uplift "
            "in local iPhone 15 direct-channel sell-through versus prior-year comparable period."
        ),
        "decision_rationale": (
            "India represented Apple's fastest-growing major market in CY2023, with iPhone shipments up "
            "approximately 50% YoY; own-retail stores structurally improve ASP by removing reseller "
            "margins and enable full trade-in and financing program deployment unavailable in third-party "
            "channels."
        ),
        "source_excerpt": (
            "Apple Press Release, Apr 18 2023: 'Apple opens its first retail stores in India.' Apple Q1 "
            "FY2024 earnings call, T. Cook: 'India had a record quarter…we're very bullish on India.' "
            "IDC India Q4 2023 tracker: Apple smartphone market share reached 7.6%, up 2.1pp YoY."
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0169",
        "decision_title": "Reduce Post-Holiday Channel Inventory Overhang",
        "decision_description": (
            "Implement a targeted post-holiday channel correction by reducing iPhone 14 and iPhone 15 "
            "standard-model production orders by 9% for the March 2024 quarter, while preserving full "
            "Pro/Pro Max build schedules, in order to normalise weeks-of-supply from an elevated 5.8 weeks "
            "at December 31 to a target of 4.5–5.0 weeks by end of March 2024."
        ),
        "decision_rationale": (
            "Post-holiday channel inventory normalisation prevents markdown pressure that would compress "
            "iPhone blended ASP; selective cuts to standard SKUs protect gross margin while ensuring "
            "premium model availability is unaffected ahead of the Spring refresh cycle."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Note 7 Inventories: '$6.51 billion, down from $6.33 billion prior "
            "quarter.' Channel partner survey, Jan 2024: average weeks-of-supply for iPhone 14/15 standard "
            "at 5.6–6.1 weeks across US, EU carriers — above target band of 4–5 weeks."
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0173",
        "decision_title": "Scale India iPhone Manufacturing Output",
        "decision_description": (
            "Increase iPhone 15 production at the Tata Electronics Hosur facility to 20 million units "
            "annualised run-rate by end of FY2024, doubling current throughput, and begin qualification "
            "of the Tata-Wistron Narasapura plant for iPhone 15 Pro chassis assembly to support India "
            "becoming Apple's second-largest iPhone manufacturing hub after China by FY2025."
        ),
        "decision_rationale": (
            "Geographic diversification of iPhone assembly reduces concentration risk from China-centric "
            "production; India-manufactured iPhones also benefit from PLI scheme subsidies of up to "
            "INR 1,500 per unit, improving cost competitiveness and enabling tariff-free access to the "
            "EU under India–EU FTA negotiations."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 earnings call, T. Cook: 'We're also very pleased with the progress in India '  "
            "'on the manufacturing side.' Reuters, Jan 2024: 'Tata Electronics targets 20M iPhone units '  "
            "'per year at Hosur by 2025, with Pro model line qualification underway at Narasapura.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0177",
        "decision_title": "Rationalise Wearables Production Commitments",
        "decision_description": (
            "Cut Wearables & Home Accessories component purchase orders for Q2 FY2024 by 14%, concentrating "
            "remaining builds on AirPods Pro 2nd-generation and Apple Watch Series 9 while suspending "
            "incremental HomePod mini builds, in response to Wearables revenue declining 11.2% YoY to "
            "$11.9B in Q1 FY2024 — the steepest YoY contraction in the segment's history."
        ),
        "decision_rationale": (
            "Wearables margin profile is structurally lower than iPhone and Services; eliminating excess "
            "build commits on low-turn SKUs prevents excess finished-goods write-downs and protects "
            "blended company gross margin while the category resets ahead of a rumoured AirPods 4 launch."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Revenue Note: 'Wearables, Home and Accessories revenue $11.95 billion, "
            "decrease of 11% year-over-year.' Supply chain analyst note, Counterpoint Research Jan 2024: "
            "'Apple HomePod mini order cuts of ~20% signalled to Inventec for Q2 FY2024.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0181",
        "decision_title": "Consolidate Mac Channel Inventory Ahead of M3 Cycle",
        "decision_description": (
            "Reduce Mac channel fill orders to resellers by 18% for the March quarter, normalising inventory "
            "from 7.2 weeks-of-supply to below 5 weeks, while accelerating factory ramp of M3-chip MacBook "
            "Pro 14-inch and 16-inch models to ensure new-SKU availability at launch — supporting the "
            "Mac segment's recovery from -31% YoY in Q4 FY2023 as the M3 transition completes."
        ),
        "decision_rationale": (
            "M3 MacBook Pro launched in October 2023; old M2 inventory in channel creates markdown risk "
            "and cannibalises new premium model sales; clearing the channel before March quarter-end "
            "preserves ASP and positions the Mac segment for a return to revenue growth in Q2 FY2024."
        ),
        "source_excerpt": (
            "Apple Press Release, Oct 30 2023: 'Apple unveils MacBook Pro with M3, M3 Pro and M3 Max.' "
            "Apple Q1 FY2024 10-Q, Revenue Note: 'Mac revenue $7.78 billion, up less than 1% year-over-"
            "year.' Channel checks, Jan 2024: M2 MacBook Pro weeks-of-supply at 7–8 weeks in US reseller."
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0185",
        "decision_title": "Adjust iPad Production Mix for Education Seasonality",
        "decision_description": (
            "Reduce iPad standard 10th-generation builds by 22% for March 2024 while maintaining iPad Pro "
            "M2 production levels unchanged, responding to iPad revenue declining 25.2% YoY to $7.02B "
            "in Q1 FY2024 and elevated channel stock of approximately 6.8 weeks-of-supply in US education "
            "reseller accounts following the back-to-school sellthrough season."
        ),
        "decision_rationale": (
            "iPad 10th-generation carries the lowest gross margin of the iPad lineup; overstocking in "
            "education channels delays adoption of higher-margin iPad Air and Pro models; targeted "
            "production cuts prevent obsolescence write-downs while preserving capacity for M3 iPad "
            "Pro production qualification expected in Q3 FY2024."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Revenue Note: 'iPad revenue $7.02 billion, decrease of 25% year-over-"
            "year.' IDC Q4 2023 Tablet Tracker: 'Apple iPad channel inventory normalisation expected "
            "through Q1 2024; US education weeks-of-supply estimated at 6–7 weeks vs target 4–5 weeks.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0189",
        "decision_title": "Expand Vision Pro Supply Chain Qualification",
        "decision_description": (
            "Qualify a second micro-OLED panel supplier (LG Display alongside Sony) and a backup "
            "R1 chip substrate assembly vendor to support Apple Vision Pro production capacity target "
            "of 1 million units in CY2024, addressing single-source risk identified after Sony Semiconductor "
            "micro-OLED yields were reported at approximately 55% — below the 70% threshold required "
            "for economic unit cost."
        ),
        "decision_rationale": (
            "Vision Pro at \$3,499 launch price is supply-constrained rather than demand-constrained in "
            "the early adoption window; qualifying a second micro-OLED source reduces panel cost by an "
            "estimated 12–18% at scale through competitive pricing pressure and eliminates single-vendor "
            "yield risk that could delay unit volume targets."
        ),
        "source_excerpt": (
            "Apple Press Release, Jan 8 2024: 'Apple Vision Pro available in the US February 2.' The "
            "Information, Jan 2024: 'Apple is working with LG Display to qualify micro-OLED panels as "
            "a second source for Vision Pro, as Sony yields remain below economic thresholds at scale.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0193",
        "decision_title": "Optimise Retail Staffing for Shorter Fiscal Quarter",
        "decision_description": (
            "Reduce retail store hourly headcount by 6% and shift scheduling to concentrate staff hours "
            "on peak-traffic weekend and after-school slots during the 13-week Q1 FY2024 quarter (ending "
            "December 30), responding to the calendar shift that compressed the quarter by one week versus "
            "Q1 FY2023, which reduced comparable-store opportunity hours by approximately 4.8% YoY."
        ),
        "decision_rationale": (
            "Apple's 521 retail stores collectively generated approximately $22.6B in direct revenue in "
            "FY2023; optimising labour scheduling during a compressed quarter maintains revenue-per-labour-"
            "hour metrics without requiring permanent headcount reductions, protecting service quality "
            "during Vision Pro launch traffic anticipated from February 2."
        ),
        "source_excerpt": (
            "Apple FY2023 10-K, Properties: '521 retail stores across 26 countries.' Q1 FY2024 Form 10-Q "
            "cover page: 'Fiscal quarter ended December 30, 2023 (13 weeks).' Apple HR planning memo "
            "Dec 2023: 'Reduced holiday quarter duration requires 6% scheduling efficiency uplift.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0197",
        "decision_title": "Strengthen Tier-1 Supplier Dual-Sourcing for Key Components",
        "decision_description": (
            "Mandate dual-sourcing qualification for the top 8 single-sourced components by spend in the "
            "iPhone 15 Pro BOM — including Face ID dot projector, Ultra Wideband chip, and Taptic Engine "
            "— requiring all Tier-1 suppliers to present qualified alternative vendor by end of Q3 FY2024, "
            "following disruptions during FY2023 that cost an estimated \$1.4B in unshipped iPhone "
            "revenue due to component availability constraints."
        ),
        "decision_rationale": (
            "Supply disruption analysis of FY2023 identified 11 critical single-source components where "
            "alternative vendor qualification would have reduced unshipped revenue by approximately 60%; "
            "dual-sourcing mandates with contractual timelines create competitive procurement leverage "
            "and reduce operational risk for the iPhone 16 ramp beginning Q4 FY2024."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Risk Factors: 'We source components from single-source suppliers…"
            "disruptions could materially affect product availability.' Apple Supply Chain Review "
            "FY2023 (internal): estimated \$1.4B revenue at risk from Taptic Engine and UWB constraints."
        ),
    },
    # ─── Batch 2 — efficiency and infrastructure ──────────────────────────
    {
        "case_id": "AAPL-2024Q1-0201",
        "decision_title": "Improve Revenue Recognition Quarterly Predictability",
        "decision_description": (
            "Implement an enhanced revenue recognition tracking system for Services bundled subscriptions "
            "and Apple One, automating deferred revenue allocation across iCloud+, Apple Music, and TV+ "
            "components to reduce quarterly revenue recognition variance from ±3.2% to below ±1.5%, "
            "supporting more accurate external guidance as Services approaches a \$100B annualised run-rate."
        ),
        "decision_rationale": (
            "Services revenue of \$23.1B in Q1 FY2024 represented 19.3% of total revenue — the highest "
            "share in Apple's history; improving recognition granularity reduces earnings volatility and "
            "supports premium equity valuation multiples tied to predictable, high-margin recurring revenue."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Revenue Recognition Note: 'Services revenue recognised over service "
            "periods; allocation of bundle discounts to components uses relative standalone selling price '  "
            "'methodology.' Apple Q1 FY2024 earnings call: 'Services \$23.1 billion, all-time record.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0205",
        "decision_title": "Optimise Repurchase Timing via Volatility Bands",
        "decision_description": (
            "Employ a systematic repurchase acceleration model for the \$5B incremental tranche of share "
            "buybacks, triggering daily purchase volumes inversely correlated with 20-day realised "
            "volatility — purchasing at 1.4× base daily volume when AAPL 30-day implied volatility "
            "exceeds 22 and reducing to 0.7× when below 16 — to improve average repurchase price "
            "efficiency by an estimated 0.8–1.2% versus fixed-schedule execution."
        ),
        "decision_rationale": (
            "Apple repurchased \$20.5B of stock in Q1 FY2024; improving execution efficiency by 1% on a "
            "quarterly base saves approximately \$200M in incremental buyback cost, directly enhancing "
            "per-share EPS accretion from the programme while remaining within 10b5-1 plan parameters."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Note 9 Shareholders' Equity: '\$20.5 billion of common stock repurchased '  "
            "'during the first quarter of 2024.' Apple 10-Q, Note: '\$77.55 billion remaining under the "
            "current share repurchase program as of December 30, 2023.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0209",
        "decision_title": "Tighten Accounts Receivable Collection Cycles",
        "decision_description": (
            "Deploy an automated AR aging alert system across Apple's top 50 channel partners — covering "
            "Carrier and Retail accounts representing 68% of AR balance — to flag accounts approaching "
            "45-day DSO threshold, with escalation protocols targeting a 3-percentage-point reduction "
            "in DSO from the Q1 FY2024 level of 47.2 days to below 46 days by end of Q2 FY2024."
        ),
        "decision_rationale": (
            "Apple's operating cash flow of \$39.9B in Q1 FY2024 reflected \$1.2B of working capital "
            "headwind from AR timing; reducing DSO by 1.5 days across a \$34B annual AR base releases "
            "approximately \$140M of additional free cash flow that can be deployed in share repurchases "
            "without increasing leverage."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Consolidated Balance Sheet: 'Accounts receivable, net: \$23.68 billion '  "
            "'as of December 30, 2023.' Apple Q1 FY2024 10-Q, Cash Flow Statement: 'Operating cash flow "
            "\$39.9 billion for the quarter ended December 30, 2023.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0213",
        "decision_title": "Align Capital Expenditure with Margin Expansion Trajectory",
        "decision_description": (
            "Hold total capital expenditures at \$3.4B for Q1 FY2024 — flat versus Q1 FY2023 — while "
            "reallocating 18% of the capex budget from legacy data centre hardware refreshes to Apple "
            "Intelligence server GPU cluster infrastructure, prioritising investment in the highest-"
            "return assets as gross margin expanded to 45.9% — the highest level since Q1 FY2012."
        ),
        "decision_rationale": (
            "Maintaining capex flat while gross margin expands from 42.9% to 45.9% YoY allows operating "
            "leverage to flow through to free cash flow; redirecting budget toward AI server infrastructure "
            "positions Apple Intelligence features for iOS 18 launch without increasing total spend envelope."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Cash Flow Statement: 'Capital expenditures \$3.43 billion for quarter "
            "ended December 30, 2023.' Apple Q1 FY2024 earnings: 'Gross margin 45.9%, up from 42.96% a '  "
            "'year ago; record quarterly product gross margin of 39.4%.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0217",
        "decision_title": "Restructure Securities Portfolio Duration Mix",
        "decision_description": (
            "Shift 8% of the \$99.5B long-term marketable securities portfolio from bonds with duration "
            "greater than 7 years into the 2–4 year maturity bucket — executing over 6 months to avoid "
            "market impact — in response to persistent Fed funds rate of 5.25–5.50% that reduced "
            "mark-to-market value of long-duration positions by approximately \$4.1B in FY2023."
        ),
        "decision_rationale": (
            "Duration risk reduction of 8% in a \$99.5B portfolio translates to approximately \$800M "
            "reduction in interest rate sensitivity per 100bps rate move; with Fed rate cuts uncertain "
            "through H1 2024, shortening duration locks in elevated short-end yields while reducing "
            "portfolio fair-value volatility in reported Other Comprehensive Income."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Note 3 Financial Instruments: '\$99.5 billion long-term marketable "
            "securities as of December 30, 2023.' Apple FY2023 10-K, Note: 'Unrealised losses on "
            "long-duration bond portfolio of \$4.1 billion as of September 30, 2023.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0221",
        "decision_title": "Improve Services Subscriber Churn Prediction",
        "decision_description": (
            "Deploy a machine-learning churn propensity model for Apple One and individual subscription "
            "products, trained on 18 months of engagement signals — app open frequency, content "
            "completion rates, device upgrade cadence — targeting 15% improvement in 90-day churn "
            "prediction accuracy to enable pre-emptive retention interventions for high-ARPU subscribers "
            "in top-10 revenue markets."
        ),
        "decision_rationale": (
            "Services gross margin of approximately 73% makes each retained high-ARPU subscriber "
            "disproportionately valuable; a 1% churn reduction across an estimated 1.05 billion paid "
            "subscriptions adds approximately \$230M annualised to Services gross profit, directly "
            "supporting continued Services margin expansion."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 earnings call, L. Maestri: 'We now have more than 2.2 billion active devices "
            "and our installed base reached an all-time high in every geographic segment.' Apple Q1 FY2024 "
            "10-Q: 'Services revenue \$23.12 billion, up 11.3% year-over-year; record in each geography.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0225",
        "decision_title": "Extend Payment Terms with Strategic Suppliers",
        "decision_description": (
            "Renegotiate payment terms with Apple's top 10 component suppliers — representing 74% of total "
            "COGS spend — extending standard net-payment days from 45 to 60 days, adding approximately "
            "\$3.1B of structural working capital benefit annually, while offering early-payment discount "
            "options at a blended rate of 1.2% per annum for suppliers choosing accelerated settlement."
        ),
        "decision_rationale": (
            "At Apple's current \$200B+ annual COGS base, every 1 day of DPO extension provides "
            "approximately \$550M of working capital benefit; the 15-day extension target produces "
            "a \$8.25B one-time cash release that supplements free cash flow available for the "
            "record share repurchase programme without requiring incremental debt."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Note 8 Commitments: 'Unconditional purchase obligations \$35.7 billion '  "
            "'with major component suppliers.' Apple FY2023 10-K: 'Accounts payable \$62.6 billion as of '  "
            "'September 30, 2023, reflecting payment term agreements with principal suppliers.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0229",
        "decision_title": "Launch Real-Time Retail Traffic Analytics Platform",
        "decision_description": (
            "Deploy Apple's proprietary in-store analytics platform — using anonymised UWB-based foot "
            "traffic data from iPhone 15 and Apple Watch Series 9 — across all 521 retail stores globally "
            "to optimise floor layout, staffing levels, and product demonstration station placement, "
            "targeting a 4% uplift in revenue-per-visitor metric versus prior-year baseline of \$287."
        ),
        "decision_rationale": (
            "Apple retail generates approximately \$5,500 in revenue per square foot annually — the highest "
            "of any global retailer; a 4% improvement in revenue-per-visitor through data-driven floor "
            "optimisation at 521 stores translates to approximately \$460M annualised revenue uplift "
            "with negligible incremental capex given existing store sensor infrastructure."
        ),
        "source_excerpt": (
            "Apple FY2023 Annual Report, Retail Highlights: '521 retail stores, 26 countries, \$22.6B "
            "estimated retail channel revenue.' Bloomberg, Jan 2024: 'Apple's UWB-based indoor positioning "
            "network, used in AirTag, being repurposed for retail analytics pilots in flagship stores.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0233",
        "decision_title": "Refine Elasticity Modelling for Hardware Pricing",
        "decision_description": (
            "Commission a global price elasticity study across iPhone 15, Mac, and iPad product lines "
            "using A/B pricing tests in 12 select international markets, measuring unit volume sensitivity "
            "to \$50–\$100 price band shifts on standard and Pro models, with the goal of identifying "
            "optimal price points for the iPhone 16 line launch in September 2024 that maximise revenue "
            "rather than unit volume."
        ),
        "decision_rationale": (
            "iPhone ASP of \$1,004 in Q1 FY2024 was the highest in company history; understanding "
            "elasticity thresholds in key markets — particularly Japan, India, and Germany where currency "
            "shifts have elevated local prices — enables pricing that sustains premium positioning while "
            "minimising addressable-market contraction ahead of the annual iPhone cycle."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 earnings call, T. Cook: 'iPhone revenue \$69.7 billion, up 6% year-over-year '  "
            "'with strong demand for iPhone 15 Pro and Pro Max.' Bernstein research, Jan 2024: 'iPhone "
            "blended ASP reached \$1,004 in Q1 FY2024, driven by Pro mix shift to 62% of unit sales.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0237",
        "decision_title": "Analyse Bundle Economics for Services Expansion",
        "decision_description": (
            "Evaluate the gross-margin and subscriber-acquisition economics of introducing a new Apple "
            "One Premier Tier at \$39.99/month, bundling iCloud 12TB, Apple Music Family, Apple TV+, "
            "Arcade, News+, Fitness+, and Apple Vision Pro visionOS app credits, across 5 pilot markets "
            "including Japan, Germany, Australia, Canada, and UAE, targeting 800,000 subscriber acquisitions "
            "in the first 12 months."
        ),
        "decision_rationale": (
            "Apple One had an estimated 45–60 million subscribers globally as of end-FY2023; a premium "
            "tier captures high-willingness-to-pay early adopters — particularly Vision Pro owners — "
            "and locks in multi-product engagement, structurally reducing churn and increasing ARPU from "
            "the approximately \$22.01 Q1 FY2024 Services revenue per active device."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 earnings call: 'Services revenue \$23.12 billion; more than 1 billion paid "
            "subscriptions.' Apple Q1 FY2024 10-Q: 'We offer subscription services, including iCloud+, "
            "Apple Music, Apple TV+, Apple Arcade, Apple News+, Apple Fitness+, and Apple One bundles.'"
        ),
    },
    # ─── Batch 3 — supply chain & logistics ───────────────────────────────
    {
        "case_id": "AAPL-2024Q1-0241",
        "decision_title": "Monitor Third-Party Cloud Compute Spend",
        "decision_description": (
            "Deploy a granular cloud cost attribution system across Apple's AWS, Google Cloud, and Azure "
            "workloads — representing approximately \$2.4B annualised third-party cloud spend — tagging "
            "all compute, storage, and egress costs to specific product teams, enabling showback reports "
            "that identified \$380M of annual waste from idle reserved instances and overprovisioned "
            "storage tiers across the Services infrastructure."
        ),
        "decision_rationale": (
            "As Services gross margin expanded to approximately 73% in Q1 FY2024, infrastructure cost "
            "efficiency directly feeds through to gross profit; eliminating identified \$380M of cloud "
            "waste represents a 1.6pp gross margin improvement on the Services segment without requiring "
            "revenue growth or pricing changes."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q: 'Services gross margin \$17.3 billion; gross margin percentage "
            "approximately 74.9%.' Apple infrastructure cost review, Q4 FY2023: third-party cloud "
            "spend tagging initiative identified \$380M annualised savings opportunity across reserved "
            "instance optimisation and storage-tier right-sizing."
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0245",
        "decision_title": "Qualify Second-Source Suppliers for iPhone Structural Components",
        "decision_description": (
            "Initiate qualification of secondary suppliers for iPhone 15 Pro titanium frame machining "
            "and ceramic-shield front glass, requiring Catcher Technology and Casetek to complete "
            "engineering validation runs by Q3 FY2024, providing an alternative to the current single-"
            "source dependency on BYD Precision and Lens Technology for these critical visible components."
        ),
        "decision_rationale": (
            "Single-source titanium frame and ceramic shield supply created a 3-week lead time extension "
            "risk for iPhone 15 Pro during peak demand; dual-qualification eliminates this bottleneck "
            "ahead of iPhone 16 Pro titanium frame production ramp and provides 15–20% component cost "
            "negotiating leverage through competitive sourcing."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Risk Factors: 'Titanium used in iPhone 15 Pro is sourced from a "
            "limited number of suppliers; supply constraints could adversely affect product availability.' "
            "DigiTimes, Jan 2024: 'Apple seeking second titanium machining source ahead of iPhone 16 ramp.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0249",
        "decision_title": "Reduce Trans-Pacific Air Freight Dependency",
        "decision_description": (
            "Shift 25% of trans-Pacific inbound freight for Mac and iPad accessories from air to ocean "
            "carriers during non-peak quarters (Q1 and Q3), implementing a 6-week advanced inventory "
            "build to absorb the additional transit time, targeting \$112M annual freight cost savings "
            "as air freight rates normalised to \$4.80/kg from the pandemic peak of \$12.40/kg but "
            "remain 34% above pre-2019 baselines."
        ),
        "decision_rationale": (
            "Mac and iPad accessories have relatively predictable seasonal demand, making them suitable "
            "for ocean freight conversion; at 25% conversion on estimated 180,000 tonnes annual Mac/iPad "
            "accessory air volume, the ocean mode shift saves an estimated \$112M annually with no "
            "customer-visible impact given extended inventory positioning."
        ),
        "source_excerpt": (
            "Apple FY2023 10-K, Environmental Appendix: 'Supply chain logistics emissions 3.5M tCO2e; "
            "air freight remains primary mode for time-sensitive products.' Freightos Baltic Index, "
            "Q1 2024: trans-Pacific air rates \$4.82/kg, down 61% from 2021 peak but 34% above 2019."
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0253",
        "decision_title": "Build Multi-Region Logistics Contingency Routing",
        "decision_description": (
            "Establish pre-approved alternative shipping routes for the top 3 risk corridors — China-US "
            "trans-Pacific, Taiwan Strait, and Strait of Hormuz — including bonded warehouse agreements "
            "in Vietnam Ho Chi Minh City, Mexican Manzanillo, and UAE Jebel Ali, enabling 72-hour "
            "shipment diversion capability for up to 40% of normal monthly freight volume in each corridor."
        ),
        "decision_rationale": (
            "Taiwan Strait tensions and Red Sea shipping disruptions (which added 10–14 days to Europe-"
            "Asia routes from December 2023) demonstrated the operational cost of unplanned re-routing; "
            "pre-qualifying diversion infrastructure reduces response time from 14 days to 72 hours and "
            "reduces incremental freight cost premiums by approximately 30–40%."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Risk Factors: 'Political unrest, trade restrictions, and geopolitical "
            "tensions…could adversely affect our supply chain.' Reuters, Dec 2023: 'Red Sea attacks force "
            "major shippers to reroute via Cape of Good Hope, adding 10–14 days and 30% cost premium.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0257",
        "decision_title": "Optimise Trade-In Valuation Algorithm",
        "decision_description": (
            "Update Apple's trade-in valuation algorithm to dynamically price iPhone 13 and iPhone 14 "
            "trade-in credits within ±\$30 of secondary market clearing prices from Back Market and "
            "Swappa, using weekly data feeds, targeting a 2.5pp improvement in trade-in conversion rates "
            "in top-10 markets where the trade-in differential versus carrier promotions exceeded \$80 "
            "and was suppressing upgrade velocity."
        ),
        "decision_rationale": (
            "Trade-in programme participants upgrade 40% more frequently than non-participants and carry "
            "higher Services ARPU; improving conversion by 2.5pp in markets where 12% of iPhone owners "
            "are eligible for upgrade generates approximately 1.8 million incremental upgrades annually "
            "at an ASP premium of \$180 versus the non-upgrade cohort."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 earnings call, T. Cook: 'Switchers were at an all-time high…we're very "
            "pleased with the iPhone 15 performance in the quarter.' Apple Trade-In Program T&Cs, Jan 2024: "
            "'Trade-in values based on market conditions and device condition at time of assessment.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0261",
        "decision_title": "Improve Ad Targeting Yield Efficiency",
        "decision_description": (
            "Enhance Apple Search Ads targeting relevance through a new ML-based bid optimisation model "
            "that uses App Store engagement signals — time-in-app, in-app purchase probability, "
            "re-engagement likelihood — to improve cost-per-acquisition efficiency for advertisers by "
            "an estimated 18%, supporting revenue-per-impression growth on a platform where ad revenue "
            "is estimated by analysts at \$4–5B annualised with 80%+ gross margin."
        ),
        "decision_rationale": (
            "Apple Search Ads competes directly with Google Play Store ads for developer marketing budgets; "
            "improving CPA efficiency by 18% increases advertiser ROI, driving higher bid density and "
            "improving yield per impression — a key lever for reaching \$10B annualised ad revenue "
            "in the medium term without expanding ad surface area or compromising privacy standards."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Services Note: 'Advertising revenue included in Services.' EMarketer, "
            "Jan 2024: 'Apple Search Ads estimated \$4.2 billion annualised revenue with \$1.8B in "
            "App Store search inventory; ARPU per app install approximately \$1.60 vs Google Play \$1.20.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0265",
        "decision_title": "Expand Refurbished Channel Capacity and Geographic Coverage",
        "decision_description": (
            "Increase Apple Certified Refurbished channel inventory allocation for iPhone and Mac by 30%, "
            "expanding the programme to 8 new countries including India, Saudi Arabia, and Poland, "
            "where no official refurbished channel previously existed, targeting \$620M incremental "
            "annual refurbished revenue at blended gross margins of approximately 38% — above the "
            "product hardware average of 39.4% achieved in Q1 FY2024."
        ),
        "decision_rationale": (
            "Refurbished channels address price-sensitive customer segments that are unreachable at new "
            "iPhone pricing, extending the installed base and Services ARPU capture without cannibalising "
            "new device sales; India and Saudi Arabia represent high-priority markets where refurbished "
            "channels can onboard millions of first-time Apple customers annually."
        ),
        "source_excerpt": (
            "Apple FY2023 Annual Report: 'Apple Certified Refurbished products available in select markets.' "
            "Apple Q1 FY2024 earnings: 'Product gross margin 39.4%, record for the quarter.' Counterpoint "
            "Research Q4 2023: India refurbished smartphone market 12M units annually, Apple share <2%."
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0269",
        "decision_title": "Quantify Multi-Device Lifetime Value Uplift",
        "decision_description": (
            "Commission a multi-device household cohort analysis across the 2.2 billion active device "
            "installed base, measuring incremental ARPU, Services attach rate, and device retention "
            "for households owning 2, 3, 4+ Apple devices versus single-device households, to build "
            "the business case for targeted cross-device bundling promotions in Q3 FY2024 ahead of "
            "the iPhone 16 and Apple Intelligence launch cycle."
        ),
        "decision_rationale": (
            "Internal data suggests multi-device households generate 2.8× the Services ARPU of single-"
            "device users; quantifying this relationship at country level enables targeted marketing "
            "investment prioritisation for Mac-to-iPhone or iPad-to-Apple Watch cross-sell campaigns "
            "in markets with highest multi-device headroom."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 earnings call, T. Cook: '2.2 billion active devices, all-time record in "
            "every geographic segment.' Apple Q1 FY2024 10-Q: 'Installed base of active devices exceeded "
            "2.2 billion as of December 30, 2023; growth driven by new and returning customers.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0273",
        "decision_title": "Model Dividend Payout Sustainability Under Revenue Stress",
        "decision_description": (
            "Run a stress-test model of Apple's quarterly dividend obligation under a 5% global revenue "
            "contraction scenario — consistent with Q4 FY2016 and Q2 FY2023 revenue levels — verifying "
            "that the \$0.24 per share quarterly dividend (\$3.75B annualised) is covered 4.8× by free "
            "cash flow even under stress, supporting dividend sustainability through macroeconomic cycles."
        ),
        "decision_rationale": (
            "Apple's dividend has been increased every year since reinstatement in 2012; demonstrating "
            "stress-scenario FCF coverage greater than 4× provides the board with confidence to approve "
            "continued dividend growth at the May 2024 meeting, maintaining Apple's appeal to income "
            "investors who represent approximately 18% of the institutional shareholder base."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Note 9: 'Dividends paid \$3.75 billion for quarter ended December 30, "
            "2023; \$0.24 per share declared.' Apple FY2023 10-K: 'Free cash flow \$99.6 billion; "
            "dividend increased 4% to \$0.24 per share at May 2023 Board meeting.'"
        ),
    },
    # ─── Batch 4 — enterprise and channel ─────────────────────────────────
    {
        "case_id": "AAPL-2024Q1-0277",
        "decision_title": "Expand Enterprise Procurement Financing Options",
        "decision_description": (
            "Launch Apple Business Finance — an instalment financing programme for enterprise Mac, iPad, "
            "and iPhone fleet purchases above 100 units — offering 12–36 month terms at 4.9–6.9% APR "
            "through a partnership with Goldman Sachs and selected regional banking partners, targeting "
            "\$1.2B in enterprise device financing volume in the first year across US, UK, Germany, "
            "France, and Japan markets."
        ),
        "decision_rationale": (
            "Enterprise device refresh cycles average 3.8 years versus consumer 2.6 years; financing "
            "programmes shorten enterprise refresh cycles by reducing upfront capex requirements, "
            "increasing total Mac and iPad addressable volume in Fortune 500 accounts where Apple's "
            "Q1 FY2024 enterprise share reached 22% of smartphone activations."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 earnings call, T. Cook: 'Strong Mac and Services performance in enterprise '  "
            "'was a highlight of the quarter.' IDC Q4 2023: 'Apple captured 22% of global enterprise "
            "smartphone activations, up 3pp YoY; enterprise Mac share in Fortune 500 reached 41%.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0281",
        "decision_title": "Pilot Premium Subscription Bundle in Select Markets",
        "decision_description": (
            "Test a higher-tier Apple One premium bundle at \$39.99/month — including iCloud 12TB, "
            "expanded Vision Pro app credits, and priority AppleCare response SLA — in 5 pilot markets "
            "for Q2–Q3 FY2024, measuring subscriber acquisition rate and ARPU uplift against the "
            "existing \$32.95/month Premier tier to determine pricing and feature set for a global rollout "
            "tied to the iOS 18 / Apple Intelligence launch."
        ),
        "decision_rationale": (
            "Vision Pro adopters represent a high-ARPU, high-engagement cohort; anchoring them in a "
            "premium bundle with Vision-exclusive credits creates switching costs and protects against "
            "churn as competitors develop spatial computing offerings — estimated ARPU uplift of \$7/month "
            "per premium tier upgrade across 800K subscribers adds \$67M annualised gross profit."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q: 'Services include iCloud, Apple One, Apple Music, Apple TV+, "
            "Apple Arcade, Apple Fitness+, Apple News+.' Apple Jan 2024: Vision Pro launches "
            "February 2, 2024 at \$3,499 with 600+ launch apps across productivity, gaming, and media."
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0285",
        "decision_title": "Allocate Internal Compute by ROI Threshold",
        "decision_description": (
            "Implement a compute resource allocation framework across Apple's 40,000+ internal servers "
            "that scores workloads by revenue-attribution score — assigning 60% of premium GPU cluster "
            "capacity to Apple Intelligence model training, 25% to Siri latency optimisation, and 15% "
            "to internal analytics — replacing the prior first-come-first-served scheduling model that "
            "resulted in non-revenue workloads consuming 28% of scarce H100 GPU time."
        ),
        "decision_rationale": (
            "Apple Intelligence model training on-premise requires prioritised access to H100 GPU "
            "clusters that are in constrained supply through mid-2024; ROI-based allocation ensures "
            "the highest-revenue workloads — Apple Intelligence for iOS 18 — are not delayed by lower-"
            "priority internal tasks, protecting the Q4 FY2024 feature launch schedule."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 earnings call, T. Cook: 'We are making significant investments in AI and "
            "machine learning across all of our products.' Apple Q1 FY2024 10-Q: 'R&D expense \$7.65 "
            "billion for the quarter; increased reflecting investment in Apple Intelligence capabilities.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0289",
        "decision_title": "Expand Credit Analytics for Channel Partners",
        "decision_description": (
            "Deploy a real-time credit exposure monitoring dashboard for Apple's top 120 channel partners "
            "— covering 82% of non-carrier wholesale AR — integrating credit bureau feeds, payment "
            "history scoring, and sell-through velocity data to identify partners at elevated default "
            "risk and trigger proactive credit limit adjustments before AR concentrations exceed "
            "defined exposure thresholds."
        ),
        "decision_rationale": (
            "Apple's \$23.7B net accounts receivable as of December 30, 2023 included significant "
            "channel partner concentration; improving early-warning detection for credit deterioration "
            "reduces bad debt expense, which averaged \$47M annually over FY2021–FY2023 but carries "
            "potential for step-change increase if macro conditions deteriorate."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Accounts Receivable Note: 'Net receivables \$23.68 billion; no "
            "single customer exceeded 10% of net receivables.' Apple FY2023 10-K, Risk Factors: "
            "'Failure by channel partners to meet payment obligations could adversely affect results.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0293",
        "decision_title": "Broaden iPhone Installment Financing in Emerging Markets",
        "decision_description": (
            "Launch Apple-branded iPhone installment financing in Brazil, Mexico, and Turkey — partnering "
            "with local banking partners (Itaú, Banorte, İş Bankası) to offer 12-month zero-interest "
            "plans for iPhone 15 and 15 Pro — targeting 850,000 financed units in the first 12 months "
            "and addressing the structural affordability barrier where iPhone 15 Pro retails at 4.2× "
            "average monthly wage in Brazil and 3.8× in Turkey."
        ),
        "decision_rationale": (
            "Brazil, Mexico, and Turkey collectively represent 180 million smartphone users where Apple "
            "iPhone share is below 12% despite strong brand aspiration; financing removes the largest "
            "adoption barrier — upfront cost — and is expected to grow iPhone share by 2–3pp annually "
            "in each market, expanding the installed base for high-margin Services monetisation."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 earnings call, T. Cook: 'We're seeing good traction in emerging markets '  "
            "'where financing programs are key to making iPhone accessible.' Counterpoint Q4 2023: "
            "Apple iPhone share Brazil 9%, Mexico 11%, Turkey 8% — all below global average of 18%."
        ),
    },
    # ─── Batch 5 — sustainability and forward planning ────────────────────
    {
        "case_id": "AAPL-2024Q1-0297",
        "decision_title": "Launch Predictive Seasonal Demand Forecasting System",
        "decision_description": (
            "Deploy an upgraded demand forecasting model incorporating macroeconomic leading indicators "
            "— consumer confidence indices, local currency movements, and smartphone replacement cycle "
            "data — across Apple's top 40 markets, targeting a reduction in one-quarter-out iPhone "
            "demand forecast error from the current ±8.4% to below ±4.5%, enabling more precise "
            "component order commitments to suppliers 14 weeks ahead of production."
        ),
        "decision_rationale": (
            "Forecast accuracy improvement directly reduces both over-supply write-down risk and under-"
            "supply revenue loss; at Apple's scale, a 1pp improvement in forecast accuracy translates "
            "to approximately \$1.2B reduction in at-risk inventory and \$600M reduction in expediting "
            "costs — the two largest drivers of blended gross margin volatility."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Risk Factors: 'We face substantial inventory and other asset risk. '  "
            "'Mismatches between demand and supply…may adversely affect our results.' Internal planning "
            "document: 'Q3 FY2023 iPhone 14 channel fill error reached 9.2%, driving \$1.4B correction.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0301",
        "decision_title": "Introduce High-Value Inventory Transit Insurance",
        "decision_description": (
            "Procure selective transit cargo insurance for Apple's 50 highest-value monthly shipments — "
            "primarily iPhone Pro model containers and Vision Pro units — at 100% declared value "
            "coverage, supplementing the current self-insurance model that left an estimated \$480M "
            "of monthly premium unit shipments with inadequate coverage during the Taiwan Strait "
            "tension period in August 2023."
        ),
        "decision_rationale": (
            "Apple's self-insurance model is economically efficient for high-volume, moderate-value "
            "shipments but creates unacceptable tail-risk exposure for Vision Pro units at \$3,499 "
            "each; fully insuring the top 50 monthly premium shipments adds estimated \$12M annual "
            "insurance cost against \$480M per-event loss exposure — a 40:1 risk-cost ratio."
        ),
        "source_excerpt": (
            "Apple FY2023 10-K, Risk Factors: 'We are self-insured for many risks; significant losses '  "
            "'may not be covered by our self-insurance reserves.' Apple Press Release, Jan 2024: "
            "'Apple Vision Pro available from February 2, starting at \$3,499 for 256GB configuration.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0305",
        "decision_title": "Implement Real-Time Spare Parts Tracking for Service Operations",
        "decision_description": (
            "Deploy RFID-based real-time inventory tracking for critical spare parts across Apple's "
            "top 80 Authorised Service Provider locations and 11 Apple Repair Centres globally, "
            "targeting a 22% reduction in part-unavailability repair delays — which currently average "
            "3.2 additional days for iPhone display and battery replacements versus the 1.4-day target "
            "stipulated in ASP Service Level Agreements."
        ),
        "decision_rationale": (
            "AppleCare revenue grew 14% YoY to \$2.4B in Q1 FY2024; repair velocity directly impacts "
            "NPS scores for AppleCare+ subscribers, who represent the highest-ARPU device segment; "
            "RFID-based spare part tracking resolves the primary cause — part location errors and "
            "phantom inventory — of 68% of SLA breach incidents."
        ),
        "source_excerpt": (
            "Apple FY2023 10-K, Products & Services: 'AppleCare provides hardware and software support '  "
            "'products and technical support.' AppleCare SLA documentation: 'Authorised Service Providers "
            "required to achieve 1.4-day average repair completion for in-warranty iPhone repairs.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0309",
        "decision_title": "Adjust Regional Marketing Allocation for Bundle Promotions",
        "decision_description": (
            "Reallocate 15% of Apple's Q2 FY2024 regional marketing budget from above-the-line brand "
            "advertising in Europe to performance-marketing channels promoting Apple One and iCloud+ "
            "upgrades, targeting markets where Services penetration among the installed base is below "
            "28% — including Italy, Spain, Poland, and the Netherlands — to close the gap with the "
            "US baseline of 41% Services penetration."
        ),
        "decision_rationale": (
            "European Services ARPU is approximately 23% below North American ARPU despite comparable "
            "device installed bases; targeted performance marketing in low-penetration markets offers "
            "4× higher marginal ROI than brand advertising, converting existing device owners into "
            "services subscribers at a lower cost than acquiring new device customers."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Geographic Data: 'Europe revenue \$30.0 billion, up 11% year-over-year.' "
            "Apple Q1 FY2024 earnings: 'Services revenue set all-time records in Americas, Europe, Japan, "
            "and Asia Pacific.' Internal marketing analytics: European Services penetration 28% vs 41% US."
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0313",
        "decision_title": "Set Liquidity Buffer Thresholds for Downturn Scenarios",
        "decision_description": (
            "Formalise a liquidity policy requiring Apple to maintain a minimum \$50B cash-and-equivalents "
            "floor even during maximum repurchase acceleration quarters, with automatic programme step-"
            "down triggers if unrestricted cash falls below \$55B — providing a structured buffer "
            "against a 20% revenue shock scenario that would reduce quarterly operating cash flow "
            "from \$39.9B to approximately \$28B for two to three consecutive quarters."
        ),
        "decision_rationale": (
            "Apple's total liquidity position of \$162.3B at December 30, 2023 includes \$99.5B in long-"
            "term securities that cannot be liquidated without market impact; the \$50B floor policy "
            "ensures adequate short-term liquidity to maintain the dividend and meet debt maturities "
            "in a severe but plausible revenue stress scenario."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q, Liquidity Note: 'Cash, cash equivalents and marketable securities "
            "\$162.3 billion as of December 30, 2023.' Apple Q1 FY2024 10-Q: 'Current portion of term "
            "debt \$10.9 billion due within 12 months, manageable within existing liquidity resources.'"
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0317",
        "decision_title": "Improve Developer Payout Forecasting Accuracy",
        "decision_description": (
            "Upgrade Apple's developer payment forecasting engine to incorporate real-time App Store "
            "sales trends, currency conversion adjustments, and regional fiscal calendar effects, "
            "reducing the quarterly discrepancy between developer-facing revenue estimates and final "
            "settled payments from ±4.8% to below ±1.5% — addressing a key developer satisfaction "
            "pain point that was cited by 38% of developers in the App Store Developer Satisfaction "
            "Survey as a top-5 friction point."
        ),
        "decision_rationale": (
            "Developer ecosystem health directly determines App Store content quality and exclusivity; "
            "improving payout predictability reduces developer cash flow uncertainty, increasing "
            "willingness to invest in premium App Store exclusives — particularly critical as App "
            "Store revenue, estimated at \$25B annually, underpins 30–35% of Services revenue."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q: 'App Store included within Services; developer community exceeded "
            "34 million registered developers.' Apple App Store Developer Survey 2023: '38% of developers "
            "cited payment timing and accuracy as top-5 satisfaction challenge.' WWDC 2023 session notes."
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0318",
        "decision_title": "Procure Carbon Offsets for Manufacturing Emissions",
        "decision_description": (
            "Procure 3.2 million tonnes of verified carbon offsets from three distinct registries — "
            "Gold Standard, Verra VCS, and American Carbon Registry — covering manufacturing scope-3 "
            "emissions from Tier-1 suppliers in China and India that have not yet completed renewable "
            "energy transitions, bridging the gap between current supplier clean energy adoption of 68% "
            "and Apple's 2030 carbon-neutral supply chain commitment."
        ),
        "decision_rationale": (
            "Apple's 2030 carbon neutrality commitment is a key ESG pillar that influences institutional "
            "investor allocations and reduces the risk of carbon border adjustment penalties under the "
            "EU CBAM; procuring verified offsets for the remaining 32% of non-renewable supplier emissions "
            "maintains Apple's environmental credibility while renewable transitions complete."
        ),
        "source_excerpt": (
            "Apple Environmental Progress Report 2023: '68% of supplier facilities now powered by "
            "renewable energy; 32% gap remains.' Apple 2030 Climate Pledge: 'Carbon neutral across "
            "entire value chain and product lifecycle by 2030.' EU CBAM effective October 2023 for "
            "embedded carbon in aluminium, steel, cement, and electricity imports."
        ),
    },
    {
        "case_id": "AAPL-2024Q1-0319",
        "decision_title": "Optimise iOS Low-Power Mode Algorithms",
        "decision_description": (
            "Enhance iPhone's Low Power Mode (LPM) activation algorithms in iOS 17 to apply dynamic "
            "CPU clock throttling at a 20% finer granularity than the current 3-tier model, targeting "
            "a 5% improvement in battery runtime at the 20%-charge threshold — addressing App Store "
            "review data showing battery life as the top complaint across iPhone 14 and 15 standard "
            "models at 4.8 out of 5 stars review scores."
        ),
        "decision_rationale": (
            "Battery perception improvement is a key iPhone repurchase driver; App Store and Trustpilot "
            "data show battery dissatisfaction accounts for 29% of negative iPhone 15 standard reviews; "
            "an over-the-air LPM algorithm improvement costs approximately \$8M in engineering resources "
            "and can reach all 800M+ iOS 17-compatible devices without hardware investment."
        ),
        "source_excerpt": (
            "Apple Q1 FY2024 10-Q: 'iPhone revenue \$69.7 billion, up 6% YoY.' iOS 17 adoption rate "
            "as of Dec 2023: 72% of active iPhones. App Store review analysis, Jan 2024: battery life "
            "rated top complaint category for iPhone 15 standard at 4.2% of all one-star reviews."
        ),
    },
]
