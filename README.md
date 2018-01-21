# TXPromoter
Made this in a few mins.. Hands on logging, not much error handling but it works.. :)

## Prerequisites
* node (iri 1.4.1.6+) either/or
	* node with pow and remote api enabled (need to change api init to that host)
	* own node where this script can run locally
* valid python installation that can run this script
	* install current PyOTA develop branch which is right now commit 033d6ecfd5da347fcf977021d0ea7745ed7008f8 (https://github.com/iotaledger/iota.lib.py/tree/develop)

## How to use
* no arguments: autopromotes tips from your localhost. will run indefinitely
* -tx txid: promotes tx until it's confirmed. will exit after that.