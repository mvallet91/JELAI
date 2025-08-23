import os
import shutil
import json
import time
import httpx

def sync_course_materials():
    course_id = os.environ.get('SELECTED_COURSE_ID')
    if not course_id:
        print("No course selected, skipping material sync.")
        return

    middleware_url = os.environ.get('MIDDLEWARE_URL', 'http://middleware:8005')
    dest_dir = '/home/jovyan/work'
    
    try:
        with httpx.Client() as client:
            # We need an admin/teacher token to get course details, but the spawner does not provide one.
            # For now, we'll rely on a shared secret or a pre-configured admin user for this internal call.
            # This is a security consideration that needs to be addressed.
            # Using a placeholder 'admin' user for now.
            headers = {'Authorization': 'Bearer admin', 'X-JELAI-ADMIN': 'true'}
            resp = client.get(f"{middleware_url}/api/courses/{course_id}", headers=headers)
            
            if resp.status_code == 200:
                course = resp.json()
                materials = course.get('materials', [])
                
                for material in materials:
                    # The material name is the filename. We need to download it from the middleware.
                    material_url = f"{middleware_url}/api/materials/{material}"
                    dest_path = os.path.join(dest_dir, material)
                    
                    # Avoid re-downloading if file exists
                    if os.path.exists(dest_path):
                        continue

                    print(f"Downloading {material}...")
                    with client.stream("GET", material_url, headers=headers) as r:
                        if r.status_code == 200:
                            with open(dest_path, 'wb') as f:
                                for chunk in r.iter_bytes():
                                    f.write(chunk)
                            print(f"Successfully downloaded {material}")
                        else:
                            print(f"Failed to download {material}: {r.status_code}")
            else:
                print(f"Failed to get course details for {course_id}: {resp.status_code}")

    except Exception as e:
        print(f"Error syncing course materials: {e}")

if __name__ == "__main__":
    # Run once at startup
    sync_course_materials()
