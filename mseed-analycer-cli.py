import argparse
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
import sys

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
        print(f"WARNING: Could not list files at {url}: {e}")
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

def download_and_merge(files, max_workers):
    merged_stream = Stream()
    total = len(files)
    start_time = time.time()
    total_bytes = 0
    print(f"Starting download and merge of {total} files...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(download_file, f): f for f in files}
        for idx, future in enumerate(concurrent.futures.as_completed(future_to_url)):
            url = future_to_url[future]
            try:
                result = future.result()
                if isinstance(result, Exception):
                    print(f"WARNING: Failed to load {url}: {result}")
                elif not result or len(result) == 0 or not hasattr(result[0], "data") or len(result[0].data) == 0:
                    print(f"WARNING: File {url} is empty or corrupted. Skipping.")
                else:
                    merged_stream += result
                    try:
                        head = requests.head(url)
                        size = int(head.headers.get('content-length', 0))
                        total_bytes += size
                    except Exception:
                        pass
            except Exception as e:
                print(f"WARNING: Failed to load {url}: {e}")
            elapsed = time.time() - start_time
            avg_time = elapsed / (idx + 1)
            remaining = avg_time * (total - (idx + 1))
            speed = (total_bytes / 1024 / 1024) / elapsed if elapsed > 0 else 0
            print(
                f"Loaded {idx+1}/{total} files. "
                f"Est. {int(remaining)}s left. "
                f"Avg speed: {speed:.2f} MB/s"
            )
    print("All files processed.")
    return merged_stream

def process_remote_url(remote_url, num_files, export_format, max_workers):
    files = list_mseed_files(remote_url)
    print(f"Found {len(files)} MiniSEED files in {remote_url}")
    if not files:
        print(f"WARNING: No MiniSEED files found in {remote_url}. Skipping.")
        return
    if len(files) > 1:
        files_to_process = files[-(num_files+1):-1]
        print(f"Processing the last {num_files} files (skipping the most recent) from {remote_url}")
    else:
        files_to_process = files
        print(f"Not enough files to skip the last one in {remote_url}; processing all available files.")

    if files_to_process:
        stream = download_and_merge(files_to_process, max_workers)
        print(f"Merged {len(stream)} traces from {len(files_to_process)} files for this station.")

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
            print(f"WAV file saved to: {wav_path}")
        elif export_format == "MP3":
            all_wav_buffer = io.BytesIO()
            wavfile.write(all_wav_buffer, sample_rate, norm_all_data)
            all_wav_buffer.seek(0)
            audio = AudioSegment.from_wav(all_wav_buffer)
            audio.export(mp3_path, format="mp3")
            print(f"MP3 file saved to: {mp3_path}")

def main():
    parser = argparse.ArgumentParser(description="MiniSEED Analyzer CLI")
    parser.add_argument("--num-files", type=int, default=4, help="Number of files to process")
    parser.add_argument("--export-format", type=str, choices=["WAV", "MP3"], default="WAV", help="Export format")
    parser.add_argument("--max-workers", type=int, default=8, help="Number of parallel downloads")
    args = parser.parse_args()

    # Define base URLs
    base_urls = [
        "https://rawdata-west.oceanobservatories.org/files/CE02SHBP/LJ01D/HYDBBA106",
        "https://rawdata-west.oceanobservatories.org/files/RS03AXPS/PC03A/HYDBBA303",
        "https://rawdata-west.oceanobservatories.org/files/RS03AXBS/LJ03A/HYDBBA302",
        "https://rawdata-west.oceanobservatories.org/files/RS01SBPS/PC01A/HYDBBA103",
        "https://rawdata-west.oceanobservatories.org/files/CE04OSBP/LJ01C/HYDBBA105"
    ]
    today = datetime.datetime.utcnow()
    remote_urls = [
        f"{base_url}/{today.year:04d}/{today.month:02d}/{today.day:02d}/"
        for base_url in base_urls
    ]

    for url in remote_urls:
        process_remote_url(
            remote_url=url,
            num_files=args.num_files,
            export_format=args.export_format,
            max_workers=args.max_workers
        )

if __name__ == "__main__":
    main()