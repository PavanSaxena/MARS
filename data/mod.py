import pandas as pd

# Input and output file paths
input_file = "data/q2-2025.csv"
output_file = "data/q2-2025_updated.csv"

# Read CSV
df = pd.read_csv(input_file)

# Ensure the column exists
if "case_id" not in df.columns:
    raise ValueError("Column 'case_id' not found in the CSV file.")

# Update case-id to start from 1
df["case_id"] = "MARS-2025-" + (df.index + 1).astype(str)

# Save updated CSV without modifying anything else
df.to_csv(output_file, index=False)

print(f"Updated file saved as {output_file}")