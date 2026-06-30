#!/bin/bash

set -euo pipefail

if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

RECORDS="$LILAKOSHA_VOLUME_PROCESSED/cdm/records"

printf "UUID\tPLAYER_NAME\tPLAYER_GENDER\tBOT_NAME\tBOT_GENDER\n"

for f in "$RECORDS"/*.json; do
    uuid=$(basename "$f" .json)

    jq -r \
        --arg id "$uuid" \
        '[
            $id,
            first(.meta.identities[]
                | select(.is_player_controlled)
                | .name),
            first(.meta.identities[]
                | select(.is_player_controlled)
                | .gender),
            first(.meta.identities[]
                | select(.is_player_controlled | not)
                | .name),
            first(.meta.identities[]
                | select(.is_player_controlled | not)
                | .gender)
        ] | @tsv' \
        "$f"
done | column -t -s $'\t'
