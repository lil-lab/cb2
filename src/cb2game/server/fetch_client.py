import os
import shutil
import urllib.request
import zipfile

import fire

from cb2game.server.util import PackageRoot
from cb2game.util.confgen import slow_type


def main(local_client_path: str = None):
    if local_client_path:
        slow_type("Copying client from local path.")
        path = PackageRoot() / "server/www"
        extract_to_path = os.path.join(path, "WebGL")
        if os.path.exists(extract_to_path):
            # Rename to .old
            shutil.move(extract_to_path, extract_to_path + ".old")
        shutil.copytree(local_client_path, extract_to_path)
        slow_type("Done.")
        return

    slow_type("Downloading client...")

    # Define the path where the file will be downloaded and extracted.
    # From this file, it's 'www/'
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "www")

    # Download the zip file
    try:
        url = "https://github.com/lil-lab/cb2/releases/latest/download/WebGL.zip"
        slow_type(f"Downloading from: {url}")
        filename = os.path.join(path, "WebGL.zip")
        urllib.request.urlretrieve(url, filename)
    except urllib.error.URLError as e:
        # If it's an SSL CERTIFICATE_VERIFY_FAILED error, recommend the user installs:
        # /Applications/Python\ 3.10/Install\ Certificates.command
        slow_type(e)
        slow_type(
            "If you're on Mac and getting an SSL Certificate not verified error, try running:"
        )
        slow_type("/Applications/Python\ 3.10/Install\ Certificates.command")
        exit(1)

    slow_type("Decompressing client.")

    extract_to_path = os.path.join(path, "WebGL")

    # Delete the old folder if it exists
    if os.path.exists(extract_to_path):
        shutil.rmtree(extract_to_path)

    # Unzip the file
    with zipfile.ZipFile(filename, "r") as zip_ref:
        zip_ref.extractall(path)

    slow_type("Done.")


if __name__ == "__main__":
    fire.Fire(main)
