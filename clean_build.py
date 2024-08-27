import os
import shutil

def clean_build():
    # Directories to remove
    build_dirs = ['build', 'dist']
    excluded_dirs = ['env']  # Add directories to exclude

    # Remove build and dist directories
    for dir_name in build_dirs:
        if os.path.exists(dir_name):
            print(f'Removing {dir_name} directory...')
            shutil.rmtree(dir_name)

    # Remove all egg-info and __pycache__ directories, excluding specified ones
    for root, dirs, files in os.walk('.'):
        for dir_name in dirs:
            # Check if the directory is in the excluded list
            if dir_name in excluded_dirs:
                continue
            
            if dir_name.endswith('.egg-info'):
                egg_info_path = os.path.join(root, dir_name)
                print(f'Removing {egg_info_path} directory...')
                shutil.rmtree(egg_info_path)
            elif dir_name == '__pycache__':
                pycache_path = os.path.join(root, dir_name)
                print(f'Removing {pycache_path} directory...')
                shutil.rmtree(pycache_path)

    print('Clean build completed.')

if __name__ == '__main__':
    clean_build()
