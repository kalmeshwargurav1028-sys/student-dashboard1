import os
from pymongo import MongoClient
import gridfs

# Connect to MongoDB
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(mongo_uri)
db = client['kalmeshwar']

# Initialize GridFS
fs = gridfs.GridFS(db)

# Create a directory to save the downloaded files
output_dir = "downloaded_files"
os.makedirs(output_dir, exist_ok=True)

print(f"Downloading files to the '{output_dir}' directory...")

# Find all files stored in GridFS
files = fs.find()
count = 0

for file in files:
    file_id = file._id
    filename = file.filename
    
    # In case a file was uploaded without a filename
    if not filename:
        filename = f"unknown_{file_id}"
        
    output_path = os.path.join(output_dir, filename)
    
    try:
        # Read the file from GridFS and write it to our local folder
        with open(output_path, 'wb') as f:
            f.write(file.read())
        print(f"✅ Saved: {filename}")
        count += 1
    except Exception as e:
        print(f"❌ Failed to save {filename}: {e}")

print(f"\nDone! Successfully extracted {count} files. You can now view them manually in the '{output_dir}' folder.")
