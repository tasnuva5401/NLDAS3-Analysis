# -*- coding: utf-8 -*-
"""
Created on Fri May 23 11:05:32 2025

@author: tasnuva.rouf
"""

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import s3fs
import os
import time  # Add this import at the top
from datetime import datetime


def process_file(url, crop_bounds, out_dir, plot=False):
    """
    Processes one NetCDF file and prints processing time.
    """
    start_time = time.time()  # Start timer

    s3 = s3fs.S3FileSystem(anon=True)
    with s3.open(url, mode='rb') as infile:
        ds = xr.open_dataset(infile, engine='h5netcdf')

        # Crop
        lat_min, lat_max, lon_min, lon_max = crop_bounds
        ds_crop = ds.sel(lat=slice(lat_min, lat_max), lon=slice(lon_min, lon_max))

        # Upscale from ~1 km to ~8 km
        ds_coarse = ds_crop.coarsen(lat=8, lon=8, boundary='trim').reduce(np.nanmean)

        # Daily mean from hourly data
        ds_daily = ds_coarse.resample(time='1D').mean()

        # Save NetCDF
        file_name = os.path.basename(url).replace('.nc', '_daily_crop.nc')
        local_path = os.path.join(out_dir, file_name)
        ds_daily.to_netcdf(local_path)
        print(f"Saved: {local_path}")

        # Extract and format date
        try:
            raw_date = os.path.basename(url).split('.')[1].strip('A')
            date_obj = datetime.strptime(raw_date, '%Y%m%d')
            formatted_date = date_obj.strftime('%B %d, %Y')
        except Exception:
            formatted_date = "Unknown Date"

        # Plot
        if plot and 'Tair' in ds_daily:
            plt.figure(figsize=(10, 6))
            ds_daily['Tair'].isel(time=0).plot(cmap='coolwarm')
            plt.title(f'Tair Daily Mean - {formatted_date}')
            plt.xlabel('Longitude')
            plt.ylabel('Latitude')
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(local_path.replace('.nc', '.png'), dpi=300)
            plt.close()

    end_time = time.time()  # End timer
    duration = end_time - start_time
    print(f"Processing time for {file_name}: {duration:.2f} seconds")

    return ds_daily


# === User inputs ===
s3_folder = 'nasa-waterinsight/test/NLDAS3_Forcing/201501'
crop_bounds = (9.5, 25, -85, -58)  # (lat_min, lat_max, lon_min, lon_max)
output_dir = 'processed_netcdf_output'
os.makedirs(output_dir, exist_ok=True)

# === Process all files in the folder ===
s3 = s3fs.S3FileSystem(anon=True)
files = s3.ls(s3_folder)

for f in files:
    if f.endswith('.nc'):
        s3_url = 's3://' + f
        try:
            process_file(s3_url, crop_bounds, output_dir, plot=True)
        except Exception as e:
            print(f"Failed to process {s3_url}: {e}")
