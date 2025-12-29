import os

target_dir = "inventory agent support-locally"
print(f"Checking directory: {target_dir}")
if os.path.exists(target_dir):
    print("Directory exists")
    files = os.listdir(target_dir)
    print("Files:", files)
    
    dump_file = os.path.join(target_dir, "converted_dump.sql")
    if os.path.exists(dump_file):
        print(f"Reading first 20 lines of {dump_file}...")
        try:
            with open(dump_file, 'r', encoding='utf-8', errors='ignore') as f:
                for i in range(20):
                    print(f.readline().strip())
        except Exception as e:
            print(f"Error reading file: {e}")
else:
    print("Directory does not exist")
    # Try listing current directory to match name
    print("Current directory content:")
    print(os.listdir('.'))
