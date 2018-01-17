# TXPromoter
Made this in a few mins.. Hands on logging, not much error handling but it works.. :)

## Prerequisites
- working node using iri 1.4.1.6 including valid python installation that can run this script
- install current PyOTA develop branch which is right now commit 702760a (https://github.com/iotaledger/iota.lib.py)

## How to use
* no arguments: autopromotes tips from your localhost that have at least 1ki value and are older than 20mins. will run indefinitely
* -tx txid: promotes tx until it's confirmed. will exit after that.