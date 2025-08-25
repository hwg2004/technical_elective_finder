# Cornell Tech Elective Checker

A Python tool that determines if Cornell courses qualify as technical electives by recursively checking their prerequisite chains against a list of acceptable prerequisite courses.

## Overview

This tool uses the Cornell Course API to:
- Fetch course information and prerequisites
- Recursively traverse prerequisite chains
- Determine if a course qualifies as a technical elective based on whether it (or its prerequisites) are in an approved list
- Check multiple courses in batch and export results to JSON

## Requirements

- Python 3.6+
- `requests` library

### Installation

```bash
pip install requests
```

## Quick Start

```python
from cornell_tech_elective_checker import CornellTechElectiveChecker

# Define your acceptable prerequisite courses
acceptable_prereqs = [
    "CS 2110",
    "CS 2112", 
    "CS 2800",
    "MATH 2940",
    # Add all acceptable prerequisites here
]

# Create checker instance
checker = CornellTechElectiveChecker(acceptable_prereqs)

# Check if a course is a tech elective
is_elective = checker.is_tech_elective("CS 4820")
print(f"CS 4820 is tech elective: {is_elective}")
```

## Features

### 1. Single Course Check
Check if a single course qualifies as a technical elective:

```python
is_elective = checker.is_tech_elective("CS 4820", roster="FA25")
```

### 2. Debug Mode
See the complete prerequisite chain to understand why a course does/doesn't qualify:

```python
checker.check_single_course_debug("CS 4820")
```

Output:
```
Debug check for CS 4820:
  → CS 4820 has prerequisites: {'CS 2110', 'CS 2800'}
    → CS 2110 has prerequisites: {'CS 1110'}
      ✗ CS 1110 has no prerequisites
    ✓ CS 2800 is in acceptable prerequisites list
Result: CS 4820 is a technical elective
```

### 3. Batch Processing
Check multiple courses at once:

```python
courses = ["CS 4820", "CS 4410", "INFO 3300", "CS 4700", "CS 4780"]
results = checker.check_multiple_courses(courses)
```

### 4. JSON Export
Check courses and save results to JSON:

```python
output = checker.check_courses_to_json(
    courses,
    roster="FA25",
    output_file="tech_electives_results.json"
)
```

JSON output format:
```json
{
  "metadata": {
    "total_courses_checked": 5,
    "tech_electives_found": 3,
    "non_tech_electives": 2,
    "roster": "FA25",
    "acceptable_prerequisites": ["CS 2110", "CS 2112", ...],
    "check_date": "2025-08-25T10:30:00",
    "execution_time_seconds": 12.3
  },
  "results": {
    "CS 4820": true,
    "CS 4410": true,
    "INFO 3300": false,
    ...
  },
  "tech_electives": ["CS 4820", "CS 4410", ...],
  "non_tech_electives": ["INFO 3300", ...]
}
```

### 5. Load from File
Load course lists from text or CSV files:

```python
# Text file (one course per line)
courses = checker.load_courses_from_file("courses.txt")

# CSV file (courses in first column)
courses = checker.load_courses_from_file("courses.csv")

# Process loaded courses
output = checker.check_courses_to_json(courses)
```

## Configuration

### Acceptable Prerequisites

The most important configuration is the list of acceptable prerequisite courses. A course qualifies as a technical elective if:
1. It's directly in the acceptable prerequisites list, OR
2. One of its prerequisites (recursively) is in the list

```python
acceptable_prereqs = [
    # Core CS courses
    "CS 2110",  # Object-Oriented Programming
    "CS 2112",  # OOP Honors
    "CS 2800",  # Discrete Structures
    "CS 3110",  # Functional Programming
    "CS 3410",  # Computer System Organization
    
    # Math courses
    "MATH 2940",  # Linear Algebra
    "MATH 2930",  # Differential Equations
    
    # Engineering courses
    "ECE 2300",  # Digital Logic
    
    # Add all courses that qualify according to your requirements
]
```

### Roster Selection

Specify which semester's course data to use:

```python
# Fall 2025 (default)
checker.is_tech_elective("CS 4820", roster="FA25")

# Spring 2024
checker.is_tech_elective("CS 4820", roster="SP24")
```

## API Rate Limiting

The Cornell API has a rate limit of 1 request per second. The tool automatically handles this with built-in rate limiting. For 1,000 courses:
- **Worst case**: ~16-17 minutes (if all courses are unique)
- **Typical case**: Much faster due to caching (common prerequisites are only fetched once)

## Large-Scale Processing (1,000+ Courses)

For checking large numbers of courses:

```python
# Load courses from file
courses = checker.load_courses_from_file("all_courses.txt")

# Process with progress tracking
output = checker.check_courses_to_json(
    courses,
    roster="FA25",
    output_file="results_1000.json",
    show_progress=True  # Shows progress and time estimates
)
```

The tool will:
- Show progress (e.g., "Checking CS 4820... (245/1000)")
- Estimate time remaining
- Cache results to minimize API calls
- Save complete results to JSON

## Troubleshooting

### No Tech Electives Found?

If all courses return `False`, use debug mode to diagnose:

```python
# Check a specific course's prerequisite chain
checker.check_single_course_debug("CS 4820")
```

Common issues:
1. **Incomplete acceptable prerequisites list**: Add missing courses shown in debug output
2. **No prerequisites in API**: Some courses may not have prerequisite data
3. **Prerequisite chain doesn't reach acceptable list**: Add intermediate courses

### API Errors

If you see "Error fetching [course]":
- Check your internet connection
- Verify the course code format (e.g., "CS 4820" not "CS4820")
- Ensure the roster code is valid (e.g., "FA25", "SP24")

### Performance Tips

1. **Use caching**: The tool automatically caches API responses
2. **Batch similar courses**: Courses with common prerequisites will be faster
3. **Increase recursion depth if needed**: Default is 5 levels

```python
# Check deeper prerequisite chains
is_elective = checker.is_tech_elective(
    "CS 4820", 
    max_depth=10  # Default is 5
)
```

## Example Usage

Complete example with all features:

```python
from cornell_tech_elective_checker import CornellTechElectiveChecker

# Configure acceptable prerequisites
acceptable_prereqs = [
    "CS 2110", "CS 2112", "CS 2800", "CS 3110",
    "CS 3410", "MATH 2940", "ECE 2300"
]

# Initialize checker
checker = CornellTechElectiveChecker(acceptable_prereqs)

# Debug a single course
print("=== DEBUG MODE ===")
checker.check_single_course_debug("CS 4820")

# Check multiple courses
print("\n=== BATCH CHECK ===")
courses = ["CS 4820", "CS 4410", "INFO 3300", "CS 4700", "CS 4780"]
output = checker.check_courses_to_json(
    courses,
    roster="FA25",
    output_file="tech_electives.json"
)

# Display results
if output:
    print(f"\nResults:")
    print(f"  Tech Electives: {output['tech_electives']}")
    print(f"  Non-Tech Electives: {output['non_tech_electives']}")
    print(f"  Success Rate: {len(output['tech_electives'])/len(courses)*100:.1f}%")
```

## License

This tool is provided as-is for educational purposes. Please respect Cornell's API usage guidelines and rate limits.

## Contact

For questions about the Cornell Course API, contact: coursenroll@cornell.edu

## Notes

- The tool respects the API's 1 request/second rate limit
- Course data for Fall 2025+ uses the new API format (catalogPrereq field)
- Course data before Fall 2025 uses the legacy format (catalogPrereqCoreq field)
- Results are cached during execution to minimize API calls