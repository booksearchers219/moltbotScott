#!/usr/bin/env bash

if [ -z "$MOLTBOOK_TOKEN" ]; then
  echo "ERROR: MOLTBOOK_TOKEN is not set"
  exit 1
fi

echo "Checking Moltbook mentions feed..."
echo "--------------------------------"

curl -s "https://www.moltbook.com/api/v1/posts?filter=mentions" \
  -H "Authorization: Bearer $MOLTBOOK_TOKEN" \
  | head -n 40

echo
echo "--------------------------------"
echo "Done."

