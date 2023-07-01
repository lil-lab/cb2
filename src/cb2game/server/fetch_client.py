import os
import urllib.request
import zipfile

print("Downloading client...")

# Define the path where the file will be downloaded and extracted.
# From this file, it's 'www/'
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "www")

# Download the zip file
try:
    url = "https://github.com/lil-lab/cb2/releases/latest/download/WebGL.zip"
    print(f"Downloading from: {url}")
    filename = os.path.join(path, "WebGL.zip")
    urllib.request.urlretrieve(url, filename)
except urllib.error.URLError as e:
    # If it's an SSL CERTIFICATE_VERIFY_FAILED error, recommend the user installs:
    # /Applications/Python\ 3.10/Install\ Certificates.command
    print(e)
    print(
        "If you're on Mac and getting an SSL Certificate not verified error, try running:"
    )
    print("/Applications/Python\ 3.10/Install\ Certificates.command")
    exit(1)

print("Decompressing client.")

extract_to_path = os.path.join(path, "WebGL")

# Delete the old folder if it exists
if os.path.exists(extract_to_path):
    import shutil

    shutil.rmtree(extract_to_path)

# Unzip the file
with zipfile.ZipFile(filename, "r") as zip_ref:
    zip_ref.extractall(path)

print("Done.")
