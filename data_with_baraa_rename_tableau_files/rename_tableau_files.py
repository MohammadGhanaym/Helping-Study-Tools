import os
import re
import shutil

def extract_course_number(filename):
    """
    Extract the course number from the filename pattern '#Tableau Course #X'
    Returns the number as an integer, or None if pattern not found
    """
    pattern = r'#Tableau Course #(\d+)'
    match = re.search(pattern, filename)
    if match:
        return int(match.group(1))
    return None

def rename_files_with_course_numbers(folder_path):
    """
    Rename files in the given folder by adding course numbers at the beginning
    """
    if not os.path.exists(folder_path):
        print(f"Error: The folder path '{folder_path}' does not exist.")
        return
    
    if not os.path.isdir(folder_path):
        print(f"Error: '{folder_path}' is not a directory.")
        return
    
    # Get all files in the directory
    files = os.listdir(folder_path)
    
    # Filter for files that contain the Tableau course pattern
    tableau_files = []
    for file in files:
        if os.path.isfile(os.path.join(folder_path, file)):
            course_num = extract_course_number(file)
            if course_num is not None:
                tableau_files.append((file, course_num))
    
    if not tableau_files:
        print("No files found with the '#Tableau Course #X' pattern.")
        return
    
    print(f"Found {len(tableau_files)} files with Tableau course numbers:")
    
    # Sort by course number for better display
    tableau_files.sort(key=lambda x: x[1])
    
    renamed_count = 0
    
    for original_filename, course_number in tableau_files:
        # Create new filename with course number at the beginning
        new_filename = f"{course_number:02d} - {original_filename}"
        
        # Full paths
        original_path = os.path.join(folder_path, original_filename)
        new_path = os.path.join(folder_path, new_filename)
        
        # Check if the new filename already exists
        if os.path.exists(new_path):
            print(f"Skipping '{original_filename}' - target file already exists: '{new_filename}'")
            continue
        
        try:
            # Rename the file
            os.rename(original_path, new_path)
            print(f"Renamed: '{original_filename}' -> '{new_filename}'")
            renamed_count += 1
        except Exception as e:
            print(f"Error renaming '{original_filename}': {str(e)}")
    
    print(f"\nCompleted! Successfully renamed {renamed_count} files.")

def main():
    """
    Main function to get user input and process files
    """
    print("Tableau Course File Renamer")
    print("=" * 40)
    print("This script will rename files containing '#Tableau Course #X' pattern")
    print("by adding the course number at the beginning of the filename.")
    print()
    
    while True:
        folder_path = input("Enter the path to the folder containing the files: ").strip()
        
        # Remove quotes if user entered them
        if folder_path.startswith('"') and folder_path.endswith('"'):
            folder_path = folder_path[1:-1]
        if folder_path.startswith("'") and folder_path.endswith("'"):
            folder_path = folder_path[1:-1]
        
        if folder_path.lower() in ['quit', 'exit', 'q']:
            print("Exiting...")
            break
        
        if not folder_path:
            print("Please enter a valid folder path or 'quit' to exit.")
            continue
        
        print(f"\nProcessing folder: {folder_path}")
        print("-" * 50)
        
        rename_files_with_course_numbers(folder_path)
        
        print("\n" + "=" * 50)
        another = input("Do you want to process another folder? (y/n): ").strip().lower()
        if another not in ['y', 'yes']:
            break
    
    print("Thank you for using the Tableau Course File Renamer!")

if __name__ == "__main__":
    main()
