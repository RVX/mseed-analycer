import streamlit as st
from obspy import read, Stream
import io
import numpy as np
from scipy.io import wavfile
from pydub import AudioSegment
import requests
from bs4 import BeautifulSoup
import concurrent.futures
import time
import datetime
import re
import os

st.set_page_config(page_title="MiniSEED Analyzer", layout="wide")
st.title("📈 MiniSEED File Analyzer for Midnight Zone Mirror Room")
st.markdown("Upload a `.mseed` file or fetch from OOI database to explore seismic data.")

st.markdown("""
This tool allows you to fetch, merge, and convert hydrophone MiniSEED files from the OOI database or your local computer.

You can select how many files to process and how many to download in parallel. The merged seismic data can be exported as WAV or MP3 audio for further analysis or creative use.

Coded By [**@Victor Mazon Gardoqui**](https://github.com/rvx) (May 2025, CC-BY-NC-SA 4.0)
""")

st.header("Fetch MiniSEED files from multiple OOI remote deployments")

use_today = st.checkbox("Use today's date for OOI folders", value=True)

if use_today:
    today = datetime.datetime.utcnow()
    base_urls = [
        "https://rawdata-west.oceanobservatories.org/files/CE02SHBP/LJ01D/HYDBBA106",
        "https://rawdata-west.oceanobservatories.org/files/RS03AXPS/PC03A/HYDBBA303",
        "https://rawdata-west.oceanobservatories.org/files/RS03AXBS/LJ03A/HYDBBA302"
    ]
    remote_urls = [
        f"{base_url}/{today.year:04d}/{today.month:02d}/{today.day:02d}/"
        for base_url in base_urls
    ]
    st.info("Auto-selected folders for today:")
    for url in remote_urls:
        st.write(url)
else:
    today = datetime.datetime.utcnow()
    urls_text = st.text_area(
        "Enter one or more remote folder URLs (one per line):",
        value=(
            f"https://rawdata-west.oceanobservatories.org/files/CE02SHBP/LJ01D/HYDBBA106/{today.year:04d}/{today.month:02d}/{today.day:02d}/\n"
            f"https://rawdata-west.oceanobservatories.org/files/RS03AXPS/PC03A/HYDBBA303/{today.year:04d}/{today.month:02d}/{today.day:02d}/\n"
            f"https://rawdata-west.oceanobservatories.org/files/RS03AXBS/LJ03A/HYDBBA302/{today.year:04d}/{today.month:02d}/{today.day:02d}/"
        )
    )
    remote_urls = [line.strip() for line in urls_text.splitlines() if line.strip()]

col1, col2 = st.columns(2)
with col1:
    NUM_FILES_TO_PROCESS = st.number_input(
        "Number of MiniSEED files to process (from the most recent ones, skipping the last one as its been stored):",
        min_value=1, max_value=100, value=12, step=1
    )
with col2:
    MAX_WORKERS = st.number_input(
        "Number of parallel downloads:",
        min_value=1, max_value=32, value=12, step=1
    )

export_format = st.radio(
    "Select export format:",
    ("WAV", "MP3"),
    horizontal=True
)

fetch = st.button("Fetch and Merge All MiniSEED Files")

def list_mseed_files(url):
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        files = []
        for link in soup.find_all("a"):
            href = link.get("href")
            if href and href.endswith(".mseed"):
                files.append(url + href)
        return files
    except Exception as e:
        st.warning(f"Could not list files at {url}: {e}")
        return []

def download_file(url, retries=3, delay=1):
    for attempt in range(retries):
        try:
            r = requests.get(url)
            r.raise_for_status()
            return read(io.BytesIO(r.content))
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                return e

def download_and_merge(files):
    merged_stream = Stream()
    progress_bar = st.progress(0, text="Starting download and merge...")
    status_text = st.empty()
    total = len(files)
    start_time = time.time()
    total_bytes = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(download_file, f): f for f in files}
        for idx, future in enumerate(concurrent.futures.as_completed(future_to_url)):
            url = future_to_url[future]
            try:
                result = future.result()
                if isinstance(result, Exception):
                    st.warning(f"Failed to load {url}: {result}")
                elif not result or len(result) == 0 or not hasattr(result[0], "data") or len(result[0].data) == 0:
                    st.warning(f"File {url} is empty or corrupted. Skipping.")
                else:
                    merged_stream += result
                    try:
                        head = requests.head(url)
                        size = int(head.headers.get('content-length', 0))
                        total_bytes += size
                    except Exception:
                        pass
            except Exception as e:
                st.warning(f"Failed to load {url}: {e}")
            elapsed = time.time() - start_time
            avg_time = elapsed / (idx + 1)
            remaining = avg_time * (total - (idx + 1))
            speed = (total_bytes / 1024 / 1024) / elapsed if elapsed > 0 else 0
            progress_bar.progress(
                (idx + 1) / total,
                text=f"Loaded {idx+1}/{total} files. "
                     f"Est. {int(remaining)}s left. "
                     f"Avg speed: {speed:.2f} MB/s"
            )
    status_text.success("All files processed.")
    progress_bar.empty()
    return merged_stream

def process_remote_url(remote_url, num_files, export_format):
    files = list_mseed_files(remote_url)
    st.write(f"Found {len(files)} MiniSEED files in {remote_url}")
    if not files:
        st.warning(f"No MiniSEED files found in {remote_url}. Skipping.")
        return
    if len(files) > 1:
        files_to_process = files[-(num_files+1):-1]
        st.info(f"Processing the last {num_files} files (skipping the most recent) from {remote_url}")
    else:
        files_to_process = files
        st.info(f"Not enough files to skip the last one in {remote_url}; processing all available files.")

    if files_to_process:
        stream = download_and_merge(files_to_process)
        st.success(f"Merged {len(stream)} traces from {len(files_to_process)} files for this station.")

        all_data = np.concatenate([tr.data for tr in stream])
        all_data = all_data - np.mean(all_data)
        sample_rate = int(stream[0].stats.sampling_rate)
        if all_data.dtype != np.int16:
            norm_all_data = all_data.astype(np.int16)
        else:
            norm_all_data = all_data

        match = re.search(r'/files/([^/]+)/([^/]+)/([^/]+)/(\d{4})/(\d{2})/(\d{2})/', remote_url)
        if match:
            site, node, sensor, year, month, day = match.groups()
            folder_part = f"{site}_{node}_{sensor}_{year}_{month}_{day}"
        else:
            folder_part = "HYDROPHONE_SONIFICATION"
        sonification_time = datetime.datetime.utcnow().strftime("%H%M%S")
        filename_base = f"{folder_part}_{sonification_time}_sonification"

        output_dir = os.path.join(os.path.dirname(__file__), "sonifications")
        os.makedirs(output_dir, exist_ok=True)
        wav_path = os.path.join(output_dir, f"{filename_base}.wav")
        mp3_path = os.path.join(output_dir, f"{filename_base}.mp3")

        if export_format == "WAV":
            wavfile.write(wav_path, sample_rate, norm_all_data)
            st.success(f"WAV file saved to: `{wav_path}`")
        elif export_format == "MP3":
            all_wav_buffer = io.BytesIO()
            wavfile.write(all_wav_buffer, sample_rate, norm_all_data)
            all_wav_buffer.seek(0)
            audio = AudioSegment.from_wav(all_wav_buffer)
            audio.export(mp3_path, format="mp3")
            st.success(f"MP3 file saved to: `{mp3_path}`")

if fetch:
    with st.spinner("Fetching and merging MiniSEED files..."):
        for remote_url in remote_urls:
            process_remote_url(remote_url, NUM_FILES_TO_PROCESS, export_format)

st.header("Or upload a local MiniSEED file")
uploaded_file = st.file_uploader("Upload a MiniSEED file", type=["mseed"])
if uploaded_file is not None:
    # You can add your local file handling code here, similar to the remote logic above
    pass