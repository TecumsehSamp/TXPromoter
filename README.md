# TXPromoter
Uses free resources of your node in a useful way by promoting/reattaching non zero transactions.

If anyone is up for creating a proper setup.py or requirements feel free to do that via PR!

## Prerequisites
* access to a node (iri 1.4.1.6+). You have two options:
	* node with pow and remote api enabled (need to change api init to that host)
	* own node where this script can run locally
* valid python installation that can run this script including:
	* install current PyOTA 2.0.4 (https://github.com/iotaledger/iota.lib.py/releases/tag/2.0.4)
	    * pip install pyota
    * install current PyOTA-CCurl 1.0.9 (https://github.com/todofixthis/pyota-ccurl/releases/tag/1.0.9) to make it even faster! (optional but strongly recommended)
        * pip install pyota[ccurl]

## How to use
* just start the script with:
    * no arguments: autopromotes tips from your localhost. will run indefinitely
    * -tx txid: promotes tx until it's confirmed (or a max of 3h is reaching). will exit after that.