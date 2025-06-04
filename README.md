# MiniSEED File Analyzer

A Streamlit web app and CLI tool to fetch, merge, and export hydrophone MiniSEED data as WAV or MP3 audio files using ObsPy.

---

## Features

- Fetch MiniSEED files from OOI remote folders (auto-select today's folder or custom URL)
- Select how many files to process and how many to download in parallel
- Remove DC offset before export
- Export merged seismic data as WAV or MP3 (saved to a `sonifications` folder)
- Upload and process local `.mseed` files (basic support)
- CLI mode for automated, scheduled sonification

---

## Requirements

- Python 3.8+
- [ffmpeg](https://ffmpeg.org/download.html) (for MP3 export)
- Install dependencies from `requirements.txt`:

    ```sh
    pip install -r requirements.txt
    ```

- Required Python packages:
    - streamlit
    - obspy
    - pydub
    - beautifulsoup4
    - numpy
    - scipy
    - requests

---

## Usage

### Web App

1. Clone or download this repository.
2. (Optional) Create and activate a virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Install ffmpeg and add it to your system PATH for MP3 export.
5. Run the app:

    ```sh
    streamlit run mseed-analycer-app.py
    ```

6. Open [http://localhost:8501](http://localhost:8501) in your browser.
7. Use the app to fetch, process, and export MiniSEED data.

---

### Automated Hourly Sonification (CLI Mode)

You can run the analyzer from the terminal for automation.  
The CLI script will automatically process all 5 OOI hydrophone locations for **today's date**.

**Export as WAV:**
```sh
python mseed-analycer-cli.py --num-files 14 --export-format WAV
```

**Export as MP3:**
```sh
python mseed-analycer-cli.py --num-files 14 --export-format MP3
```

- Output files are saved in the `sonifications` folder.
- Schedule this command with your system's scheduler (cron, Task Scheduler, etc.) to run hourly.

---

## Troubleshooting

- **MP3 export unavailable:**  
  Ensure `ffmpeg` is installed and available in your system PATH.
- **File not found in browser:**  
  Exported files are saved to the `sonifications` folder next to the script.

---

## License

CC-BY-NC-SA 4.0