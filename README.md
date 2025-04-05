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
- **Downloads media items in their original quality when available.**

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
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib requests tqdm
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
