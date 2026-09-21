import os
import glob

def clear_txt_files():
    """Clear all .txt files in the current directory"""
    txt_files = glob.glob("*.txt")
    
    if not txt_files:
        print("No .txt files found.")
        return
    
    for file_path in txt_files:
        try:
            with open(file_path, 'w') as f:
                f.write('')
            print(f"Cleared: {file_path}")
        except Exception as e:
            print(f"Error clearing {file_path}: {e}")
    
    print(f"Done. Cleared {len(txt_files)} file(s).")

if __name__ == "__main__":
    clear_txt_files()