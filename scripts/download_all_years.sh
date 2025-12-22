#!/bin/bash
# Download NYC Spending Data for Multiple Fiscal Years
# Run this to download the past 5 years of data

echo "================================================================================"
echo "NYC SPENDING - MULTI-YEAR DOWNLOAD"
echo "================================================================================"
echo "This will download FY2020-2024 (5 fiscal years)"
echo ""

# Array of fiscal years to download
YEARS=(2024 2023 2022 2021 2020)

for YEAR in "${YEARS[@]}"; do
    echo ""
    echo "================================================================================"
    echo "Starting download for FY$YEAR"
    echo "================================================================================"
    echo ""

    python3 download_fiscal_year.py $YEAR

    if [ $? -eq 0 ]; then
        echo ""
        echo "✓ FY$YEAR download complete"
        echo ""
        echo "Merging FY$YEAR chunks..."
        python3 merge_fiscal_year.py $YEAR

        if [ $? -eq 0 ]; then
            echo "✓ FY$YEAR merge complete"
        else
            echo "✗ FY$YEAR merge failed"
            exit 1
        fi
    else
        echo "✗ FY$YEAR download failed"
        exit 1
    fi

    echo ""
    echo "================================================================================"
    echo "FY$YEAR COMPLETE"
    echo "================================================================================"
    echo ""
done

echo ""
echo "================================================================================"
echo "ALL YEARS DOWNLOADED SUCCESSFULLY!"
echo "================================================================================"
echo "Downloaded files:"
ls -lh fy20*_full.csv
echo ""
echo "Total disk space used:"
du -sh fy20*_chunks fy20*_full.csv
echo "================================================================================"
