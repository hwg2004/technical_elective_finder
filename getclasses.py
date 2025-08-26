#!/usr/bin/env python3
import sys
import requests
import json
from typing import Dict, Any, List

API_URL = "https://classes.cornell.edu/api/2.0/search/classes.json"

def fetch_classes(roster: str, subject: str) -> List[Dict[str, Any]]:
    params = {"roster": roster, "subject": subject}
    r = requests.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    return (r.json().get("data") or {}).get("classes", []) or []

def main(roster: str, subject: str) -> dict:
    try:
        courses = fetch_classes(roster, subject)
    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr); sys.exit(1)
    except requests.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr); sys.exit(1)

    if not courses:
        print("No courses found. Check roster and subject codes."); sys.exit(0)

    results = []
    for cls in courses:
        subj_code = cls.get("subject", "UNKNOWN")
        num = cls.get("catalogNbr", "N/A")

        # FA25+ -> catalogPrereq ; legacy -> catalogPrereqCoreq
        prereq = (
            cls.get("catalogPrereq")
            or cls.get("catalogPrereqCoreq")
            or "None specified"
        )

        results.append({
            "subject": subj_code,
            "number": num,
            "prerequisites": prereq
        })

    output = {
        subject: {
            "total_courses": len(results),
            "courses": results
        }   
    }
    print(f"Fetched {len(results)} {subject} courses")
    return output

  


if __name__ == "__main__":
    subjects = ["CS", "INFO", "MATH", "ECON", "MAE", "ORIE", "PHIL", "PHYS", "STSCI", "ECE", "AEM", "BTRY", "PUBPOL", "CEE", "LING"]
    final_output = {}
    for s in subjects:
        final_output.update(main(roster="FA25", subject=s))
    with open("results.json", "w") as f:
        json.dump(final_output, f, indent=2)