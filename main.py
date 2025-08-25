#!/usr/bin/env python3
"""
Dump Cornell Class Roster data with prereq parsing and a 'technical_elective' flag.

Usage:
  python dump_roster.py --roster FA25 --subject CS
  python dump_roster.py --roster SP24
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Set, Any, Optional

import requests
import os

import re
from typing import Tuple, Set, Dict

def norm_code(subj: str, num: str) -> Tuple[str, str]:
    subj = (subj or "").upper()
    m = re.match(r"(\d{3,4}[A-Z]?)", str(num or ""))
    return (subj, m.group(1)) if m else (subj, str(num or "").upper())

def build_prereq_graph(classes: list[dict]) -> Dict[Tuple[str,str], Set[Tuple[str,str]]]:
    """
    Graph of course -> set of immediate prereq course codes (SUBJ, NUM).
    """
    graph: Dict[Tuple[str,str], Set[Tuple[str,str]]] = {}
    for course in classes:
        key = norm_code(course.get("subject"), course.get("catalog_nbr"))
        codes = { (s, n) for (s, n) in course.get("prereq_course_codes", []) }
        graph[key] = codes
    return graph

def qualifies_transitively(
    course_key: Tuple[str,str],
    graph: Dict[Tuple[str,str], Set[Tuple[str,str]]],
    qualifying: Set[Tuple[str,str]],
    max_depth: int = 6
) -> bool:
    """
    True if the course directly OR transitively depends on any qualifying code.
    Traverses within the known graph; if a prereq node is missing from the graph,
    we still count it if it's directly in `qualifying`.
    """
    if course_key not in graph:
        return False

    # direct match
    if len(graph[course_key].intersection(qualifying)) > 0:
        return True

    visited: Set[Tuple[str,str]] = set()
    stack: list[tuple[Tuple[str,str], int]] = [(p, 1) for p in graph[course_key]]

    while stack:
        node, depth = stack.pop()
        if node in visited: 
            continue
        visited.add(node)

        # if this prereq itself is on the qualifying list, we're done
        if node in qualifying:
            return True

        if depth >= max_depth:
            continue

        # expand only if we know this node's prereqs
        if node in graph:
            for nxt in graph[node]:
                if nxt not in visited:
                    stack.append((nxt, depth + 1))

    return False

API_BASE = "https://classes.cornell.edu/api/2.0"

# ---- EDIT THIS WHEN YOU GET THE OFFICIAL LIST --------------------------------
# Conservative whitelist of "acceptable prerequisite courses" that indicate a course
# should count as a technical elective when they appear in the prereq text.
QUALIFYING_PREREQS: Set[Tuple[str, str]] = {
    ("CS", "2110"), ("CS", "2112"),
    ("CS", "2800"), ("CS", "2802"),
    ("CS", "3110"), ("CS", "3410"),
    ("MATH", "2210"), ("MATH", "2930"), ("MATH", "2940"),
    # Add more as needed once the official list is confirmed
}

def load_qualifying_list(path: str) -> Set[Tuple[str, str]]:
    """
    Load qualifying prereq courses from a file.
    Accepted formats:
      - JSON array of strings: ["CS 2110","CS 3110"]
      - JSON array of pairs: [["CS","2110"],["MATH","2210"]]
      - Newline-separated text: each line like "CS 2110"
    Returns a set of (SUBJ, NUM) tuples, upper-cased.
    """
    path = path.strip()
    if not path:
        return set()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Qualifying list file not found: {path}")

    def to_pair(s: str) -> Tuple[str, str]:
        s = s.strip().upper()
        m = re.match(r"^([A-Z]{2,5})\s+(\d{3,4}[A-Z]?)$", s)
        if not m:
            raise ValueError(f"Invalid course code format: {s!r}")
        return (m.group(1), m.group(2))

    # Try JSON first
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        pairs: Set[Tuple[str, str]] = set()
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, str):
                    pairs.add(to_pair(item))
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    pairs.add((str(item[0]).upper(), str(item[1]).upper()))
                else:
                    raise ValueError("Unsupported JSON item in qualifying list.")
            return pairs
    except json.JSONDecodeError:
        pass  # fall through to plaintext

    # Fallback: plaintext, newline-separated
    pairs: Set[Tuple[str, str]] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            pairs.add(to_pair(line))
    return pairs

# Optional extra guardrails (set to True to enforce)
REQUIRE_MIN_LEVEL = False
MIN_LEVEL = 3000  # e.g., only count courses numbered 3000+

SUBJECT_WHITELIST: Optional[Set[str]] = None
# Example: {"CS", "ECE", "INFO"} to only consider those subjects as potential tech electives.


# ---- Regex to extract course codes from text ---------------------------------
COURSE_RE = re.compile(
    r"""
    (?P<subj>[A-Z]{2,5})      # Subject, e.g., CS, ECE, MATH, INFO
    [\s/]*
    (?P<num>\d{3,4}[A-Z]?)    # Number, e.g., 2110, 3110, 4321, 4999, 4710B
    """,
    re.VERBOSE
)

def extract_course_codes(text: str) -> Set[Tuple[str, str]]:
    """Return set of (SUBJ, NUM) pairs found in prereq/coreq text."""
    if not text:
        return set()
    # Expand patterns like "CS/INFO 4321" into "CS 4321, INFO 4321"
    expanded = re.sub(
        r'([A-Z]{2,5})/([A-Z]{2,5})\s+(\d{3,4}[A-Z]?)',
        r'\1 \3, \2 \3',
        text.upper()
    )
    hits = {(m.group("subj"), m.group("num")) for m in COURSE_RE.finditer(expanded)}
    return hits


def course_level_ok(catalog_nbr: Any) -> bool:
    if not REQUIRE_MIN_LEVEL:
        return True
    try:
        m = re.match(r"(\d{3,4})", str(catalog_nbr))
        if not m:
            return False
        return int(m.group(1)) >= MIN_LEVEL
    except Exception:
        return False


def subject_ok(subject: str) -> bool:
    if SUBJECT_WHITELIST is None:
        return True
    return subject.upper() in SUBJECT_WHITELIST


def is_technical_elective(
    course_subject: str,
    catalog_nbr: Any,
    prereq_text: str,
    qualifying_whitelist: Set[Tuple[str, str]],
) -> bool:
    """Heuristic: counts if prereq text mentions ANY code in our whitelist + passes optional guards."""
    if not subject_ok(course_subject) or not course_level_ok(catalog_nbr):
        return False
    codes = extract_course_codes(prereq_text or "")
    return len(codes.intersection(qualifying_whitelist)) > 0


def safe_get(d: Dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return default
    return d


def fetch_classes(roster: str, subject: Optional[str] = None, **extra_params) -> List[Dict]:
    """Fetch class objects from the Cornell API."""
    params = {"roster": roster}
    if subject:
        params["subject"] = subject
    params.update(extra_params)
    url = f"{API_BASE}/search/classes.json"
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    classes = safe_get(payload, "data", "classes", default=[])
    return classes or []


def build_records(raw_classes: List[Dict], qualifying_set: Set[Tuple[str, str]]) -> Tuple[List[Dict], List[Dict], Dict[str, Any]]:
    """
    Transform raw API classes into structured records, mark technical electives,
    and collect analytics on observed prereq codes.
    """
    classes_out: List[Dict] = []
    tech_electives_out: List[Dict] = []

    observed_codes_counter: Counter = Counter()
    missing_from_whitelist: Counter = Counter()

    for c in raw_classes:
        subject = c.get("subject")
        catalog_nbr = c.get("catalogNbr")
        title = c.get("titleLong") or c.get("titleShort")
        description = c.get("description")  # may be absent in standard rosters
        attrs = c.get("crseAttrs", [])
        attr_groups = c.get("crseAttrValueGroups", [])

        # FA25+ split fields; legacy is combined
        prereq = c.get("catalogPrereq")  # text
        coreq = c.get("catalogCoreq")    # text
        legacy_prereq_coreq = c.get("catalogPrereqCoreq")  # text

        prereq_text = prereq or legacy_prereq_coreq or ""
        coreq_text = coreq or ""

        # Sections / meetings / instructors live under enrollGroups
        sections = []
        for eg in c.get("enrollGroups", []):
            for sec in eg.get("classSections", []):
                for mtg in sec.get("meetings", []):
                    instructors = [
                        i.get("name") for i in mtg.get("instructors", [])
                        if i.get("name")
                    ]
                    sections.append({
                        "section": sec.get("classNbr"),
                        "component": sec.get("ssrComponent"),
                        "pattern": mtg.get("pattern"),
                        "facility": mtg.get("facilityDescr"),
                        "start": mtg.get("timeStart"),
                        "end": mtg.get("timeEnd"),
                        "instructors": instructors
                    })

        # Extract prereq course codes and update counters
        prereq_codes = extract_course_codes(prereq_text)
        for code in prereq_codes:
            observed_codes_counter[code] += 1
            if code not in qualifying_set:
                missing_from_whitelist[code] += 1

        technical_elective = is_technical_elective(
            subject or "",
            catalog_nbr,
            prereq_text,
            qualifying_set,
        )

        rec = {
            "subject": subject,
            "catalog_nbr": catalog_nbr,
            "title": title,
            "description": description,
            "course_attributes": attrs,
            "attribute_groups": attr_groups,
            "prereq": prereq,                         # FA25+
            "coreq": coreq,                           # FA25+
            "legacy_prereq_coreq": legacy_prereq_coreq,  # pre-FA25
            "prereq_text": prereq_text,
            "coreq_text": coreq_text,
            "prereq_course_codes": sorted(list(prereq_codes)),
            "sections": sections,
            "technical_elective": technical_elective,
        }
        classes_out.append(rec)

        if technical_elective:
            tech_electives_out.append({
                "subject": subject,
                "catalog_nbr": catalog_nbr,
                "title": title,
                "prereq_text": prereq_text,
                "matched_codes": sorted(list(prereq_codes.intersection(qualifying_set))),
            })

    analytics = {
        "observed_code_counts": sorted(
            [(f"{s} {n}", cnt) for (s, n), cnt in observed_codes_counter.items()],
            key=lambda x: (-x[1], x[0])
        ),
        "not_in_whitelist_counts": sorted(
            [(f"{s} {n}", cnt) for (s, n), cnt in missing_from_whitelist.items()],
            key=lambda x: (-x[1], x[0])
        ),
        "whitelist_size": len(qualifying_set),
    }

    return classes_out, tech_electives_out, analytics


def main():
    ap = argparse.ArgumentParser(description="Dump Cornell roster classes with prereq parsing.")
    ap.add_argument("--roster", required=True, help="Roster code, e.g., SP24, FA25")
    ap.add_argument("--subject", help="Subject code to filter, e.g., CS (optional)")
    ap.add_argument("--outfile-classes", default="classes.json", help="Output file for all classes")
    ap.add_argument("--outfile-tech", default="tech_electives.json", help="Output file for tech electives subset")
    ap.add_argument("--outfile-observed", default="observed_prereq_codes.json",
                    help="Output file with observed prereq codes + counts")
    ap.add_argument("--qualifying-file", help="Path to a file containing qualifying prereq courses (overrides built-in list).")
    ap.add_argument("--transitive", dest="transitive", action="store_true", help="Enable transitive prereq evaluation (default).")
    ap.add_argument("--no-transitive", dest="transitive", action="store_false", help="Disable transitive prereq evaluation; only direct matches count.")
    ap.set_defaults(transitive=True)
    args = ap.parse_args()

    qualifying_set = set(QUALIFYING_PREREQS)
    if args.qualifying_file:
        qualifying_set = load_qualifying_list(args.qualifying_file)
        print(f"Loaded {len(qualifying_set)} qualifying prereq codes from {args.qualifying_file}")

    print(f"Fetching classes for roster={args.roster} subject={args.subject or '(all)'} …")
    raw = fetch_classes(args.roster, args.subject)

    print(f"Parsing {len(raw)} classes …")
    classes, tech_electives, analytics = build_records(raw, qualifying_set)

    # If transitive evaluation is enabled, recompute the technical_elective flag using the graph.
    if args.transitive:
        graph = build_prereq_graph(classes)
        updated_tech_electives = []
        for course in classes:
            course_key = norm_code(course.get("subject"), course.get("catalog_nbr"))
            guards_ok = subject_ok(course.get("subject") or "") and course_level_ok(course.get("catalog_nbr"))
            if guards_ok and qualifies_transitively(course_key, graph, qualifying_set):
                course["technical_elective"] = True
            # rebuild the tech_electives list to reflect any upgrades due to transitive matches
            if course.get("technical_elective"):
                updated_tech_electives.append({
                    "subject": course["subject"],
                    "catalog_nbr": course["catalog_nbr"],
                    "title": course["title"],
                    "prereq_text": course.get("prereq_text", "") or "",
                    "matched_codes": sorted(list(set(course.get("prereq_course_codes", [])).intersection(qualifying_set))),
                    "qualified_via_transitive": True,  # indicates transitive logic was considered
                })
        tech_electives = updated_tech_electives

    with open(args.outfile_classes, "w", encoding="utf-8") as f:
        json.dump(classes, f, indent=2, ensure_ascii=False)

    with open(args.outfile_tech, "w", encoding="utf-8") as f:
        json.dump(tech_electives, f, indent=2, ensure_ascii=False)

    with open(args.outfile_observed, "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2, ensure_ascii=False)

    print(f"✅ Wrote {len(classes)} classes to {args.outfile_classes}")
    print(f"✅ Wrote {len(tech_electives)} technical electives to {args.outfile_tech}")
    print(f"✅ Wrote observed prereq code stats to {args.outfile_observed}")
    if analytics["not_in_whitelist_counts"]:
        print("ℹ️  Tip: review 'not_in_whitelist_counts' in observed_prereq_codes.json to grow your whitelist.")


if __name__ == "__main__":
    main()