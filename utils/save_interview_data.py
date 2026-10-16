import json
import os

from utils.interview_flow import sanitize_name


def save_interview_data(interview_data, candidate_name, output_dir="outputs"):
    """Save interview data to outputs/<name>_interview_data.json and return the path."""
    filename = f"{sanitize_name(candidate_name)}_interview_data.json"

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(interview_data, f, indent=2, ensure_ascii=False)

    print(f"Interview data saved to {filepath}")
    return filepath
