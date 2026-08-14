#!/bin/bash

watch -n 600 "./run.sh \
    pipeline/35-report-health.yml \
    --report_hide_anomaly_details true \
    --report_breakdown true \
    $@"
