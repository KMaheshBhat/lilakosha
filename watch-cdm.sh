#!/bin/bash

watch -n 120 "./run.sh \
    pipeline/35-report-records.yml \
    --audit_only true \
    --hide_anomaly_details true \
    --report_breakdown true \
    $@"
