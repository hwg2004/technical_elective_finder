import requests
import time
import re
from typing import Set, List, Optional, Dict, Tuple, Any
import json

class CornellTechElectiveChecker:
    def __init__(self, acceptable_prerequisites: List[str]):
        """
        Initialize the checker with a list of acceptable prerequisite courses.
        
        Args:
            acceptable_prerequisites: List of course codes that qualify as acceptable prerequisites
                                    (e.g., ['CS 2110', 'CS 2112', 'MATH 2940'])
        """
        self.base_url = "https://classes.cornell.edu/api/2.0"
        self.acceptable_prerequisites = set(acceptable_prerequisites)
        self.cache = {}  # Cache to avoid redundant API calls
        self.last_request_time = 0
        
    def _rate_limit(self):
        """Ensure we don't exceed 1 request per second."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < 1:
            time.sleep(1 - time_since_last)
        self.last_request_time = time.time()
    
    def _parse_course_code(self, course_str: str) -> Tuple[str, str]:
        """
        Parse a course string into subject and number.
        
        Args:
            course_str: Course string like "CS 2110" or "MATH 2940"
            
        Returns:
            Tuple of (subject, number) or (None, None) if parse fails
        """
        match = re.match(r'([A-Z]+)\s*(\d+)', course_str.upper())
        if match:
            return match.group(1), match.group(2)
        return None, None
    
    def _fetch_course_data(self, subject: str, course_num: str, roster: str = "FA25") -> Optional[Dict]:
        """
        Fetch course data from the Cornell API.
        
        Args:
            subject: Course subject (e.g., 'CS')
            course_num: Course number (e.g., '2110')
            roster: Semester roster (default 'FA25' for Fall 2025)
            
        Returns:
            Course data dictionary or None if not found
        """
        cache_key = f"{roster}_{subject}_{course_num}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        self._rate_limit()
        
        try:
            url = f"{self.base_url}/search/classes.json"
            params = {
                'roster': roster,
                'subject': subject
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Find the specific course in the results
            if 'data' in data and 'classes' in data['data']:
                for course in data['data']['classes']:
                    if course.get('catalogNbr', '').strip() == course_num:
                        self.cache[cache_key] = course
                        return course
            
            self.cache[cache_key] = None
            return None
            
        except Exception as e:
            print(f"Error fetching {subject} {course_num}: {e}")
            return None
    
    def _extract_prerequisites(self, course_data: Dict, roster: str = "FA25") -> Set[str]:
        """
        Extract prerequisite courses from course data.
        
        Args:
            course_data: Course data from API
            roster: Semester roster to determine which field to use
            
        Returns:
            Set of prerequisite course codes
        """
        prerequisites = set()
        
        # Determine which field to use based on roster
        # For Fall 2025 and later, use catalogPrereq
        # For earlier, use catalogPrereqCoreq
        year = int(roster[2:4])
        is_fall = roster.startswith('FA')
        
        if year > 25 or (year == 25 and is_fall):
            prereq_text = course_data.get('catalogPrereq', '')
        else:
            prereq_text = course_data.get('catalogPrereqCoreq', '')
        
        if not prereq_text:
            # Also check the enrollGroups for prerequisite info
            enroll_groups = course_data.get('enrollGroups', [])
            for group in enroll_groups:
                if isinstance(group, dict):
                    # Check various possible fields for prerequisites
                    for field in ['prerequisite', 'prerequisites', 'prereq']:
                        if field in group:
                            prereq_text += " " + str(group[field])
        
        if not prereq_text:
            return prerequisites
        
        # Parse prerequisites from text
        # Look for patterns like "CS 2110", "MATH 2940", "CS2110", etc.
        # Handle both with and without spaces
        pattern = r'([A-Z]+)\s*(\d+)'
        matches = re.findall(pattern, prereq_text.upper())
        
        for subject, number in matches:
            # Skip course numbers that are too long (likely years or other data)
            if len(number) <= 4:
                prerequisites.add(f"{subject} {number}")
        
        return prerequisites
    
    def is_tech_elective(self, course: str, roster: str = "FA25", 
                        visited: Optional[Set[str]] = None, depth: int = 0, max_depth: int = 5,
                        debug: bool = False) -> bool:
        """
        Check if a course is a technical elective by recursively checking prerequisites.
        
        Args:
            course: Course code (e.g., "CS 4820")
            roster: Semester roster (default 'FA25')
            visited: Set of already visited courses (for cycle detection)
            depth: Current recursion depth
            max_depth: Maximum recursion depth to prevent infinite loops
            debug: Print debug information
            
        Returns:
            True if the course is a technical elective, False otherwise
        """
        if visited is None:
            visited = set()
        
        # Prevent infinite recursion
        if depth > max_depth:
            return False
        
        # Check if this course is directly in the acceptable list
        if course.upper() in (p.upper() for p in self.acceptable_prerequisites):
            if debug:
                print(f"  {'  '*depth}✓ {course} is in acceptable prerequisites list")
            return True
        
        # Avoid cycles
        if course in visited:
            return False
        
        visited.add(course)
        
        # Parse course code
        subject, number = self._parse_course_code(course)
        if not subject or not number:
            if debug:
                print(f"  {'  '*depth}✗ Could not parse course code: {course}")
            return False
        
        # Fetch course data
        course_data = self._fetch_course_data(subject, number, roster)
        if not course_data:
            if debug:
                print(f"  {'  '*depth}✗ No data found for {course}")
            return False
        
        # Extract prerequisites
        prerequisites = self._extract_prerequisites(course_data, roster)
        
        if debug:
            print(f"  {'  '*depth}→ {course} has prerequisites: {prerequisites if prerequisites else 'None'}")
        
        # Check if any prerequisite qualifies
        for prereq in prerequisites:
            if self.is_tech_elective(prereq, roster, visited.copy(), depth + 1, max_depth, debug):
                return True
        
        return False
    
    def check_single_course_debug(self, course: str, roster: str = "FA25") -> bool:
        """
        Check a single course with debug output to see the prerequisite chain.
        
        Args:
            course: Course code to check
            roster: Semester roster
            
        Returns:
            True if tech elective, False otherwise
        """
        print(f"\nDebug check for {course}:")
        result = self.is_tech_elective(course, roster, debug=True)
        print(f"Result: {course} is {'a' if result else 'NOT a'} technical elective\n")
        return result
    
    def check_multiple_courses(self, courses: List[str], roster: str = "FA25", 
                              show_progress: bool = True) -> Dict[str, bool]:
        """
        Check multiple courses for technical elective status.
        
        Args:
            courses: List of course codes
            roster: Semester roster
            show_progress: Whether to show progress updates
            
        Returns:
            Dictionary mapping course codes to their tech elective status
        """
        results = {}
        total = len(courses)
        
        for i, course in enumerate(courses, 1):
            if show_progress:
                print(f"Checking {course}... ({i}/{total})")
            results[course] = self.is_tech_elective(course, roster)
            
            # Show estimated time remaining for large batches
            if show_progress and i % 10 == 0 and total > 50:
                elapsed = self.last_request_time - self._start_time if hasattr(self, '_start_time') else 0
                if elapsed > 0:
                    rate = i / elapsed
                    remaining = (total - i) / rate if rate > 0 else 0
                    print(f"  Estimated time remaining: {remaining:.1f} seconds")
        
        return results  # THIS WAS MISSING!
    
    def check_courses_to_json(self, courses: List[str], roster: str = "FA25", 
                             output_file: str = "tech_electives_results.json",
                             show_progress: bool = True) -> Dict:
        """
        Check multiple courses and save results to JSON file.
        
        Args:
            courses: List of course codes
            roster: Semester roster
            output_file: Path to output JSON file
            show_progress: Whether to show progress updates
            
        Returns:
            Dictionary with results and metadata
        """
        import datetime
        
        self._start_time = time.time()
        
        # Handle empty input
        if not courses:
            print("No courses provided to check.")
            return None
        
        print(f"Starting check of {len(courses)} courses...")
        print(f"Note: Due to API rate limiting (1 req/sec), this may take up to {len(courses)*0.5:.1f} seconds")
        print(f"(Actual time will be less due to caching of repeated prerequisites)\n")
        
        # Get results (simple dict of course -> bool)
        results = self.check_multiple_courses(courses, roster, show_progress)
        
        # Handle complete failure
        if results is None:
            print("ERROR: Failed to check courses")
            return None
        
        # Separate tech electives from non-tech electives
        tech_electives = [course for course, is_tech in results.items() if is_tech]
        non_tech_electives = [course for course, is_tech in results.items() if not is_tech]
        
        # Create detailed JSON output
        output_data = {
            "metadata": {
                "total_courses_checked": len(courses),
                "tech_electives_found": len(tech_electives),
                "non_tech_electives": len(non_tech_electives),
                "roster": roster,
                "acceptable_prerequisites": list(self.acceptable_prerequisites),
                "check_date": datetime.datetime.now().isoformat(),
                "execution_time_seconds": time.time() - self._start_time
            },
            "results": results,
            "tech_electives": tech_electives,
            "non_tech_electives": non_tech_electives
        }
        
        # Save to JSON file
        try:
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            print(f"\n✓ Results saved to {output_file}")
            print(f"  Tech Electives Found: {len(tech_electives)}")
            print(f"  Non-Tech Electives: {len(non_tech_electives)}")
            print(f"  Total Time: {output_data['metadata']['execution_time_seconds']:.1f} seconds")
            
        except Exception as e:
            print(f"ERROR: Failed to save results to {output_file}: {e}")
            return output_data  # Return data even if file save fails
        
        return output_data
    
    def load_courses_from_file(self, filepath: str, file_format: str = "auto") -> List[str]:
        """
        Load course codes from a file.
        
        Args:
            filepath: Path to file containing course codes
            file_format: 'txt' (one per line), 'csv', or 'auto' to detect
            
        Returns:
            List of course codes
        """
        courses = []
        
        if file_format == "auto":
            file_format = "csv" if filepath.endswith('.csv') else "txt"
        
        try:
            if file_format == "csv":
                import csv
                with open(filepath, 'r') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        # Assume course codes are in first column
                        if row and row[0].strip():
                            courses.append(row[0].strip())
            else:  # txt format
                with open(filepath, 'r') as f:
                    courses = [line.strip() for line in f if line.strip()]
            
            print(f"Loaded {len(courses)} courses from {filepath}")
            return courses
            
        except Exception as e:
            print(f"Error loading file {filepath}: {e}")
            return []


# Example usage
if __name__ == "__main__":
    # Define acceptable prerequisite courses for tech electives
    # IMPORTANT: Update this list with YOUR actual acceptable prerequisites!
    # These are just examples - you need to replace with the real requirements
    acceptable_prereqs = [
        "CS 2110",  # Object-Oriented Programming and Data Structures
        "CS 2112",  # Object-Oriented Design and Data Structures - Honors
        "CS 2800",  # Discrete Structures
        "CS 3110",  # Data Structures and Functional Programming
        "CS 3410",  # Computer System Organization and Programming
        "CS 3420",  # Embedded Systems
        "MATH 2940",  # Linear Algebra for Engineers
        "ECE 2300",  # Digital Logic and Computer Organization
        # Add ALL acceptable prerequisites from your requirements here!
    ]
    
    # Create checker instance
    checker = CornellTechElectiveChecker(acceptable_prereqs)
    
    # Example 1: Debug a single course to see why it's failing
    print("=" * 60)
    print("DEBUGGING MODE - Checking prerequisite chain:")
    print("=" * 60)
    checker.check_single_course_debug("CS 4820")
    
    # Example 2: Check multiple courses with JSON output
    print("=" * 60)
    print("BATCH CHECK:")
    print("=" * 60)
    courses_to_check = ["CS 4820", "CS 4410", "INFO 3300", "CS 4700", "CS 4780"]
    output = checker.check_courses_to_json(
        courses_to_check, 
        roster="FA25",
        output_file="tech_electives_results.json"
    )
    
    if output:
        print(f"\nFound {output['metadata']['tech_electives_found']} tech electives out of {len(courses_to_check)} courses")
        if output['metadata']['tech_electives_found'] == 0:
            print("\n⚠️  No tech electives found! Possible issues:")
            print("   1. The acceptable_prereqs list might be incomplete")
            print("   2. The courses might not have prerequisites in the API")
            print("   3. The prerequisite chain might not reach the acceptable list")
            print("\nRun debug mode on a specific course to see its prerequisite chain.")
    
    # Example 3: Load and check 1,000+ courses from a file
    # courses_from_file = checker.load_courses_from_file("courses_to_check.txt")
    # if courses_from_file:
    #     output = checker.check_courses_to_json(
    #         courses_from_file,
    #         roster="FA25",
    #         output_file="batch_results_1000.json",
    #         show_progress=True
    #     )