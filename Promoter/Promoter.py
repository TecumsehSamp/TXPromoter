from __future__ import print_function
import argparse
import iota
import logging
import os
import random
import sys
import time

logger = logging.getLogger()

def setup_logging(name):

    logdir = os.path.join('logs', time.strftime("%d-%m-%Y"))
    if not os.path.exists(logdir):
        os.makedirs(logdir)
    
    os.environ['TZ'] = 'Europe/Amsterdam'
    try:
        time.tzset()
    except Exception:
        pass
    
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', '%d.%m.%Y %H:%M:%S')

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    fh = logging.FileHandler(os.path.join(logdir,time.strftime("%H%M%S")+"_"+name))
    fh.setFormatter(formatter)
    logger.addHandler(fh)

def get_depth():
    return random.randint(3,14)

def promote_tx(txid):
    logger.info('------------------------Start------------------------')
    node = 'http://localhost:14265'
    api = iota.Iota(node)
       
    inputtx = iota.Transaction.from_tryte_string(api.get_trytes([iota.TransactionHash(iota.TryteString(txid.encode('ascii')))])['trytes'][0])
    logger.info('start promoting tx (%smin): %s', round((time.time()-inputtx.timestamp)/60), txid)
    bundlehash = inputtx.bundle_hash
    logger.info('bundle: %s', bundlehash)

    count = 0
    maxCount = 5
    while (True):
        txhashes = api.find_transactions([bundlehash])['hashes']
        logger.info('found %s tx in bundle', len(txhashes))

        if any(confirmed == True for confirmed in api.get_latest_inclusion(txhashes)['states'].values()):
            logger.info('!!!tx confirmed!!!')
            break

        txtrytes = api.get_trytes(txhashes)['trytes']        
        for x in txtrytes:
            tx = iota.Transaction.from_tryte_string(x)

            if (tx.is_tail):
                if (count < maxCount):
                    try:
                        logger.info('promoting tx: %s', tx.hash)
                        promotiontx = api.promote_transaction(tx.hash, get_depth())['bundle'][0]
                        logger.debug('created tx: %s', promotiontx.hash)
                    except Exception as err:
                        logger.error(format(err))
                else:
                    if (api.is_reattachable([tx.address])['reattachable'][0]):
                        try:
                            logger.info('reattaching tx: %s', tx.hash)
                            reattachtx = api.replay_bundle(tx.hash,get_depth())['bundle'][0]
                            logger.debug('created tx: %s', reattachtx.hash)
                        except Exception as err:
                            pass
                            logger.error(format(err))
                        break
        
        if (count == maxCount):
            count = 0
        else:
            count += 1

        logger.info('finished. %s more runs until reattach', maxCount-count)
        sleeping = random.randint(0,2)
        while (sleeping > 0):
            logger.info('%s min sleep...', sleeping)
            time.sleep(60)
            sleeping -= 1

        logger.info('------------------------Finish------------------------')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Promote / Reattach IOTA transaction')
    parser.add_argument('-tx')

    args = parser.parse_args()

    if (args.tx is not None):
        setup_logging(args.tx)        
        promote_tx(args.tx)
    else:
        setup_logging('autopromote')
        pass    