import os
import sys

def load_html_template(filename="template.html"):
    """Safely loads the HTML template from an external file to prevent string syntax errors."""
    if not os.path.exists(filename):
        print(f"Error: Template file '{filename}' not found.")
        sys.exit(1)
        
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()

def main():
    print("Running stock screener...")
    
    # Load the HTML content cleanly from the separate template file
    html_content = load_html_template("template.html")
    
    # Example processing/output step
    output_filename = "output.html"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Successfully generated {output_filename}!")

if __name__ == "__main__":
    main()
