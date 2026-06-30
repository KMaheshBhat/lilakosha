#!/bin/bash

watch -n 60 "./run.sh \
    pipeline/35-report-records.yml \
    --audit_only true \
    --hide_anomaly_details true \
    --report_breakdown true \
    $@"
