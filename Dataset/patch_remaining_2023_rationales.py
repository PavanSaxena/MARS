"""
patch_remaining_2023_rationales.py
Updates the remaining 21 duplicate rationales across Q3 and Q4 so that every single rationale
across the entire 640 cases of 2023 is 100% UNIQUE.
"""

import pandas as pd

RATS_Q3 = {
    "AAPL-2023Q3-0092": "Tuned specifically for the upcoming A17 Pro 3nm silicon and titanium chassis, balancing sustained 60fps console gaming performance against localized chassis heat conduction in summer testing.",
    "AAPL-2023Q3-0096": "Optimizes desktop widget rendering cycles in macOS Sonoma beta 3, ensuring background interactive controls remain responsive without degrading battery endurance on portable MacBooks.",
    "AAPL-2023Q3-0098": "Leverages the on-device Neural Engine in iOS 17 beta to deliver instantaneous, real-time voicemail transcription with zero cloud round-trip latency and complete end-to-end caller privacy.",
    "AAPL-2023Q3-0099": "Focuses engineering resources on modem baseband calibration ahead of high-band mmWave testing, preparing proprietary silicon to gradually replace Qualcomm modem components.",
    "AAPL-2023Q3-0113": "Enables iOS developers in summer 2023 to deploy 4-bit quantized generative diffusion models directly onto Apple Silicon with minimal DRAM bandwidth utilization.",
    "AAPL-2023Q3-0118": "Allows users at risk of speech loss to generate a personalized synthesized voice directly on iPhone within 15 minutes of training, keeping all biometric vocal weights strictly on-device.",
    "AAPL-2023Q3-0135": "Provides granular public data on app rejections, developer account terminations, and government removal requests in summer 2023, satisfying statutory commitments and transparency demands.",
    "AAPL-2023Q3-0136": "Institutes rigorous automated screening of Developer Transition Kits and advanced compute hardware across international freight forwarders to adhere to updated BIS entity designations.",
    "AAPL-2023Q3-0139": "Asserts Apple's registered European trademarks against copycat electronics and counterfeit wearable brands, preventing consumer confusion in key European Union retail markets.",
    "AAPL-2023Q3-0150": "Reflects shifting macroeconomic headwinds and semiconductor supply chain exposure in Q3 Form 10-Q disclosures, ensuring full compliance with SEC Regulation S-K requirements."
}

RATS_Q4 = {
    "AAPL-2023Q4-0014": "Automates multi-SKU retail carton stacking at Elk Grove during the holiday shipping surge, cutting outbound pallet staging cycle times by 35%.",
    "AAPL-2023Q4-0024": "Expands operational assembly capacity at Compal's Vietnam facilities in Q4 FY2023, accelerating geographic supply chain diversification away from central China for the iPad product family.",
    "AAPL-2023Q4-0028": "Secures dedicated regional buffer stock of Sony 48MP CMOS image sensors near Kumamoto fabrication hubs, protecting iPhone 15 Pro final assembly lines from optical supply disruptions.",
    "AAPL-2023Q4-0031": "Ramps high-end professional desktop assembly at the Houston, Texas campus to support enterprise customer orders with rapid domestic fulfillment.",
    "AAPL-2023Q4-0041": "Retires common shares under Rule 10b5-1 daily repurchase grids in Q4 FY2023, deploying $19.0 billion of operational cash flow to drive long-term EPS growth.",
    "AAPL-2023Q4-0042": "Distributes $3.8 billion in quarterly cash dividends to shareholders of record in November 2023, reflecting Board commitment to disciplined capital return.",
    "AAPL-2023Q4-0045": "Hedging contracts executed in autumn 2023 shield UK holiday commercial hardware revenues from volatile sterling fluctuations following Bank of England policy adjustments.",
    "AAPL-2023Q4-0048": "Secures tiered merchant acquirer fee concessions across European payment gateways ahead of the holiday shopping peak, defending Services gross margins.",
    "AAPL-2023Q4-0049": "Calibrates carrier channel promotional co-op funds and trade-in subsidies for the holiday shopping quarter, driving iPhone 15 unit volume without diluting headline ASPs.",
    "AAPL-2023Q4-0053": "Establishes deliverable currency forwards to hedge Q4 holiday sales proceeds in Greater China, insulating reported segment margins against ongoing Renminbi depreciation.",
    "AAPL-2023Q4-0071": "Maintains pristine corporate credit ratings in the FY2023 Form 10-K, ensuring Apple retains premier borrowing access and minimal credit spreads across global bond markets."
}

df3 = pd.read_csv("MARS/Dataset/Decisions/decisions_2023_q3.csv")
for cid, rat in RATS_Q3.items():
    df3.loc[df3["case_id"] == cid, "decision_rationale"] = rat
df3.to_csv("MARS/Dataset/Decisions/decisions_2023_q3.csv", index=False)
print("Updated Q3 rationales")

df4 = pd.read_csv("MARS/Dataset/Decisions/decisions_2023_q4.csv")
for cid, rat in RATS_Q4.items():
    df4.loc[df4["case_id"] == cid, "decision_rationale"] = rat
df4.to_csv("MARS/Dataset/Decisions/decisions_2023_q4.csv", index=False)
print("Updated Q4 rationales")
