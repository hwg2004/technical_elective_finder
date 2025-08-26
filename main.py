import json
import re
from typing import Dict, Set, List, Tuple, Optional
from collections import defaultdict, deque

class PrerequisiteChecker:
    def __init__(self, courses_json_path: str, acceptable_base_courses: List[str]):
        """
        Initialize with a JSON file of courses and list of acceptable base courses.
        
        Args:
            courses_json_path: Path to JSON file with course data
            acceptable_base_courses: List of courses that are acceptable prerequisites
        """
        self.courses = {}
        self.prerequisite_graph = defaultdict(set)  # course -> set of prerequisites
        self.acceptable_base = set(acceptable_base_courses)
        self.load_courses(courses_json_path)
        self.build_prerequisite_graph()
        
    def load_courses(self, json_path: str):
        """Load courses from JSON file."""
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                for course in data:
                    course_code = f"{course['subject']} {course['number']}"
                    self.courses[course_code] = course.get('prerequisites', '')
            print(f"Loaded {len(self.courses)} courses from {json_path}")
        except Exception as e:
            print(f"Error loading JSON: {e}")
            
    def parse_prerequisites(self, prereq_text: str) -> Set[str]:
        """
        Parse prerequisite text to extract course codes.
        
        Args:
            prereq_text: Text describing prerequisites
            
        Returns:
            Set of prerequisite course codes
        """
        prerequisites = set()
        
        # Pattern to match course codes like "MATH 1920" or "MATH 2210-MATH 2240"
        pattern = r'([A-Z]+)\s+(\d{4})'
        matches = re.findall(pattern, prereq_text)
        
        for subject, number in matches:
            prerequisites.add(f"{subject} {number}")
            
        return prerequisites
    
    def build_prerequisite_graph(self):
        """Build a directed graph of prerequisites."""
        for course, prereq_text in self.courses.items():
            prerequisites = self.parse_prerequisites(prereq_text)
            self.prerequisite_graph[course] = prerequisites
            
        print(f"Built prerequisite graph with {len(self.prerequisite_graph)} courses")
    
    def is_tech_elective(self, course: str, visited: Optional[Set[str]] = None) -> bool:
        """
        Check if a course is a technical elective by checking if it or its
        prerequisites are in the acceptable base courses.
        
        Args:
            course: Course code to check
            visited: Set of already visited courses (for cycle detection)
            
        Returns:
            True if the course is a technical elective
        """
        if visited is None:
            visited = set()
            
        # Base case: course is directly in acceptable list
        if course in self.acceptable_base:
            return True
            
        # Avoid cycles
        if course in visited:
            return False
            
        visited.add(course)
        
        # Check prerequisites recursively
        prerequisites = self.prerequisite_graph.get(course, set())
        for prereq in prerequisites:
            if self.is_tech_elective(prereq, visited.copy()):
                return True
                
        return False
    
    def get_prerequisite_chain(self, course: str, visited: Optional[Set[str]] = None, 
                              depth: int = 0) -> List[str]:
        """
        Get the complete prerequisite chain for a course.
        
        Args:
            course: Course code
            visited: Set of already visited courses
            depth: Current recursion depth
            
        Returns:
            List of strings showing the prerequisite chain
        """
        if visited is None:
            visited = set()
            
        chain = []
        indent = "  " * depth
        
        if course in self.acceptable_base:
            chain.append(f"{indent}✓ {course} (acceptable prerequisite)")
            return chain
            
        if course in visited:
            chain.append(f"{indent}↻ {course} (already visited - cycle)")
            return chain
            
        visited.add(course)
        prerequisites = self.prerequisite_graph.get(course, set())
        
        if not prerequisites:
            chain.append(f"{indent}• {course} (no prerequisites)")
        else:
            chain.append(f"{indent}→ {course} requires: {', '.join(sorted(prerequisites))}")
            for prereq in sorted(prerequisites):
                chain.extend(self.get_prerequisite_chain(prereq, visited.copy(), depth + 1))
                
        return chain
    
    def check_courses(self, courses_to_check: List[str]) -> Dict[str, bool]:
        """
        Check multiple courses for tech elective status.
        
        Args:
            courses_to_check: List of course codes
            
        Returns:
            Dictionary mapping courses to their tech elective status
        """
        results = {}
        for course in courses_to_check:
            results[course] = self.is_tech_elective(course)
        return results
    
    def generate_report(self, courses_to_check: List[str], output_file: str = "results.json"):
        """
        Generate a detailed report for multiple courses.
        
        Args:
            courses_to_check: List of course codes
            output_file: Path to save JSON report
        """
        print("\n" + "="*60)
        print("TECHNICAL ELECTIVE CHECK REPORT")
        print("="*60)
        
        results = {}
        tech_electives = []
        non_tech_electives = []
        
        for course in courses_to_check:
            is_tech = self.is_tech_elective(course)
            results[course] = is_tech
            
            if is_tech:
                tech_electives.append(course)
            else:
                non_tech_electives.append(course)
                
            print(f"\n{course}: {'✓ TECH ELECTIVE' if is_tech else '✗ NOT TECH ELECTIVE'}")
            chain = self.get_prerequisite_chain(course)
            for line in chain[:5]:  # Show first 5 levels
                print(line)
            if len(chain) > 5:
                print("  ... (chain continues)")
        
        # Save to JSON
        report = {
            "acceptable_prerequisites": list(self.acceptable_base),
            "courses_checked": len(courses_to_check),
            "tech_electives_found": len(tech_electives),
            "results": results,
            "tech_electives": tech_electives,
            "non_tech_electives": non_tech_electives
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        print("\n" + "="*60)
        print(f"SUMMARY: {len(tech_electives)}/{len(courses_to_check)} courses are tech electives")
        print(f"Results saved to: {output_file}")
        print("="*60)
    
    def find_all_tech_electives(self) -> List[str]:
        """
        Find ALL courses that qualify as tech electives.
        
        Returns:
            List of all courses that are tech electives
        """
        tech_electives = []
        for course in self.courses.keys():
            if self.is_tech_elective(course):
                tech_electives.append(course)
        return sorted(tech_electives)
    
    def visualize_graph_stats(self):
        """Print statistics about the prerequisite graph."""
        print("\n" + "="*60)
        print("PREREQUISITE GRAPH STATISTICS")
        print("="*60)
        
        # Courses with no prerequisites
        no_prereqs = [c for c, p in self.prerequisite_graph.items() if not p]
        print(f"Courses with no prerequisites: {len(no_prereqs)}")
        
        # Most common prerequisites
        prereq_counts = defaultdict(int)
        for prereqs in self.prerequisite_graph.values():
            for prereq in prereqs:
                prereq_counts[prereq] += 1
        
        print("\nTop 10 most common prerequisites:")
        for prereq, count in sorted(prereq_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {prereq}: required by {count} courses")
        
        # Courses with most prerequisites
        print("\nCourses with most prerequisites:")
        sorted_by_prereqs = sorted(self.prerequisite_graph.items(), 
                                  key=lambda x: len(x[1]), reverse=True)[:5]
        for course, prereqs in sorted_by_prereqs:
            print(f"  {course}: {len(prereqs)} prerequisites")


def main():
    """Main function to run the prerequisite checker."""
    
    # Path to your JSON file
    json_file = "courses.json"  # Change this to your JSON file path
    
    # Define acceptable base prerequisite courses
    # These are courses that, if found in a prerequisite chain, make a course a tech elective
    acceptable_prerequisites = [
        # Core CS courses
        "CS 2110",   # Object-Oriented Programming
        "CS 2112",   # OOP Honors
        "CS 2800",   # Discrete Structures
        "CS 3110",   # Functional Programming
        "CS 3410",   # Computer System Organization
        
        # Core Math courses
        "MATH 1920", # Multivariable Calculus
        "MATH 2210", # Linear Algebra
        "MATH 2220", # Multivariable Calculus
        "MATH 2230", # Theoretical Linear Algebra
        "MATH 2940", # Linear Algebra for Engineers
        
        # Core Engineering
        "ECE 2300",  # Digital Logic
        "ENGRD 2110", # Object-Oriented Programming
        
        # Add more as needed based on your requirements
    ]
    
    # Initialize checker
    print("Initializing Prerequisite Checker...")
    checker = PrerequisiteChecker(json_file, acceptable_prerequisites)
    
    # Show graph statistics
    checker.visualize_graph_stats()
    
    # Check specific courses
    courses_to_check = [
        "MATH 4310",  # Linear Algebra
        "MATH 4410",  # Combinatorics
        "CS 4820",    # Algorithms (if in your JSON)
        "MATH 3040",  # Prove It!
        "MATH 3110",  # Analysis
    ]
    
    # Generate detailed report
    print("\nChecking specific courses...")
    checker.generate_report(courses_to_check, "tech_electives_report.json")
    
    # Find ALL tech electives in the dataset
    print("\nFinding all tech electives in the dataset...")
    all_tech_electives = checker.find_all_tech_electives()
    print(f"Found {len(all_tech_electives)} total tech electives")
    
    # Save complete list
    with open("all_tech_electives.json", 'w') as f:
        json.dump({
            "total_courses": len(checker.courses),
            "tech_electives_count": len(all_tech_electives),
            "tech_electives": all_tech_electives
        }, f, indent=2)
    print("Complete list saved to: all_tech_electives.json")
    
    # Interactive mode (optional)
    print("\n" + "="*60)
    print("Interactive Mode - Enter course codes to check (or 'quit' to exit)")
    print("="*60)
    while True:
        course = input("\nEnter course code (e.g., MATH 4310): ").strip().upper()
        if course == 'QUIT':
            break
        if course in checker.courses:
            is_tech = checker.is_tech_elective(course)
            print(f"{course}: {'✓ TECH ELECTIVE' if is_tech else '✗ NOT TECH ELECTIVE'}")
            print("\nPrerequisite chain:")
            chain = checker.get_prerequisite_chain(course)
            for line in chain[:10]:
                print(line)
        else:
            print(f"Course {course} not found in database")


if __name__ == "__main__":
    main()