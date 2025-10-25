#!/usr/bin/env python3
"""
Image Recovery Script
Recovers all images that ever existed in the git history under a specified folder.
Optimized for performance with parallel processing and efficient git operations.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict


#!/usr/bin/env python3
"""
Image Recovery Script
Recovers all images that ever existed in the git history under a specified folder.
Optimized for performance with parallel processing and efficient git operations.
"""

def run_git_command(args):
    """Run a git command and return the output."""
    try:
        result = subprocess.run(['git'] + args, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}")
        return None

def is_git_repository():
    """Check if we're in a git repository."""
    try:
        subprocess.run(['git', 'rev-parse', '--git-dir'], 
                      capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def get_image_objects(folder):
    """Get all image objects that ever existed in the specified folder (optimized)."""
    print("Scanning git history for image objects...")
    
    # Get all objects that ever existed under the folder in one go
    output = run_git_command(['rev-list', '--objects', '--all', '--', folder])
    if not output:
        return []
    
    # Pre-compile regex for better performance
    image_pattern = re.compile(r'\.(png|jpe?g|gif|webp|bmp|tiff|svg)$', re.IGNORECASE)
    
    # Use dict to efficiently track unique objects by OID
    unique_objects = {}
    
    for line in output.strip().split('\n'):
        if not line.strip():
            continue
            
        # Split only once and limit to 2 parts for efficiency
        parts = line.split(' ', 1)
        if len(parts) == 2:
            oid, path = parts
            if image_pattern.search(path):
                # Keep the first occurrence of each OID (arbitrary choice for duplicates)
                if oid not in unique_objects:
                    unique_objects[oid] = path
    
    return list(unique_objects.items())

def recover_image_batch(oid_path_batch, output_dir):
    """Recover a batch of images in parallel."""
    results = []
    
    for oid, path in oid_path_batch:
        try:
            # Get the basename of the original path
            basename = os.path.basename(path)
            
            # Create output filename with OID to avoid name clashes
            # output_filename = f"{oid}_{basename}"
            output_filename = f"{basename}"
            output_path = os.path.join(output_dir, output_filename)
            
            # Get the file content from git
            result = subprocess.run(['git', 'cat-file', '-p', oid], 
                                   capture_output=True, check=True)
            
            # Write to output file
            with open(output_path, 'wb') as f:
                f.write(result.stdout)
            
            results.append((True, f"Recovered: {path} -> {output_filename}"))
            
        except subprocess.CalledProcessError as e:
            results.append((False, f"Failed to recover {path} (OID: {oid}): {e}"))
        except Exception as e:
            results.append((False, f"Error recovering {path}: {e}"))
    
    return results

def recover_images_parallel(image_objects, output_dir, max_workers=4):
    """Recover images using parallel processing."""
    if not image_objects:
        return 0
    
    # Split work into batches for better efficiency
    batch_size = max(1, len(image_objects) // max_workers)
    batches = [image_objects[i:i + batch_size] for i in range(0, len(image_objects), batch_size)]
    
    recovered_count = 0
    
    print(f"Processing {len(image_objects)} images using {max_workers} workers...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all batches
        future_to_batch = {
            executor.submit(recover_image_batch, batch, output_dir): batch 
            for batch in batches
        }
        
        # Process results as they complete
        for future in as_completed(future_to_batch):
            try:
                results = future.result()
                for success, message in results:
                    if success:
                        recovered_count += 1
                    print(message)
            except Exception as e:
                print(f"Batch processing error: {e}")
    
    return recovered_count

def main():
    """Main function to recover images from git history."""
    # Configuration
    folder = "images"  # Change if needed
    output_dir = "images"
    max_workers = min(8, os.cpu_count() or 4)  # Limit workers to reasonable number
    
    # Check if we're in a git repository
    if not is_git_repository():
        print("Error: Not in a git repository")
        sys.exit(1)
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    print("Starting optimized image recovery from git history...")
    print(f"Looking for images in: {folder}")
    print(f"Output directory: {output_dir}")
    print(f"Using {max_workers} worker threads")
    
    # Get all image objects from git history
    image_objects = get_image_objects(folder)
    
    if not image_objects:
        print(f"No images found in the git history under '{folder}' folder.")
        return
    
    print(f"Found {len(image_objects)} unique image(s) to recover...")
    
    # Recover images in parallel
    recovered_count = recover_images_parallel(image_objects, output_dir, max_workers)
    
    print("\nImage recovery completed!")
    print(f"Recovered {recovered_count} out of {len(image_objects)} images.")
    print(f"Check the '{output_dir}' directory for recovered images.")

if __name__ == "__main__":
    main()