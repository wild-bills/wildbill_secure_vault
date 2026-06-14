#!/bin/bash

# Create the folder right inside your project directory
mkdir -p upload_ready

echo "Scanning /home/wildbill/adult_clipart_factory/ for ZIP files..."

# Scan the exact home folder and copy them here
find /home/wildbill/adult_clipart_factory/ -type f -name "*.zip" -exec cp {} ./upload_ready/ \;

echo "------------------------------------------------"
echo "Process Finished!"
echo "Total files successfully copied: $(ls -1 ./upload_ready/ | wc -l)"
