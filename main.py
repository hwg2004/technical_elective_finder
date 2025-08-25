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
            return prerequisites
        
        # Parse prerequisites from text
        # Look for patterns like "CS 2110", "MATH 2940", etc.
        pattern = r'([A-Z]+)\s*(\d+)'
        matches = re.findall(pattern, prereq_text.upper())
        
        for subject, number in matches:
            prerequisites.add(f"{subject} {number}")
        
        return prerequisites
    
    def is_tech_elective(self, course: str, roster: str = "FA25", 
                        visited: Optional[Set[str]] = None, depth: int = 0, max_depth: int = 5) -> bool:
        """
        Check if a course is a technical elective by recursively checking prerequisites.
        
        Args:
            course: Course code (e.g., "CS 4820")
            roster: Semester roster (default 'FA25')
            visited: Set of already visited courses (for cycle detection)
            depth: Current recursion depth
            max_depth: Maximum recursion depth to prevent infinite loops
            
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
            return True
        
        # Avoid cycles
        if course in visited:
            return False
        
        visited.add(course)
        
        # Parse course code
        subject, number = self._parse_course_code(course)
        if not subject or not number:
            return False
        
        # Fetch course data
        course_data = self._fetch_course_data(subject, number, roster)
        if not course_data:
            return False
        
        # Extract prerequisites
        prerequisites = self._extract_prerequisites(course_data, roster)
        
        # Check if any prerequisite qualifies
        for prereq in prerequisites:
            if self.is_tech_elective(prereq, roster, visited.copy(), depth + 1, max_depth):
                return True
        
        return False
    
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
            Dictionary with results, errors, and metadata
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
        
        # Get results (now includes errors)
        check_output = self.check_multiple_courses(courses, roster, show_progress)
        
        # Handle complete failure
        if check_output is None:
            print("ERROR: Failed to check courses")
            return None
        
        results = check_output.get('results', {})
        errors = check_output.get('errors', {})
        
        # Separate successful checks from failed ones
        successful_results = {k: v for k, v in results.items() if v is not None}
        tech_electives = [course for course, is_tech in successful_results.items() if is_tech]
        non_tech_electives = [course for course, is_tech in successful_results.items() if not is_tech]
        
        # Create detailed JSON output
        output_data = {
            "metadata": {
                "total_courses_checked": len(courses),
                "successfully_checked": len(successful_results),
                "failed_checks": len(errors),
                "tech_electives_found": len(tech_electives),
                "non_tech_electives": len(non_tech_electives),
                "roster": roster,
                "acceptable_prerequisites": list(self.acceptable_prerequisites),
                "check_date": datetime.datetime.now().isoformat(),
                "execution_time_seconds": time.time() - self._start_time,
                "success": check_output.get('success', False)
            },
            "results": results,
            "tech_electives": tech_electives,
            "non_tech_electives": non_tech_electives,
            "errors": errors
        }
        
        # Save to JSON file
        try:
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            print(f"\n✓ Results saved to {output_file}")
            print(f"  Successfully Checked: {len(successful_results)}/{len(courses)}")
            print(f"  Tech Electives Found: {len(tech_electives)}")
            print(f"  Non-Tech Electives: {len(non_tech_electives)}")
            if errors:
                print(f"  ⚠ Failed Checks: {len(errors)}")
                print(f"    Failed courses: {', '.join(list(errors.keys())[:5])}")
                if len(errors) > 5:
                    print(f"    ... and {len(errors)-5} more")
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
    # You would replace this with your actual list
    acceptable_prereqs = [
        "CS 2110",  # Object-Oriented Programming and Data Structures
        "CS 2112",  # Object-Oriented Design and Data Structures - Honors
        "CS 2800",  # Discrete Structures
        "MATH 2940",  # Linear Algebra for Engineers
        "ECE 2300",  # Digital Logic and Computer Organization
        # Add more acceptable prerequisites here
    ]
    
    # Create checker instance
    checker = CornellTechElectiveChecker(acceptable_prereqs)
    
    # Example 1: Check a single course
    course_to_check = "CS 4820"  # Algorithms
    is_elective = checker.is_tech_elective(course_to_check)
    print(f"{course_to_check} is {'a' if is_elective else 'NOT a'} technical elective\n")
    
    # Example 2: Check multiple courses with JSON output
    courses_to_check = ["CS 4820", "CS 4410", "INFO 3300", "CS 4700", "CS 4780", "INVALID 9999"]
    output = checker.check_courses_to_json(
        courses_to_check, 
        roster="FA25",
        output_file="tech_electives_results.json"
    )
    
    # Check if everything succeeded
    if output and output['metadata']['failed_checks'] > 0:
        print(f"\nWarning: {output['metadata']['failed_checks']} courses could not be checked")
        print("See 'errors' section in JSON for details")
    
    # Example 3: Check a large batch of courses (e.g., all CS 4000-level courses)
    large_batch = [f"CS {num}" for num in range(4000, 4999, 10)]  # Sample of CS 4000-level
    
    # For very large batches (100+ courses), you might want to save progress
    # in case of interruption
    print("\n\nChecking large batch...")
    large_output = checker.check_courses_to_json(
        large_batch,
        roster="FA25", 
        output_file="large_batch_results.json",
        show_progress=True
    )
    
    # Handle results
    if large_output:
        if large_output['metadata']['success']:
            print("All courses checked successfully!")
        else:
            print(f"Some courses failed - check errors in JSON")
    else:
        print("ERROR: Check failed completely")
    
    # Example 4: Load courses from a text file and check them
    # Assuming you have a file with one course per line
    """
    # For checking 1,000+ courses from a file:
    courses_from_file = checker.load_courses_from_file("courses_to_check.txt")
    
    if courses_from_file:
        # This will handle 1,000+ courses efficiently
        output = checker.check_courses_to_json(
            courses_from_file,
            roster="FA25",
            output_file="batch_results_1000.json",
            show_progress=True  # Shows progress and time estimates
        )
        
        # Check results
        if output:
            success_rate = output['metadata']['successfully_checked'] / output['metadata']['total_courses_checked']
            print(f"\nSuccess rate: {success_rate:.1%}")
            
            # The JSON output will include:
            # - Complete results for all courses (None for failed checks)
            # - List of which are tech electives
            # - List of which are not
            # - Errors dictionary with failure reasons
            # - Metadata including execution time
        else:
            print("Failed to check courses")
    else:
        print("Failed to load courses from file")
    """