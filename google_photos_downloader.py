#!/usr/bin/env python3

"""
Google Photos Album Downloader

This script downloads Google Photos albums using the Google Photos API.
It authenticates using OAuth 2.0, allowing users to list albums,
download specific albums by ID, or download all albums. Each album
is saved as a separate .zip file.
"""

import argparse
import os
import pickle
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

# --- Configuration ---
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
DOWNLOAD_DIR = Path('google_photos_downloads')
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
API_SERVICE_NAME = 'photoslibrary'
API_VERSION = 'v1'

# --- README Content ---
README_TEXT = """
# Google Photos Album Downloader

This script downloads your Google Photos albums using the Google Photos API.

## Features

- Authenticates using OAuth 2.0 (requires `credentials.json`).
- Lists all available albums with their IDs.
- Downloads a specific album by its ID.
- Downloads all albums.
- Saves each album as a separate `.zip` file in a specified directory.
- Handles API pagination for albums and media items.
- Retries failed downloads for individual media items.
- Provides informative console output.

## Prerequisites

1.  **Python 3.7+**
2.  **Google Cloud Project:**
    - Go to the [Google Cloud Console](https://console.cloud.google.com/).
    - Create a new project or select an existing one.
    - Enable the **Google Photos Library API**.
    - Create OAuth 2.0 Credentials:
        - Go to "APIs & Services" > "Credentials".
        - Click "Create Credentials" > "OAuth client ID".
        - Select "Desktop app" as the Application type.
        - Give it a name (e.g., "Photos Downloader").
        - Click "Create".
        - Download the JSON file. Rename it to `credentials.json` and place it in the same directory as this script.
3.  **Python Libraries:** Install the required libraries:
    ```bash
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib requests
    ```

## Usage

Place the `credentials.json` file in the same directory as the script (`google_photos_downloader.py`).

Run the script from your terminal:

```bash
python google_photos_downloader.py [OPTIONS]
```

**Options:**

-   `--list`: List all album names and their corresponding IDs, then exit.
-   `--album-id <ALBUM_ID>`: Download only the album with the specified ID.
-   `--all`: Download all albums found in your Google Photos library.
-   `--help`: Show the help message and exit.

**First Run:**

The first time you run the script, it will open a browser window asking you to authorize access to your Google Photos library. Follow the prompts to grant permission. A `token.json` file will be created to store your authorization token for future runs.

**Output:**

Downloaded albums will be saved as `.zip` files in the `google_photos_downloads` directory (created if it doesn't exist).

## Error Handling

- The script includes basic error handling for API requests and file operations.
- It will retry downloading individual media items a few times if errors occur.
- Ensure your `credentials.json` is correctly configured and placed.
- If you encounter persistent authentication issues, try deleting the `token.json` file and re-running the script to re-authenticate.

## Limitations

- The Google Photos API does not provide original quality downloads for all items via the standard download URLs. Videos, in particular, might be transcoded. Use Google Takeout for full-fidelity backups.
- Shared albums where you are not the owner might have limitations.
- Very large albums might take a significant amount of time and bandwidth to download.
"""

# --- Authentication ---
def authenticate() -> Any:
    """Handles OAuth 2.0 authentication."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        except (pickle.UnpicklingError, EOFError, FileNotFoundError) as e:
            print(f"Error loading token file: {e}. Need to re-authenticate.")
            creds = None # Force re-authentication

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing access token...")
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}. Need to re-authenticate.")
                if os.path.exists(TOKEN_FILE):
                    os.remove(TOKEN_FILE) # Remove invalid token file
                creds = None # Force re-authentication
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"Error: Credentials file '{CREDENTIALS_FILE}' not found.")
                print("Please download it from Google Cloud Console and place it here.")
                exit(1)
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES)
                # Pass a specific port (e.g., 8080) or let it choose dynamically (port=0)
                # Using a fixed port can sometimes help in restricted environments.
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"Error during authentication flow: {e}")
                exit(1)

        # Save the credentials for the next run
        try:
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
            print(f"Authentication successful. Token saved to {TOKEN_FILE}")
        except IOError as e:
            print(f"Error saving token file: {e}")
            # Continue execution even if token saving fails, but warn user.

    if not creds:
        print("Authentication failed.")
        exit(1)

    return creds

# --- Google Photos API Service ---
def get_photos_service(credentials: Any) -> Resource:
    """Builds and returns the Google Photos API service."""
    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials, static_discovery=False)
        return service
    except Exception as e:
        print(f"Error building Google Photos service: {e}")
        exit(1)

# --- Album Operations ---
def list_albums(service: Resource) -> List[Dict[str, Any]]:
    """Fetches and returns a list of all albums."""
    albums = []
    next_page_token = None
    print("Fetching albums...")
    try:
        while True:
            results = service.albums().list(
                pageSize=50,  # Max 50 per page
                pageToken=next_page_token
            ).execute()

            found_albums = results.get('albums', [])
            if found_albums:
                albums.extend(found_albums)
                print(f"Found {len(found_albums)} albums (Total: {len(albums)})...")
            else:
                 print("No albums found on this page.")

            next_page_token = results.get('nextPageToken')
            if not next_page_token:
                break
            time.sleep(0.5) # Small delay between pages
    except HttpError as error:
        print(f"An API error occurred while listing albums: {error}")
    except Exception as e:
        print(f"An unexpected error occurred while listing albums: {e}")

    print(f"Finished fetching. Total albums found: {len(albums)}")
    return albums

def get_album_by_id(service: Resource, album_id: str) -> Optional[Dict[str, Any]]:
    """Fetches a specific album by its ID."""
    print(f"Fetching album details for ID: {album_id}...")
    try:
        album = service.albums().get(albumId=album_id).execute()
        print(f"Found album: '{album.get('title', 'Untitled')}'")
        return album
    except HttpError as error:
        if error.resp.status == 404:
            print(f"Error: Album with ID '{album_id}' not found.")
        else:
            print(f"An API error occurred while fetching album {album_id}: {error}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while fetching album {album_id}: {e}")
        return None

# --- Media Item Operations ---
def get_album_media_items(service: Resource, album_id: str) -> List[Dict[str, Any]]:
    """Fetches all media items for a given album ID."""
    media_items = []
    next_page_token = None
    print(f"Fetching media items for album ID: {album_id}...")
    try:
        while True:
            results = service.mediaItems().search(
                body={
                    'albumId': album_id,
                    'pageSize': 100,  # Max 100 per page
                    'pageToken': next_page_token
                }
            ).execute()

            found_items = results.get('mediaItems', [])
            if found_items:
                 media_items.extend(found_items)
                 print(f"Found {len(found_items)} media items (Total: {len(media_items)})...")
            else:
                print("No media items found on this page.")


            next_page_token = results.get('nextPageToken')
            if not next_page_token:
                break
            time.sleep(0.5) # Small delay between pages
    except HttpError as error:
        print(f"An API error occurred while fetching media items for album {album_id}: {error}")
    except Exception as e:
        print(f"An unexpected error occurred while fetching media items for album {album_id}: {e}")

    print(f"Finished fetching. Total media items found: {len(media_items)}")
    return media_items

def download_media_item(
    session: requests.Session,
    media_item: Dict[str, Any],
    download_path: Path,
    max_retries: int = MAX_RETRIES,
    retry_delay: int = RETRY_DELAY
) -> bool:
    """Downloads a single media item with retries."""
    item_id = media_item.get('id')
    filename = media_item.get('filename', f"untitled_{item_id}")
    base_url = media_item.get('baseUrl')

    if not base_url:
        print(f"Warning: Media item {item_id} ('{filename}') has no base URL. Skipping.")
        return False

    # Determine download URL (photos need '=d', videos usually don't)
    # The API docs suggest using '=d' for direct download.
    download_url = f"{base_url}=d"

    filepath = download_path / filename
    if filepath.exists():
        print(f"Skipping download, file already exists: {filepath.name}")
        return True # Treat as success if already exists

    print(f"  Downloading: {filename}...")

    for attempt in range(max_retries):
        try:
            response = session.get(download_url, stream=True, timeout=60) # Increased timeout
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"  Successfully downloaded: {filename}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"  Error downloading {filename} (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"  Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"  Failed to download {filename} after {max_retries} attempts.")
                # Optionally remove partially downloaded file
                if filepath.exists():
                    try:
                        filepath.unlink()
                    except OSError as unlink_err:
                        print(f"  Warning: Could not remove partial file {filepath}: {unlink_err}")
                return False
        except Exception as e: # Catch other potential errors during file writing etc.
             print(f"  An unexpected error occurred during download of {filename}: {e}")
             return False # Don't retry on unexpected errors

    return False # Should not be reached, but ensures a return value

# --- Album Downloading and Zipping ---
def download_album(
    service: Resource,
    album: Dict[str, Any],
    base_download_dir: Path,
    max_retries: int = MAX_RETRIES,
    retry_delay: int = RETRY_DELAY
) -> None:
    """Downloads all media items in an album and zips them."""
    album_id = album.get('id')
    album_title = album.get('title', f"Untitled_Album_{album_id}")
    # Sanitize title for filesystem use
    safe_album_title = "".join(c for c in album_title if c.isalnum() or c in (' ', '_', '-')).rstrip()
    if not safe_album_title: # Handle cases where title becomes empty after sanitizing
        safe_album_title = f"Album_{album_id}"

    print(f"\nProcessing album: '{album_title}' (ID: {album_id})")

    media_items = get_album_media_items(service, album_id)
    if not media_items:
        print(f"No media items found in album '{album_title}'. Skipping zip creation.")
        return

    # Create a temporary directory for this album's downloads
    temp_album_dir = base_download_dir / f"{safe_album_title}_temp"
    zip_file_path = base_download_dir / f"{safe_album_title}.zip"

    if zip_file_path.exists():
        print(f"Zip file already exists: {zip_file_path.name}. Skipping download.")
        return

    try:
        temp_album_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created temporary directory: {temp_album_dir}")

        download_count = 0
        fail_count = 0
        total_items = len(media_items)

        # Use a session for potential connection reuse
        with requests.Session() as session:
            # Add authentication headers if needed (usually not for baseUrl=d)
            # Check Google Photos API docs if direct downloads require auth headers
            pass

            for i, item in enumerate(media_items):
                print(f" Album '{safe_album_title}' - Item {i+1}/{total_items}")
                if download_media_item(session, item, temp_album_dir, max_retries, retry_delay):
                    download_count += 1
                else:
                    fail_count += 1
                time.sleep(0.1) # Small delay between downloads

        if fail_count > 0:
            print(f"Warning: Failed to download {fail_count} items for album '{safe_album_title}'.")

        if download_count == 0 and fail_count > 0:
             print(f"Error: No items were successfully downloaded for album '{safe_album_title}'. Skipping zip creation.")
             # Clean up temp dir early if nothing was downloaded
             try:
                 for item_path in temp_album_dir.iterdir():
                     item_path.unlink()
                 temp_album_dir.rmdir()
                 print(f"Removed empty temporary directory: {temp_album_dir}")
             except OSError as e:
                 print(f"Error removing temporary directory {temp_album_dir}: {e}")
             return # Exit function early

        # Create the zip file
        print(f"Creating zip file: {zip_file_path.name}...")
        try:
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for item_path in temp_album_dir.iterdir():
                    if item_path.is_file(): # Ensure it's a file before adding
                        zipf.write(item_path, arcname=item_path.name)
            print(f"Successfully created zip file: {zip_file_path.name}")
        except zipfile.BadZipFile as e:
            print(f"Error creating zip file {zip_file_path.name}: {e}")
            # Optionally remove corrupted zip file
            if zip_file_path.exists():
                try:
                    zip_file_path.unlink()
                except OSError as unlink_err:
                    print(f"Warning: Could not remove corrupted zip file {zip_file_path}: {unlink_err}")
        except OSError as e:
             print(f"File system error during zipping for {zip_file_path.name}: {e}")


    finally:
        # Clean up the temporary directory
        if temp_album_dir.exists():
            print(f"Cleaning up temporary directory: {temp_album_dir}")
            try:
                for item_path in temp_album_dir.iterdir():
                    item_path.unlink() # Delete files first
                temp_album_dir.rmdir() # Delete empty directory
                print(f"Removed temporary directory: {temp_album_dir}")
            except OSError as e:
                print(f"Error removing temporary directory {temp_album_dir}: {e}")
                print("Please remove it manually.")


# --- Main Execution ---
def main():
    """Main function to parse arguments and execute commands."""
    parser = argparse.ArgumentParser(
        description="Download Google Photos albums.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=README_TEXT # Display README as part of help
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--list',
        action='store_true',
        help='List all album names and IDs, then exit.'
    )
    group.add_argument(
        '--album-id',
        type=str,
        metavar='ALBUM_ID',
        help='Download a specific album by its ID.'
    )
    group.add_argument(
        '--all',
        action='store_true',
        help='Download all albums.'
    )

    # Add a hidden argument to just show the readme
    parser.add_argument(
        '--readme',
        action='store_true',
        help=argparse.SUPPRESS # Hide from standard help
    )


    args = parser.parse_args()

    if args.readme:
        print(README_TEXT)
        exit(0)

    # If no arguments were given, print help and exit
    if not args.list and not args.album_id and not args.all:
        parser.print_help()
        exit(0)

    print("Starting Google Photos Downloader...")

    # Ensure download directory exists
    try:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Downloads will be saved to: {DOWNLOAD_DIR.resolve()}")
    except OSError as e:
        print(f"Error creating download directory {DOWNLOAD_DIR}: {e}")
        exit(1)


    credentials = authenticate()
    service = get_photos_service(credentials)

    if args.list:
        albums = list_albums(service)
        if albums:
            print("\nAvailable Albums:")
            print("-" * 30)
            for album in albums:
                print(f"  Title: {album.get('title', 'Untitled')}")
                print(f"  ID:    {album.get('id')}")
                print("-" * 30)
        else:
            print("No albums found in your library.")

    elif args.album_id:
        album = get_album_by_id(service, args.album_id)
        if album:
            download_album(service, album, DOWNLOAD_DIR, MAX_RETRIES, RETRY_DELAY)
        else:
            print(f"Could not proceed with download for album ID: {args.album_id}")


    elif args.all:
        albums = list_albums(service)
        if albums:
            print(f"\nStarting download for {len(albums)} albums...")
            for i, album in enumerate(albums):
                print(f"\n--- Album {i+1}/{len(albums)} ---")
                download_album(service, album, DOWNLOAD_DIR, MAX_RETRIES, RETRY_DELAY)
            print("\nFinished downloading all albums.")
        else:
            print("No albums found to download.")

    print("\nGoogle Photos Downloader finished.")

if __name__ == '__main__':
    main()
